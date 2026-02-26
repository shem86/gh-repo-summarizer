import pytest
import httpx
import respx

from app.github import (
    build_tree_text,
    classify_file,
    fetch_repo_content,
    file_priority_score,
    parse_github_url,
)


# --- Phase 2: Pure functions ---


class TestParseGithubUrl:
    def test_happy_path(self):
        assert parse_github_url("https://github.com/psf/requests") == ("psf", "requests")

    def test_strips_dot_git(self):
        assert parse_github_url("https://github.com/psf/requests.git") == ("psf", "requests")

    def test_trailing_slash(self):
        assert parse_github_url("https://github.com/psf/requests/") == ("psf", "requests")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("https://gitlab.com/psf/requests")

    def test_missing_repo_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("https://github.com/psf")


class TestClassifyFile:
    @pytest.mark.parametrize(
        "path",
        [
            "node_modules/express/index.js",
            ".git/HEAD",
            "__pycache__/mod.cpython-39.pyc",
        ],
    )
    def test_skip_dirs(self, path: str):
        assert classify_file(path) == "skip"

    @pytest.mark.parametrize(
        "path",
        [
            "image.png",
            "fonts/bold.woff2",
            "data.db",
            "archive.zip",
            "bundle.min.js",
        ],
    )
    def test_skip_extensions(self, path: str):
        assert classify_file(path) == "skip"

    @pytest.mark.parametrize("path", ["package-lock.json", "yarn.lock", ".ds_store"])
    def test_skip_filenames(self, path: str):
        assert classify_file(path) == "skip"

    def test_readme_always_include(self):
        assert classify_file("README.md") == "always_include"
        assert classify_file("readme.rst") == "always_include"
        assert classify_file("README") == "always_include"

    def test_config_always_include(self):
        assert classify_file("package.json") == "always_include"
        assert classify_file("pyproject.toml") == "always_include"
        assert classify_file("Cargo.toml") == "always_include"

    def test_high_priority_entry_points(self):
        assert classify_file("main.py") == "high_priority"
        assert classify_file("src/index.ts") == "high_priority"
        assert classify_file("app.js") == "high_priority"

    def test_normal_source_file(self):
        assert classify_file("src/utils/helpers.py") == "normal"
        assert classify_file("lib/parser.rs") == "normal"


class TestBuildTreeText:
    def test_produces_indented_tree(self):
        paths = ["src/main.py", "README.md", "src/utils/helpers.py"]
        result = build_tree_text(paths)
        lines = result.split("\n")
        assert "README.md" in lines
        assert "  main.py" in lines
        assert "    helpers.py" in lines

    def test_empty_input(self):
        assert build_tree_text([]) == ""


class TestFilePriorityScore:
    def test_shallow_python_file_ranks_higher(self):
        shallow = file_priority_score("main.py", 100)
        deep = file_priority_score("a/b/c/main.py", 100)
        assert shallow < deep  # lower = higher priority

    def test_python_ranks_higher_than_yaml(self):
        py = file_priority_score("config.py", 100)
        yml = file_priority_score("config.yml", 100)
        assert py < yml

    def test_smaller_file_ranks_higher(self):
        small = file_priority_score("main.py", 100)
        big = file_priority_score("main.py", 10000)
        assert small < big


# --- Phase 3: Async functions with mocked HTTP ---


OWNER, REPO = "testowner", "testrepo"
BASE_URL = "https://api.github.com"


class TestFetchRepoContent:
    @respx.mock
    async def test_happy_path(self):
        # Mock default branch
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}").mock(
            return_value=httpx.Response(200, json={"default_branch": "main"})
        )
        # Mock tree
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}/git/trees/main").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "README.md", "type": "blob", "size": 50},
                        {"path": "src/main.py", "type": "blob", "size": 100},
                        {"path": "src", "type": "tree"},
                    ]
                },
            )
        )
        # Mock file contents
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}/contents/README.md").mock(
            return_value=httpx.Response(200, text="# Test Repo")
        )
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}/contents/src/main.py").mock(
            return_value=httpx.Response(200, text="print('hello')")
        )

        tree_text, file_contents = await fetch_repo_content(
            f"https://github.com/{OWNER}/{REPO}"
        )

        assert "README.md" in tree_text
        assert "main.py" in tree_text
        assert len(file_contents) >= 1
        paths = [f["path"] for f in file_contents]
        assert "README.md" in paths

    @respx.mock
    async def test_empty_repo_raises(self):
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}").mock(
            return_value=httpx.Response(200, json={"default_branch": "main"})
        )
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}/git/trees/main").mock(
            return_value=httpx.Response(200, json={"tree": []})
        )

        with pytest.raises(ValueError, match="empty"):
            await fetch_repo_content(f"https://github.com/{OWNER}/{REPO}")

    @respx.mock
    async def test_404_raises(self):
        respx.get(f"{BASE_URL}/repos/{OWNER}/{REPO}").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_repo_content(f"https://github.com/{OWNER}/{REPO}")
