import logging
from dataclasses import dataclass
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from .config import settings, SENTINEL_TEST_TOKENS
from .models import EvaluateRequest, HealthResponse
from .repo_cloner import cloned_repo, validate_github_url
from .evaluator import evaluate_repository
from .symfony_client import EvaluationCallback, send_evaluation_callback

# --- Constants ---
MIN_CHALLENGE_TEXT_LENGTH = 10
RAW_OUTPUT_TRUNCATION_LENGTH = 2000
ERROR_SUMMARY_TRUNCATION_LENGTH = 200
ERROR_REASONING_TRUNCATION_LENGTH = 1000
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


_configure_logging()

app = FastAPI(
    title="Challenge Evaluator",
    description="Python microservice that evaluates GitHub repos using LangChain + Grok (xAI)/Gemini",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
        grok_configured=settings.is_grok_configured(),
        gemini_configured=settings.is_gemini_configured(),
        xai_configured=settings.is_grok_configured(),
    )


@app.get("/")
async def root():
    return {"message": "Challenge Evaluator API", "docs": "/docs", "health": "/health"}


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
            f"approved={result['approved']}, provider={metadata.get('llm_provider_used')}"
        )
        return result, metadata


def _send_success_callback(task: EvaluationTask, result: dict, metadata: dict) -> None:
    raw_output = str(result.get("raw", ""))[:RAW_OUTPUT_TRUNCATION_LENGTH]
    callback = EvaluationCallback(
        submission_id=task.submission_id,
        approved=result["approved"],
        summary=result["summary"],
        improvements=result["improvements"],
        reasoning=result.get("reasoning"),
        raw_output=raw_output,
    )
    success = send_evaluation_callback(task.callback_url, task.callback_token, callback)
    if not success:
        logger.error(f"[Background] Callback failed for {task.submission_id} after retries")
    else:
        logger.info(f"[Background] Callback succeeded for {task.submission_id}")


def _send_failure_callback(task: EvaluationTask, error: Exception) -> None:
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
    )
    try:
        send_evaluation_callback(task.callback_url, task.callback_token, failure_callback)
    except Exception as callback_error:
        logger.error(f"[Background] Failed to send failure callback for {task.submission_id}: {callback_error}")


# --- API Endpoint with extracted validations ---
@app.post("/evaluate", status_code=202)
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
