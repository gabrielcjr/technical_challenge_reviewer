import logging

import httpx
from celery import shared_task
from django.conf import settings

from .models import Submission

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=3600, max_retries=10)
def process_evaluation_task(self, submission_id: int):
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found.")
        return

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
    evaluator_url = getattr(settings, "EVALUATOR_SERVICE_URL", "http://evaluator:8000").rstrip("/") + "/evaluate"

    logger.info(f"Posting evaluation request to {evaluator_url} for submission {submission.id}")

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(evaluator_url, json=payload, headers=headers)
        if resp.status_code < 200 or resp.status_code > 299:
            raise Exception(f"Evaluator responded with status {resp.status_code}")

    logger.info(f"Successfully dispatched evaluation for submission {submission.id}")
