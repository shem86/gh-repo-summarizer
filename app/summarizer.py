from anthropic import AsyncAnthropic

from app.config import settings
from app.models import SummarizeResponse

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def _build_prompt(tree_text: str, file_contents: list[dict[str, str]]) -> str:
    """Build the LLM prompt from repo content."""
    files_section = ""
    for f in file_contents:
        files_section += f"\n--- {f['path']} ---\n{f['content']}\n"

    return f"""Analyze the following GitHub repository and return a structured summary.

## Repository Directory Tree

```
{tree_text}
```

## File Contents
{files_section}

Include only technologies clearly evidenced in the code or configuration files."""


async def summarize_repo(
    tree_text: str, file_contents: list[dict[str, str]]
) -> SummarizeResponse:
    """Send repo content to Claude and get a structured summary via structured outputs."""
    prompt = _build_prompt(tree_text, file_contents)

    response = await client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        output_format=SummarizeResponse,
    )

    if response.parsed_output is None:
        raise RuntimeError("Claude refused to summarize this repository")

    return response.parsed_output
