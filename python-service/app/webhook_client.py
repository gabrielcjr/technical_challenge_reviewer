import logging
from dataclasses import dataclass

import httpx

from .celery_app import celery_app
from .config import settings
from .models import CallbackPayload

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class EvaluationCallback:
    """Value object representing callback data."""

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
        return payload.to_webhook_dict()


def _resolve_callback_url(provided_url: str) -> str:
    return provided_url or getattr(settings, "webhook_callback_url", "http://nginx/api/internal/evaluation-result")


def _resolve_callback_token(provided_token: str) -> str:
    return provided_token or settings.callback_token


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.RequestError, httpx.HTTPStatusError),
    retry_backoff=True,
    retry_backoff_max=3600,
    max_retries=10,
)
def send_evaluation_callback_task(self, url: str, token: str, payload: dict):
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": token,
    }

    logger.info(f"Posting callback to {url} with payload submissionId={payload.get('submissionId')}")

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(
                f"Server error {response.status_code}", request=response.request, response=response
            )
        response.raise_for_status()


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
    Send evaluation result back to Orchestrator by enqueuing a Celery task.
    Returns True immediately.
    """
    resolved_url = _resolve_callback_url(callback_url)
    resolved_token = _resolve_callback_token(callback_token)
    payload = evaluation_callback.to_payload(resolved_token)

    send_evaluation_callback_task.delay(resolved_url, resolved_token, payload)
    logger.info(f"Enqueued callback task for submissionId={payload.get('submissionId')}")
    return True
