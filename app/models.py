import re

from pydantic import BaseModel, field_validator


class SummarizeRequest(BaseModel):
    github_url: str

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r"^https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/?$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid GitHub URL. Expected format: https://github.com/owner/repo"
            )
        return v.rstrip("/")


class SummarizeResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
