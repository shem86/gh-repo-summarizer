from unittest.mock import AsyncMock, patch

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
