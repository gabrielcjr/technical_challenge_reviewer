import logging
import json
import pathlib
from dataclasses import dataclass
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type

from .config import settings
from .models import CallbackPayload

logger = logging.getLogger(__name__)

# Constants - intention revealing names
CALLBACK_RETRY_ATTEMPTS = 5
CALLBACK_RETRY_MIN_WAIT = 2
CALLBACK_RETRY_MAX_WAIT = 30
CALLBACK_RETRY_MULTIPLIER = 1
HTTP_TIMEOUT_SECONDS = 15.0
SERVER_ERROR_THRESHOLD = 500
FAILED_CALLBACKS_LOG_PATH = "/tmp/failed_callbacks.jsonl"
RESPONSE_PREVIEW_LENGTH = 200


@dataclass(frozen=True)
class EvaluationCallback:
    """Value object representing callback data - replaces 8-arg function."""

    submission_id: str
    approved: bool
    summary: str
    improvements: list
    reasoning: str | None = None
    raw_output: str | None = None
    failed: bool = False

    def to_payload(self, token: str) -> dict:
        payload = CallbackPayload(
            submissionId=self.submission_id,
            approved=self.approved,
            summary=self.summary,
            improvements=self.improvements,
            reasoning=self.reasoning,
            rawOutput=self.raw_output,
            callbackToken=token,
            failed=self.failed,
        )
        return payload.to_symfony_dict()


@retry(
    stop=stop_after_attempt(CALLBACK_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=CALLBACK_RETRY_MULTIPLIER, min=CALLBACK_RETRY_MIN_WAIT, max=CALLBACK_RETRY_MAX_WAIT),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
def _post_with_retry(url: str, payload: dict, token: str) -> httpx.Response:
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": token,
    }

    logger.info(f"Posting callback to {url} with payload submissionId={payload.get('submissionId')}")

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=headers)
        _raise_for_server_errors(response)
        response.raise_for_status()
        return response


def _raise_for_server_errors(response: httpx.Response) -> None:
    if response.status_code >= SERVER_ERROR_THRESHOLD:
        raise httpx.HTTPStatusError(
            f"Server error {response.status_code}", request=response.request, response=response
        )


def _resolve_callback_url(provided_url: str) -> str:
    return provided_url or settings.symfony_callback_url


def _resolve_callback_token(provided_token: str) -> str:
    return provided_token or settings.callback_token


def _get_failed_path() -> pathlib.Path:
    # Single source of truth: config, fallback to legacy constant only for safety
    try:
        return pathlib.Path(settings.failed_callbacks_path)
    except AttributeError:
        return pathlib.Path(FAILED_CALLBACKS_LOG_PATH)


def _ensure_parent_exists(path: pathlib.Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _log_failed_callback(url: str, payload: dict, error: Exception) -> None:
    try:
        log_file = _get_failed_path()
        _ensure_parent_exists(log_file)
        with log_file.open("a", encoding="utf-8") as file_handle:
            file_handle.write(
                json.dumps({"url": url, "payload": payload, "error": str(error)}) + "\n"
            )
        logger.info(f"Logged failed callback to {log_file}")
    except Exception as log_error:
        logger.error(f"Failed to log failed callback: {log_error}")


def send_callback(
    callback_url: str,
    callback_token: str,
    submission_id: str,
    approved: bool,
    summary: str,
    improvements: list,
    reasoning: str | None = None,
    raw_output: str | None = None,
    failed: bool = False,
) -> bool:
    """
    Backward compatible wrapper - delegates to send_evaluation_callback.
    """
    evaluation_callback = EvaluationCallback(
        submission_id=submission_id,
        approved=approved,
        summary=summary,
        improvements=improvements,
        reasoning=reasoning,
        raw_output=raw_output,
        failed=failed,
    )
    return send_evaluation_callback(callback_url, callback_token, evaluation_callback)


def send_evaluation_callback(
    callback_url: str,
    callback_token: str,
    evaluation_callback: EvaluationCallback,
) -> bool:
    """
    Send evaluation result back to Symfony with retry logic.
    Returns True on success, False on failure after retries.
    """
    resolved_url = _resolve_callback_url(callback_url)
    resolved_token = _resolve_callback_token(callback_token)
    payload = evaluation_callback.to_payload(resolved_token)

    try:
        response = _post_with_retry(resolved_url, payload, resolved_token)
        logger.info(f"Callback successful: {response.status_code} {response.text[:RESPONSE_PREVIEW_LENGTH]}")
        return True
    except Exception as callback_error:
        logger.error(f"Callback failed after retries: {callback_error}")
        _log_failed_callback(resolved_url, payload, callback_error)
        return False
