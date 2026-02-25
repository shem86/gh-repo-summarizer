from anthropic import AsyncAnthropic

from app.config import settings
from app.models import SummarizeResponse

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096

SUMMARY_TOOL = {
    "name": "provide_summary",
    "description": "Provide a structured summary of the GitHub repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A clear, human-readable description of what this project does, its purpose, and key features. 2-4 sentences.",
            },
            "technologies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Main technologies, frameworks, libraries, and languages used. Be specific (e.g. 'React' not 'JavaScript').",
            },
            "structure": {
                "type": "string",
                "description": "Brief description of how the project is organized: key directories, architecture pattern, notable choices. 2-4 sentences.",
            },
        },
        "required": ["summary", "technologies", "structure"],
    },
}

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def _build_prompt(tree_text: str, file_contents: list[dict[str, str]]) -> str:
    """Build the LLM prompt from repo content."""
    files_section = ""
    for f in file_contents:
        files_section += f"\n--- {f['path']} ---\n{f['content']}\n"

    return f"""Analyze the following GitHub repository and provide a structured summary using the provide_summary tool.

## Repository Directory Tree

```
{tree_text}
```

## File Contents
{files_section}

Use the provide_summary tool to return your analysis. Include only technologies clearly evidenced in the code or configuration files."""


async def summarize_repo(
    tree_text: str, file_contents: list[dict[str, str]]
) -> SummarizeResponse:
    """Send repo content to Claude and get a structured summary via tool use."""
    prompt = _build_prompt(tree_text, file_contents)

    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        tools=[SUMMARY_TOOL],
        tool_choice={"type": "tool", "name": "provide_summary"},
    )

    # Extract the tool use block
    for block in response.content:
        if block.type == "tool_use" and block.name == "provide_summary":
            return SummarizeResponse(**block.input)

    raise RuntimeError("LLM did not return the expected tool call")
