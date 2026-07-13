from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class EvaluateRequest(BaseModel):
    """Clean DTO with snake_case internally, camelCase alias for external API backward compat."""

    model_config = ConfigDict(populate_by_name=True)

    submission_id: str = Field(..., alias="submissionId", description="UUID of submission in Symfony")
    github_repo_url: str = Field(..., alias="githubRepoUrl", description="GitHub repo URL")
    challenge_text: str = Field(..., alias="challengeText", description="Challenge requirements text")
    callback_url: str = Field(..., alias="callbackUrl", description="Symfony callback URL")
    callback_token: str = Field(..., alias="callbackToken", description="Shared token for callback auth")


class EvaluationResult(BaseModel):
    approved: bool
    summary: str
    improvements: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    raw_output: Optional[str] = None


class CallbackPayload(BaseModel):
    """Callback sent to Symfony - uses Symfony-expected camelCase keys."""

    model_config = ConfigDict(populate_by_name=True)

    submission_id: str = Field(..., alias="submissionId")
    approved: bool
    summary: str
    improvements: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    raw_output: Optional[str] = Field(default=None, alias="rawOutput")
    callback_token: Optional[str] = Field(default=None, alias="callbackToken")

    def to_symfony_dict(self) -> dict:
        return self.model_dump(by_alias=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "python-evaluator"
    llm_provider: str
    grok_configured: bool
    gemini_configured: bool
    xai_configured: bool = False  # backward compat alias
