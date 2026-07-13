import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type

from .config import settings
from .models import CallbackPayload

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
def _post_with_retry(url: str, payload: dict, token: str) -> httpx.Response:
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": token,
    }

    logger.info(f"Posting callback to {url} with payload submissionId={payload.get('submissionId')}")

    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, json=payload, headers=headers)
        # Raise for status to trigger retry on 5xx
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(f"Server error {response.status_code}", request=response.request, response=response)
        response.raise_for_status()
        return response

def send_callback(
    callback_url: str,
    callback_token: str,
    submission_id: str,
    approved: bool,
    summary: str,
    improvements: list,
    reasoning: str = None,
    raw_output: str = None,
) -> bool:
    """
    Send evaluation result back to Symfony with retry logic.
    Returns True on success, False on failure after retries.
    """
    payload = {
        "submissionId": submission_id,
        "approved": approved,
        "summary": summary,
        "improvements": improvements,
        "reasoning": reasoning,
        "rawOutput": raw_output,
        "callbackToken": callback_token,
    }

    # Use token from settings if callback_token is empty? Use provided
    token = callback_token or settings.callback_token

    # If callback_url is empty, use default from settings
    url = callback_url or settings.symfony_callback_url

    # Ensure URL uses internal docker network host if needed
    # If url contains localhost, replace with nginx for docker?
    # Keep as provided; in docker, Symfony app expects nginx host

    try:
        response = _post_with_retry(url, payload, token)
        logger.info(f"Callback successful: {response.status_code} {response.text[:200]}")
        return True
    except Exception as e:
        logger.error(f"Callback failed after retries: {e}")

        # Log to file for manual replay
        try:
            import json, pathlib
            log_file = pathlib.Path("/tmp/failed_callbacks.jsonl")
            with log_file.open("a") as f:
                f.write(json.dumps({"url": url, "payload": payload, "error": str(e)}) + "\n")
            logger.info(f"Logged failed callback to {log_file}")
        except Exception as log_e:
            logger.error(f"Failed to log failed callback: {log_e}")

        return False
