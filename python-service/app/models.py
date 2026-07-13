from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class EvaluateRequest(BaseModel):
    submissionId: str = Field(..., description="UUID of submission in Symfony")
    githubRepoUrl: str = Field(..., description="GitHub repo URL")
    challengeText: str = Field(..., description="Challenge requirements text")
    callbackUrl: str = Field(..., description="Symfony callback URL")
    callbackToken: str = Field(..., description="Shared token for callback auth")

class FileInfo(BaseModel):
    path: str
    size: int

class EvaluationResult(BaseModel):
    approved: bool
    summary: str
    improvements: List[str] = []
    reasoning: Optional[str] = None
    raw_output: Optional[str] = None

class CallbackPayload(BaseModel):
    submissionId: str
    approved: bool
    summary: str
    improvements: List[str] = []
    reasoning: Optional[str] = None
    rawOutput: Optional[str] = None
    callbackToken: Optional[str] = None

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "python-evaluator"
    llm_provider: str
    grok_configured: bool
    gemini_configured: bool
    # backward compat
    grok_configured: bool = False
