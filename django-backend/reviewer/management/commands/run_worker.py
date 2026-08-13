import logging
import time

from django.core.management.base import BaseCommand
from reviewer.models import Submission, SubmissionStatus
from reviewer.utils import dispatch_evaluation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs background queue worker consuming pending evaluations."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Django evaluation worker..."))
        while True:
            try:
                pending_submissions = Submission.objects.filter(status=SubmissionStatus.PENDING)
                for submission in pending_submissions:
                    logger.info(f"Worker picked up pending submission {submission.id}")
                    dispatch_evaluation(submission)
            except Exception as err:
                logger.error(f"Worker iteration error: {err}")
            time.sleep(5)
