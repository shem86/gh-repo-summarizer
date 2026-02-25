import asyncio
import re
from pathlib import PurePosixPath
from typing import Optional

import httpx

from app.config import settings

GITHUB_API_BASE = "https://api.github.com"

# Token budget constants (char-based, ~4 chars per token)
MAX_TOTAL_CHARS = 350_000  # ~87K tokens, conservative for 200K context
MAX_FILE_CHARS = 30_000  # truncate any single file
FETCH_CONCURRENCY = 10

# --- Skip lists ---

ALWAYS_SKIP_DIRS: set[str] = {
    "node_modules",
    ".git",
    "vendor",
    "third_party",
    "dist",
    "build",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "eggs",
    ".eggs",
    "bower_components",
    "jspm_packages",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".cache",
}

ALWAYS_SKIP_EXTENSIONS: set[str] = {
    # Binary/media
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".flv", ".wmv",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Compiled/minified
    ".min.js", ".min.css", ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".class", ".jar", ".exe", ".o", ".a", ".lib",
    # Data/generated
    ".db", ".sqlite", ".sqlite3",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    # Maps
    ".map",
    # Lock files
    ".lock",
}

ALWAYS_SKIP_FILENAMES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "gemfile.lock",
    "poetry.lock",
    "pipfile.lock",
    "composer.lock",
    "cargo.lock",
    ".ds_store",
    "thumbs.db",
}

# --- Include lists ---

ALWAYS_INCLUDE_FILENAMES: set[str] = {
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "cargo.toml",
    "go.mod",
    "gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "makefile",
    "cmakelists.txt",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "tsconfig.json",
    "requirements.txt",
    "environment.yml",
    ".env.example",
    "deno.json",
    "deno.jsonc",
}

# Patterns that match README variants (case-insensitive)
README_PATTERN = re.compile(r"^readme(\.\w+)?$", re.IGNORECASE)

# High-priority entry point patterns
HIGH_PRIORITY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(src/)?(main|index|app|server|cli|__main__)\.\w+$"),
    re.compile(r"^(src/)?(lib|mod)\.\w+$"),
]

# Source code extensions for normal-file prioritization
SOURCE_EXTENSIONS: dict[str, int] = {
    ".py": 0, ".js": 0, ".ts": 0, ".go": 0, ".rs": 0, ".rb": 0,
    ".java": 0, ".jsx": 1, ".tsx": 1, ".c": 1, ".cpp": 1, ".h": 1,
    ".cs": 1, ".swift": 1, ".kt": 1, ".scala": 1, ".ex": 1, ".exs": 1,
    ".vue": 2, ".svelte": 2, ".html": 3, ".css": 3, ".scss": 3,
    ".yaml": 4, ".yml": 4, ".toml": 4, ".json": 4, ".xml": 4,
    ".md": 5, ".txt": 5, ".rst": 5,
    ".sh": 3, ".bash": 3, ".zsh": 3,
}


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url
    )
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return match.group(1), match.group(2)


def _github_headers() -> dict[str, str]:
    """Build headers for GitHub API requests."""
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def classify_file(path: str) -> str:
    """Classify a file path into: 'skip', 'always_include', 'high_priority', or 'normal'."""
    parts = PurePosixPath(path).parts
    filename = parts[-1]
    filename_lower = filename.lower()

    # Check skip dirs
    for part in parts[:-1]:
        if part.lower() in ALWAYS_SKIP_DIRS:
            return "skip"

    # Check skip filenames
    if filename_lower in ALWAYS_SKIP_FILENAMES:
        return "skip"

    # Check skip extensions
    ext = PurePosixPath(filename).suffix.lower()
    if ext in ALWAYS_SKIP_EXTENSIONS:
        return "skip"

    # Check double extensions like .min.js
    if filename_lower.endswith(".min.js") or filename_lower.endswith(".min.css"):
        return "skip"

    # Check README
    if README_PATTERN.match(filename):
        return "always_include"

    # Check always-include filenames
    if filename_lower in ALWAYS_INCLUDE_FILENAMES:
        return "always_include"

    # Check high-priority patterns
    for pattern in HIGH_PRIORITY_PATTERNS:
        if pattern.match(path):
            return "high_priority"

    return "normal"


def build_tree_text(paths: list[str]) -> str:
    """Build a formatted directory tree string from a list of file paths."""
    lines: list[str] = []
    for path in sorted(paths):
        depth = path.count("/")
        name = PurePosixPath(path).name
        # Add trailing / for directories implied by deeper paths
        indent = "  " * depth
        lines.append(f"{indent}{name}")
    return "\n".join(lines)


def file_priority_score(path: str, size: int) -> tuple[int, int, int]:
    """Score a file for priority sorting. Lower = higher priority."""
    depth = path.count("/")
    ext = PurePosixPath(path).suffix.lower()
    ext_priority = SOURCE_EXTENSIONS.get(ext, 8)
    return (depth, ext_priority, size)


async def _get_default_branch(
    client: httpx.AsyncClient, owner: str, repo: str
) -> str:
    """Get the default branch of a repository."""
    resp = await client.get(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
        headers=_github_headers(),
    )
    resp.raise_for_status()
    return resp.json()["default_branch"]


async def _get_file_tree(
    client: httpx.AsyncClient, owner: str, repo: str, branch: str
) -> list[dict]:
    """Get the full recursive file tree."""
    resp = await client.get(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
        headers=_github_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    return [entry for entry in data.get("tree", []) if entry.get("type") == "blob"]


async def _fetch_file_content(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    branch: str,
    semaphore: asyncio.Semaphore,
) -> Optional[dict[str, str]]:
    """Fetch a single file's content. Returns {"path": ..., "content": ...} or None."""
    async with semaphore:
        try:
            headers = _github_headers()
            headers["Accept"] = "application/vnd.github.raw+json"
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                params={"ref": branch},
                headers=headers,
            )
            resp.raise_for_status()

            content = resp.text
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n... [truncated]"

            return {"path": path, "content": content}
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None


async def fetch_repo_content(
    github_url: str,
) -> tuple[str, list[dict[str, str]]]:
    """Fetch repository content: directory tree and selected file contents.

    Returns (tree_text, file_contents) where file_contents is a list of
    {"path": ..., "content": ...} dicts.
    """
    owner, repo = parse_github_url(github_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        branch = await _get_default_branch(client, owner, repo)
        tree_entries = await _get_file_tree(client, owner, repo, branch)

        if not tree_entries:
            raise ValueError("Repository appears to be empty")

        # Build directory tree from all paths
        all_paths = [entry["path"] for entry in tree_entries]
        tree_text = build_tree_text(all_paths)

        # Classify files into buckets
        always_include: list[dict] = []
        high_priority: list[dict] = []
        normal: list[dict] = []

        for entry in tree_entries:
            category = classify_file(entry["path"])
            if category == "skip":
                continue
            elif category == "always_include":
                always_include.append(entry)
            elif category == "high_priority":
                high_priority.append(entry)
            else:
                normal.append(entry)

        # Sort by priority
        high_priority.sort(key=lambda e: e.get("size", 0))
        normal.sort(
            key=lambda e: file_priority_score(e["path"], e.get("size", 0))
        )

        # Apply token budget
        budget = MAX_TOTAL_CHARS - len(tree_text)
        selected_paths: list[str] = []

        for entry in always_include:
            size = entry.get("size", 0)
            cost = min(size, MAX_FILE_CHARS)
            if budget - cost < 0 and selected_paths:
                continue
            budget -= cost
            selected_paths.append(entry["path"])

        for entry in high_priority:
            size = entry.get("size", 0)
            cost = min(size, MAX_FILE_CHARS)
            if budget - cost < 0:
                break
            budget -= cost
            selected_paths.append(entry["path"])

        for entry in normal:
            size = entry.get("size", 0)
            cost = min(size, MAX_FILE_CHARS)
            if budget - cost < 0:
                break
            budget -= cost
            selected_paths.append(entry["path"])

        if not selected_paths:
            raise ValueError(
                "Could not retrieve any content from this repository"
            )

        # Fetch files concurrently
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
        tasks = [
            _fetch_file_content(client, owner, repo, path, branch, semaphore)
            for path in selected_paths
        ]
        results = await asyncio.gather(*tasks)

        file_contents = [r for r in results if r is not None]

        if not file_contents:
            raise ValueError(
                "Could not retrieve any content from this repository"
            )

        return tree_text, file_contents
