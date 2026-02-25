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

## Model Choice

Uses **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`) — the best balance of speed, cost, and quality for summarization tasks. Opus would be overkill for this use case; Haiku might miss nuance in complex repos.

## Repository Content Strategy

The core challenge is fitting relevant repo information into the LLM context window. The service uses a three-tier priority system:

1. **Always include**: README files, configuration/manifest files (`package.json`, `pyproject.toml`, `Cargo.toml`, `Dockerfile`, etc.)
2. **High priority**: Entry points and main modules (`main.py`, `index.js`, `app.ts`, `server.go`, etc.)
3. **Normal**: Remaining source files, sorted by depth (shallower first) and file size (smaller first)

Files are fetched until a character budget (~350K chars, ~87K tokens) is exhausted. Binary files, lock files, `node_modules/`, `.git/`, vendored dependencies, and other non-informative content are always skipped. Individual files are truncated at 30K characters.

The full directory tree is always sent to the LLM regardless of which files are fetched, giving it a complete picture of the project layout.
