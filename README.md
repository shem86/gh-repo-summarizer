# GitHub Repository Summarizer

A FastAPI service that takes a GitHub repository URL and returns an LLM-generated summary of the project: what it does, technologies used, and how it's structured.

## Setup

```bash
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Optionally set a GitHub token for higher rate limits (60 req/hr unauthenticated → 5,000 req/hr authenticated):

```bash
GITHUB_TOKEN=ghp_...
```

## Caching

Summaries are cached to disk with a 1-week TTL, so repeated requests for the same repo skip the GitHub API and LLM calls entirely.

Cache files are stored in `.cache/` (e.g. `.cache/psf__requests.json`). To disable caching, set `CACHE_ENABLED=false`.

| Variable | Default | Description |
|---|---|---|
| `CACHE_ENABLED` | `true` | Enable/disable the cache |
| `CACHE_TTL` | `604800` | TTL in seconds (default: 1 week) |
| `CACHE_DIR` | `.cache` | Directory to store cache files |

## Running

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Usage

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

Response:

```json
{
  "summary": "Human-readable description of what the project does",
  "technologies": ["Python", "urllib3", "certifi"],
  "structure": "Brief description of the project structure"
}
```

## Testing

```bash
python3 -m pytest -v
```

Tests cover models (Pydantic validation), GitHub API interaction (mocked with `respx`), LLM summarization (mocked Anthropic client), and FastAPI endpoint error handling. No real API calls are made.

## Model Choice

Uses **Claude Sonnet 4.6** (`claude-sonnet-4-6`)
Opus would be overkill for this use case; Haiku might miss nuance in complex repos.
Sonnet 4.6 represents the "sweet spot" in 2026 for developer tools. It provides Opus-level reasoning for complex architectural patterns while maintaining the speed and cost-efficiency required for a responsive user experience. It is specifically optimized for "tree-first" repository traversal, allowing it to navigate large-scale projects with minimal hallucination.

## Repository Content Strategy

The core challenge is fitting relevant repo information into the LLM context window. The service uses a three-tier priority system:

1. **Always include**: README files, configuration/manifest files (`package.json`, `pyproject.toml`, `Cargo.toml`, `Dockerfile`, etc.)
2. **High priority**: Entry points and main modules (`main.py`, `index.js`, `app.ts`, `server.go`, etc.)
3. **Normal**: Remaining source files, sorted by depth (shallower first) and file size (smaller first)

Files are fetched until a character budget (~350K chars, ~87K tokens) is exhausted. Binary files, lock files, `node_modules/`, `.git/`, vendored dependencies, and other non-informative content are always skipped. Individual files are truncated at 30K characters.

The full directory tree is always sent to the LLM regardless of which files are fetched, giving it a complete picture of the project layout.
