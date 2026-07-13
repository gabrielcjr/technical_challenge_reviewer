import logging
import os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .models import EvaluateRequest, HealthResponse
from .repo_cloner import cloned_repo, validate_github_url
from .evaluator import evaluate_repository
from .symfony_client import send_callback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Challenge Evaluator",
    description="Python microservice that evaluates GitHub repos using LangChain + Grok (xAI)/Gemini",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/health", response_model=HealthResponse)
async def health():
    grok_ok = bool(settings.grok_api_key and settings.grok_api_key not in ("", "gsk_test", "xai_test", "test"))
    gemini_ok = bool(settings.gemini_api_key and settings.gemini_api_key not in ("", "test"))
    return HealthResponse(
        status="ok",
        service="python-evaluator",
        llm_provider=settings.llm_provider,
        grok_configured=grok_ok,
        gemini_configured=gemini_ok,
        grok_configured=grok_ok  # backward compat
    )

@app.get("/")
async def root():
    return {"message": "Challenge Evaluator API", "docs": "/docs", "health": "/health"}

def background_evaluation_task(
    submission_id: str,
    github_repo_url: str,
    challenge_text: str,
    callback_url: str,
    callback_token: str
):
    """Background task that does cloning + evaluation + callback"""
    logger.info(f"[Background] Starting evaluation for submission {submission_id}, repo {github_repo_url}")

    try:
        with cloned_repo(github_repo_url) as repo_path:
            logger.info(f"[Background] Repo cloned to {repo_path}")

            # Evaluate
            result, metadata = evaluate_repository(repo_path, challenge_text)

            logger.info(f"[Background] Evaluation completed for {submission_id}: approved={result['approved']}, provider={metadata.get('llm_provider_used')}")

            # Send callback to Symfony
            success = send_callback(
                callback_url=callback_url,
                callback_token=callback_token,
                submission_id=submission_id,
                approved=result['approved'],
                summary=result['summary'],
                improvements=result['improvements'],
                reasoning=result.get('reasoning'),
                raw_output=str(result.get('raw', ''))[:2000]
            )

            if not success:
                logger.error(f"[Background] Callback failed for {submission_id} after retries")
            else:
                logger.info(f"[Background] Callback succeeded for {submission_id}")

    except Exception as e:
        logger.exception(f"[Background] Evaluation failed for {submission_id}: {e}")

        # Try to notify Symfony of failure as REJECTED with error details
        try:
            send_callback(
                callback_url=callback_url,
                callback_token=callback_token,
                submission_id=submission_id,
                approved=False,
                summary=f"Evaluation failed: {str(e)[:200]}",
                improvements=["Check repository URL is valid and public", "Ensure repo is not too large", "Contact admin if issue persists"],
                reasoning=str(e),
                raw_output=str(e)[:1000]
            )
        except Exception as cb_e:
            logger.error(f"[Background] Failed to send failure callback for {submission_id}: {cb_e}")

@app.post("/evaluate", status_code=202)
async def evaluate(request: EvaluateRequest, background_tasks: BackgroundTasks):
    """
    Receives evaluation request from Symfony (webhook).
    Payload: {submissionId, githubRepoUrl, challengeText, callbackUrl, callbackToken}
    Returns 202 immediately and processes in background.
    """

    logger.info(f"Received evaluation request: submissionId={request.submissionId}, repo={request.githubRepoUrl}")

    # Validate GitHub URL
    if not validate_github_url(request.githubRepoUrl):
        # Still accept but log warning; evaluator will fail later if invalid
        logger.warning(f"Invalid GitHub URL format: {request.githubRepoUrl}")

    if not request.challengeText or len(request.challengeText.strip()) < 10:
        raise HTTPException(status_code=400, detail="challengeText too short, minimum 10 chars")

    # Add background task
    background_tasks.add_task(
        background_evaluation_task,
        submission_id=request.submissionId,
        github_repo_url=request.githubRepoUrl,
        challenge_text=request.challengeText,
        callback_url=request.callbackUrl,
        callback_token=request.callbackToken
    )

    return {
        "status": "accepted",
        "submissionId": request.submissionId,
        "message": "Evaluation started in background, result will be sent via callback"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )
