# GitHub Repository Summarizer

## Project Overview

A FastAPI service that takes a GitHub repository URL (`POST /summarize`) and returns an LLM-generated summary of the project: what it does, technologies used, and how it's structured. Uses the Anthropic Claude API for summarization.

## Tech Stack

- **Python 3.10+**
- **FastAPI** as the web framework
- **Anthropic Claude** for LLM summarization (choose the best model for the job from available Anthropic models)
- **httpx** for async HTTP requests to GitHub
- **uvicorn** as the ASGI server

## API Contract

### `POST /summarize`

**Request:**

```json
{
  "github_url": "https://github.com/psf/requests"
}
```

**Success response (200):**

```json
{
  "summary": "Human-readable description of what the project does",
  "technologies": ["Python", "urllib3", "certifi"],
  "structure": "Brief description of the project structure"
}
```

**Error response (appropriate HTTP status code):**

```json
{
  "status": "error",
  "message": "Description of what went wrong"
}
```

## Key Design Decisions

### Repository Content Strategy

The core challenge is fitting relevant repo information into the LLM context window. The approach should:

1. **Always include:** README (any variant), directory tree, config/manifest files (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.)
2. **Include selectively:** Key source files (entry points, main modules) — prioritize by relevance
3. **Always skip:** Binary files, lock files, `node_modules/`, `.git/`, vendored dependencies, large generated files, images, fonts
4. **Truncate** individual files that are too long rather than sending them whole
5. **Budget tokens** — keep total content well within the model's context window, leaving room for the prompt and response

There is no single correct approach. Optimize for giving the LLM the best understanding of the project.

### GitHub API Usage

- Use the GitHub REST API
- Use the Git Trees API (`GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`) to get the full file listing in one call
- Fetch individual file contents via the raw content URL or Contents API

### Configuration

- `ANTHROPIC_API_KEY` — **required**, set via environment variable. Never hardcode.

## Project Structure

Keep it simple and flat:

```text
gh-repo-summarizer/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, endpoint definition
│   ├── github.py        # GitHub API interaction, repo fetching
│   ├── summarizer.py    # LLM prompt construction and API call
│   └── models.py        # Pydantic request/response models
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test the endpoint
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

## Code Style

- Use async/await throughout (FastAPI + httpx async)
- Use Pydantic models for request/response validation
- Keep error handling clean — return proper HTTP status codes with the error JSON format
- No over-engineering: no database, no caching, no auth beyond API keys
- Type hints on all functions
