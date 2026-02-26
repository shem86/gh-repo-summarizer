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

    def test_contains_tool_instruction(self):
        prompt = _build_prompt(SAMPLE_TREE, SAMPLE_FILES)
        assert "provide_summary" in prompt


class TestSummarizeRepo:
    async def test_happy_path(self):
        mock_block = type(
            "ToolUseBlock",
            (),
            {
                "type": "tool_use",
                "name": "provide_summary",
                "input": {
                    "summary": "A test project",
                    "technologies": ["Python"],
                    "structure": "Flat structure",
                },
            },
        )()
        mock_response = type("Response", (), {"content": [mock_block]})()

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response

        with patch("app.summarizer.client", mock_client):
            result = await summarize_repo(SAMPLE_TREE, SAMPLE_FILES)

        assert isinstance(result, SummarizeResponse)
        assert result.summary == "A test project"
        assert result.technologies == ["Python"]

    async def test_no_tool_call_raises(self):
        mock_block = type("TextBlock", (), {"type": "text", "text": "hello"})()
        mock_response = type("Response", (), {"content": [mock_block]})()

        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_response

        with patch("app.summarizer.client", mock_client):
            with pytest.raises(RuntimeError, match="expected tool call"):
                await summarize_repo(SAMPLE_TREE, SAMPLE_FILES)
