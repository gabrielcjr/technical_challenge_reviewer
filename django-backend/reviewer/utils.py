import logging
import threading

import httpx
from django.conf import settings

from .models import Submission

logger = logging.getLogger(__name__)


def dispatch_evaluation(submission: Submission) -> None:
    """
    Dispatches evaluation request to the evaluator microservice.
    Runs asynchronously in a daemon thread so API responses return immediately.
    """
    submission.mark_as_processing()
    submission.append_processing_log("Dispatching to evaluator")
    submission.save()

    def _worker():
        payload = {
            "submissionId": str(submission.id),
            "githubRepoUrl": submission.github_repo_url,
            "challengeText": submission.challenge_snapshot,
            "callbackUrl": getattr(settings, "WEBHOOK_CALLBACK_URL", "http://nginx/api/internal/evaluation-result"),
            "callbackToken": getattr(settings, "CALLBACK_TOKEN", "default_secret_callback_token_123"),
        }
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": getattr(settings, "CALLBACK_TOKEN", "default_secret_callback_token_123"),
        }
        evaluator_url = (
            getattr(settings, "EVALUATOR_SERVICE_URL", "http://evaluator:8000").rstrip("/") + "/evaluate"
        )

        try:
            logger.info(f"Posting evaluation request to {evaluator_url} for submission {submission.id}")
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(evaluator_url, json=payload, headers=headers)
                if resp.status_code < 200 or resp.status_code > 299:
                    raise Exception(f"Evaluator responded with status {resp.status_code}")
            logger.info(f"Successfully dispatched evaluation for submission {submission.id}")
        except Exception as err:
            logger.error(f"Dispatch failed for submission {submission.id}: {err}")
            submission.mark_as_failed(f"Dispatch failed: {err}")
            submission.save()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
