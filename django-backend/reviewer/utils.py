import logging

from .models import Submission

logger = logging.getLogger(__name__)


def dispatch_evaluation(submission: Submission) -> None:
    """
    Dispatches evaluation request to the evaluator microservice.
    Enqueues a Celery task so API responses return immediately.
    """
    submission.mark_as_processing()
    submission.append_processing_log("Dispatching to evaluator")
    submission.save()

    from .tasks import process_evaluation_task

    process_evaluation_task.delay(submission.id)
