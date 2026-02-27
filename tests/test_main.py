from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest

from app.main import app
from app.models import SummarizeResponse


VALID_URL = "https://github.com/owner/repo"
MOCK_TREE = "README.md\nsrc/\n  main.py"
MOCK_FILES = [{"path": "README.md", "content": "# Test"}]
MOCK_RESPONSE = SummarizeResponse(
    summary="A test project",
    technologies=["Python"],
    structure="Flat structure",
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


class TestSummarizeEndpoint:
    async def test_happy_path(self, client):
        with (
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.summarize_repo", new_callable=AsyncMock) as mock_summarize,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_fetch.return_value = (MOCK_TREE, MOCK_FILES)
            mock_summarize.return_value = MOCK_RESPONSE

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "A test project"
        assert data["technologies"] == ["Python"]
        assert data["structure"] == "Flat structure"

    async def test_invalid_url_returns_400(self, client):
        resp = await client.post("/summarize", json={"github_url": "not-a-url"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["status"] == "error"

    async def test_missing_api_key_returns_500(self, client):
        with patch("app.main.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 500
        assert "ANTHROPIC_API_KEY" in resp.json()["message"]

    async def test_repo_not_found_returns_404(self, client):
        mock_resp = httpx.Response(404, request=httpx.Request("GET", "https://api.github.com"))
        with (
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Not Found", request=mock_resp.request, response=mock_resp
            )

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 404
        assert resp.json()["message"] == "Repository not found"

    async def test_rate_limit_returns_429(self, client):
        mock_resp = httpx.Response(403, request=httpx.Request("GET", "https://api.github.com"))
        with (
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Forbidden", request=mock_resp.request, response=mock_resp
            )

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 429
        assert "rate limit" in resp.json()["message"].lower()

    async def test_github_unreachable_returns_502(self, client):
        with (
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_fetch.side_effect = httpx.ConnectError("Connection refused")

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 502
        assert "Unable to reach" in resp.json()["message"]

    async def test_claude_api_error_returns_502(self, client):
        with (
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.summarize_repo", new_callable=AsyncMock) as mock_summarize,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_fetch.return_value = (MOCK_TREE, MOCK_FILES)
            mock_summarize.side_effect = anthropic.APIError(
                message="Internal server error",
                request=httpx.Request("POST", "https://api.anthropic.com"),
                body=None,
            )

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 502
        assert "LLM API error" in resp.json()["message"]


class TestCacheIntegration:
    # Cycle 6 — cache hit skips GitHub + LLM
    async def test_cache_hit_skips_fetch_and_summarize(self, client):
        mock_cache = MagicMock()
        mock_cache.get.return_value = MOCK_RESPONSE.model_dump()

        with (
            patch("app.main._cache", mock_cache),
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.summarize_repo", new_callable=AsyncMock) as mock_summarize,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 200
        assert resp.json()["summary"] == "A test project"
        mock_fetch.assert_not_called()
        mock_summarize.assert_not_called()

    # Cycle 7 — cache miss stores result
    async def test_cache_miss_stores_result(self, client):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with (
            patch("app.main._cache", mock_cache),
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.summarize_repo", new_callable=AsyncMock) as mock_summarize,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.cache_ttl = 604800
            mock_fetch.return_value = (MOCK_TREE, MOCK_FILES)
            mock_summarize.return_value = MOCK_RESPONSE

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 200
        mock_cache.set.assert_called_once_with(
            "owner__repo", MOCK_RESPONSE.model_dump(), 604800
        )

    # Cycle 8 — cache write failure is non-fatal
    async def test_cache_write_failure_is_nonfatal(self, client):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = OSError("disk full")

        with (
            patch("app.main._cache", mock_cache),
            patch("app.main.fetch_repo_content", new_callable=AsyncMock) as mock_fetch,
            patch("app.main.summarize_repo", new_callable=AsyncMock) as mock_summarize,
            patch("app.main.settings") as mock_settings,
        ):
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.cache_ttl = 604800
            mock_fetch.return_value = (MOCK_TREE, MOCK_FILES)
            mock_summarize.return_value = MOCK_RESPONSE

            resp = await client.post("/summarize", json={"github_url": VALID_URL})

        assert resp.status_code == 200
