from contextlib import asynccontextmanager
from typing import Optional

import anthropic
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.cache import BaseCache, LocalFileCache
from app.config import settings
from app.github import fetch_repo_content, parse_github_url
from app.models import SummarizeRequest, SummarizeResponse
from app.summarizer import summarize_repo

_cache: Optional[BaseCache] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache
    if settings.cache_enabled:
        _cache = LocalFileCache(settings.cache_dir)
    yield


app = FastAPI(title="GitHub Repository Summarizer", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request, exc: RequestValidationError
) -> JSONResponse:
    messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        messages.append(f"{field}: {error['msg']}" if field else error["msg"])
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": "; ".join(messages)},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal error occurred"},
    )


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest) -> SummarizeResponse:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=500, detail="ANTHROPIC_API_KEY not configured"
        )

    owner, repo = parse_github_url(request.github_url)
    cache_key = f"{owner}__{repo}".lower()

    if _cache is not None:
        cached = _cache.get(cache_key)
        if cached is not None:
            return SummarizeResponse(**cached)

    try:
        tree_text, file_contents = await fetch_repo_content(request.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository not found")
        if e.response.status_code == 403:
            raise HTTPException(
                status_code=429,
                detail="GitHub API rate limit exceeded. Set a GITHUB_TOKEN environment variable or try again later.",
            )
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API error: {e.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Unable to reach GitHub API"
        )

    try:
        result = await summarize_repo(tree_text, file_contents)
    except anthropic.APIError as e:
        raise HTTPException(
            status_code=502, detail=f"LLM API error: {e.message}"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if _cache is not None:
        try:
            _cache.set(cache_key, result.model_dump(), settings.cache_ttl)
        except OSError:
            pass

    return result
