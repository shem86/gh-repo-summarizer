from unittest.mock import AsyncMock, patch

import pytest

from app.models import SummarizeResponse
from app.summarizer import _build_prompt, summarize_repo


SAMPLE_TREE = "README.md\nsrc/\n  main.py"
SAMPLE_FILES = [
    {"path": "README.md", "content": "# Test"},
    {"path": "src/main.py", "content": "print('hello')"},
]


class TestBuildPrompt:
    def test_contains_tree_and_files(self):
        prompt = _build_prompt(SAMPLE_TREE, SAMPLE_FILES)
        assert SAMPLE_TREE in prompt
        assert "--- README.md ---" in prompt
        assert "# Test" in prompt
        assert "--- src/main.py ---" in prompt
        assert "print('hello')" in prompt

    def test_does_not_reference_tool(self):
        prompt = _build_prompt(SAMPLE_TREE, SAMPLE_FILES)
        assert "provide_summary" not in prompt


class TestSummarizeRepo:
    async def test_happy_path(self):
        expected = SummarizeResponse(
            summary="A test project",
            technologies=["Python"],
            structure="Flat structure",
        )
        mock_response = type("ParsedResponse", (), {"parsed_output": expected})()

        mock_client = AsyncMock()
        mock_client.messages.parse.return_value = mock_response

        with patch("app.summarizer.client", mock_client):
            result = await summarize_repo(SAMPLE_TREE, SAMPLE_FILES)

        assert isinstance(result, SummarizeResponse)
        assert result.summary == "A test project"
        assert result.technologies == ["Python"]
        mock_client.messages.parse.assert_called_once()

    async def test_refusal_raises(self):
        mock_response = type("ParsedResponse", (), {"parsed_output": None})()

        mock_client = AsyncMock()
        mock_client.messages.parse.return_value = mock_response

        with patch("app.summarizer.client", mock_client):
            with pytest.raises(RuntimeError, match="refused"):
                await summarize_repo(SAMPLE_TREE, SAMPLE_FILES)
