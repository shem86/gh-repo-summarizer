import pytest
from pydantic import ValidationError

from app.models import ErrorResponse, SummarizeRequest, SummarizeResponse


class TestSummarizeRequest:
    def test_valid_github_url(self):
        req = SummarizeRequest(github_url="https://github.com/owner/repo")
        assert req.github_url == "https://github.com/owner/repo"

    def test_trailing_slash_stripped(self):
        req = SummarizeRequest(github_url="https://github.com/owner/repo/")
        assert req.github_url == "https://github.com/owner/repo"

    @pytest.mark.parametrize(
        "url",
        [
            "https://gitlab.com/owner/repo",
            "https://github.com/owner",
            "",
            "not-a-url",
            "https://github.com/",
        ],
    )
    def test_invalid_urls_rejected(self, url: str):
        with pytest.raises(ValidationError):
            SummarizeRequest(github_url=url)


class TestSummarizeResponse:
    def test_construction(self):
        resp = SummarizeResponse(
            summary="A test project",
            technologies=["Python", "FastAPI"],
            structure="Simple flat structure",
        )
        assert resp.summary == "A test project"
        assert resp.technologies == ["Python", "FastAPI"]
        assert resp.structure == "Simple flat structure"


class TestErrorResponse:
    def test_status_defaults_to_error(self):
        err = ErrorResponse(message="something went wrong")
        assert err.status == "error"
        assert err.message == "something went wrong"

    def test_status_can_be_overridden(self):
        err = ErrorResponse(status="fail", message="oops")
        assert err.status == "fail"
