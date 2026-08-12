import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

from .config import settings
from .models import EvaluateRequest, HealthResponse
from .repo_cloner import cloned_repo, validate_github_url, cleanup_stale_clone_directories
from .evaluator import evaluate_repository
from .symfony_client import EvaluationCallback, send_evaluation_callback
from .callback_replayer import (
    get_failed_path,
    get_failed_callbacks_count,
    replay_failed_callbacks,
    replay_loop,
)

# --- Constants ---
# Keep aligned with Symfony Submission challengeSnapshot min length (20).
MIN_CHALLENGE_TEXT_LENGTH = 20
RAW_OUTPUT_TRUNCATION_LENGTH = 2000
ERROR_SUMMARY_TRUNCATION_LENGTH = 200
ERROR_REASONING_TRUNCATION_LENGTH = 1000
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


_configure_logging()


def verify_internal_token(x_internal_token: str | None = Header(None, alias="X-Internal-Token")) -> None:
    expected_token = settings.callback_token
    if expected_token and expected_token not in ("", "s3cr3t_shared_token_change_me"):
        if not x_internal_token or x_internal_token != expected_token:
            raise HTTPException(status_code=401, detail="Unauthorized internal request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cleanup stale temporary clone folders on startup
    try:
        cleaned = cleanup_stale_clone_directories()
        if (cleaned or 0) > 0:
            logger.info(f"Cleaned up {cleaned} stale clone folders on startup")
    except Exception as cleanup_err:
        logger.warning(f"Startup clone directory cleanup warning: {cleanup_err}")
    # Start DLQ replay cron - guarantees no feedback lost if Symfony was down
    task = asyncio.create_task(replay_loop())
    logger.info("Callback replay cron started")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Callback replay cron stopped")


app = FastAPI(
    title="Challenge Evaluator",
    description="Python microservice that evaluates GitHub repos using LangChain + Groq (free) / Gemini (free quota)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@dataclass(frozen=True)
class EvaluationTask:
    """Value object replacing 5-arg function - clean argument handling."""

    submission_id: str
    github_repo_url: str
    challenge_text: str
    callback_url: str
    callback_token: str


# --- Health ---
@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="python-evaluator",
        llm_provider=settings.llm_provider,
        groq_configured=settings.is_groq_configured(),
        gemini_configured=settings.is_gemini_configured(),
    )


@app.get("/")
async def root():
    return {"message": "Challenge Evaluator API", "docs": "/docs", "health": "/health"}


@app.get("/admin/replay-status", dependencies=[Depends(verify_internal_token)])
async def replay_status():
    count = await asyncio.to_thread(get_failed_callbacks_count)
    path = get_failed_path()
    return {
        "failed_callbacks": count,
        "path": str(path),
        "replay_interval": settings.callback_replay_interval_seconds,
    }


@app.post("/admin/replay-failed-callbacks", dependencies=[Depends(verify_internal_token)])
async def replay_failed():
    result = await asyncio.to_thread(replay_failed_callbacks)
    return result.to_dict()


# --- Background Task Decomposition ---
def background_evaluation_task(
    submission_id: str,
    github_repo_url: str,
    challenge_text: str,
    callback_url: str,
    callback_token: str,
):
    """Backward compatible wrapper using EvaluationTask value object."""
    task = EvaluationTask(
        submission_id=submission_id,
        github_repo_url=github_repo_url,
        challenge_text=challenge_text,
        callback_url=callback_url,
        callback_token=callback_token,
    )
    _execute_background_evaluation(task)


def _execute_background_evaluation(task: EvaluationTask) -> None:
    """Orchestrates evaluation - single level of abstraction."""
    logger.info(f"[Background] Starting evaluation for submission {task.submission_id}, repo {task.github_repo_url}")

    try:
        result, metadata = _clone_and_evaluate(task)
        _send_success_callback(task, result, metadata)
    except Exception as evaluation_error:
        logger.exception(f"[Background] Evaluation failed for {task.submission_id}: {evaluation_error}")
        _send_failure_callback(task, evaluation_error)


def _clone_and_evaluate(task: EvaluationTask):
    with cloned_repo(task.github_repo_url) as repo_path:
        logger.info(f"[Background] Repo cloned to {repo_path}")
        result, metadata = evaluate_repository(repo_path, task.challenge_text)
        logger.info(
            f"[Background] Evaluation completed for {task.submission_id}: "
            f"approved={result.get('approved', False)}, provider={metadata.get('llm_provider_used')}"
        )
        return result, metadata


def _send_success_callback(task: EvaluationTask, result: dict, metadata: dict) -> None:
    raw_output = str(result.get("raw", ""))[:RAW_OUTPUT_TRUNCATION_LENGTH]
    callback = EvaluationCallback(
        submission_id=task.submission_id,
        approved=bool(result.get("approved", False)),
        summary=str(result.get("summary", "Evaluation completed")),
        improvements=result.get("improvements", []),
        reasoning=result.get("reasoning"),
        raw_output=raw_output,
    )
    success = send_evaluation_callback(task.callback_url, task.callback_token, callback)
    if not success:
        logger.error(f"[Background] Callback failed for {task.submission_id} after retries")
    else:
        logger.info(f"[Background] Callback succeeded for {task.submission_id}")


def _send_failure_callback(task: EvaluationTask, error: Exception) -> None:
    # failed=True marks infrastructure/process errors as FAILED (not REJECTED).
    failure_callback = EvaluationCallback(
        submission_id=task.submission_id,
        approved=False,
        summary=f"Evaluation failed: {str(error)[:ERROR_SUMMARY_TRUNCATION_LENGTH]}",
        improvements=[
            "Check repository URL is valid and public",
            "Ensure repo is not too large",
            "Contact admin if issue persists",
        ],
        reasoning=str(error),
        raw_output=str(error)[:ERROR_REASONING_TRUNCATION_LENGTH],
        failed=True,
    )
    try:
        send_evaluation_callback(task.callback_url, task.callback_token, failure_callback)
    except Exception as callback_error:
        logger.error(f"[Background] Failed to send failure callback for {task.submission_id}: {callback_error}")


# --- API Endpoint with extracted validations ---
@app.post("/evaluate", status_code=202, dependencies=[Depends(verify_internal_token)])
async def evaluate(request: EvaluateRequest, background_tasks: BackgroundTasks):
    """
    Receives evaluation request from Symfony.
    Returns 202 immediately and processes in background.
    """
    logger.info(f"Received evaluation request: submissionId={request.submission_id}, repo={request.github_repo_url}")

    _validate_github_url_or_warn(request.github_repo_url)
    _validate_challenge_text(request.challenge_text)

    background_tasks.add_task(
        _execute_background_evaluation,
        EvaluationTask(
            submission_id=request.submission_id,
            github_repo_url=request.github_repo_url,
            challenge_text=request.challenge_text,
            callback_url=request.callback_url,
            callback_token=request.callback_token,
        ),
    )

    return {
        "status": "accepted",
        "submissionId": request.submission_id,
        "message": "Evaluation started in background, result will be sent via callback",
    }


def _validate_github_url_or_warn(github_url: str) -> None:
    if not validate_github_url(github_url):
        logger.warning(f"Invalid GitHub URL format: {github_url}")
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format")


def _validate_challenge_text(challenge_text: str) -> None:
    if not challenge_text or len(challenge_text.strip()) < MIN_CHALLENGE_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"challengeText too short, minimum {MIN_CHALLENGE_TEXT_LENGTH} chars")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
