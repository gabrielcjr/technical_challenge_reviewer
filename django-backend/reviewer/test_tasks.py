from unittest.mock import MagicMock, patch

from django.test import TestCase
from reviewer.models import Submission, SubmissionStatus
from reviewer.tasks import process_evaluation_task
from reviewer.utils import dispatch_evaluation


class CeleryTaskTestCase(TestCase):
    def setUp(self):
        self.submission = Submission.objects.create(
            user_name="Celery User",
            github_repo_url="https://github.com/user/celery-repo",
            challenge_snapshot="Snapshot",
            status=SubmissionStatus.PENDING,
        )

    @patch("reviewer.tasks.httpx.Client.post")
    def test_process_evaluation_task_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call the task synchronously
        process_evaluation_task(self.submission.id)

        mock_post.assert_called_once()
        self.assertTrue(mock_post.call_args[1]["json"]["submissionId"] == str(self.submission.id))

    @patch("reviewer.tasks.httpx.Client.post")
    def test_process_evaluation_task_failure_raises_exception(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        with self.assertRaises(Exception) as context:
            process_evaluation_task(self.submission.id)

        self.assertIn("Evaluator responded with status 500", str(context.exception))
        mock_post.assert_called_once()

    @patch("reviewer.tasks.process_evaluation_task.delay")
    def test_dispatch_evaluation_enqueues_task(self, mock_delay):
        dispatch_evaluation(self.submission)

        # Verify status updated
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, SubmissionStatus.PROCESSING)

        # Verify Celery delay was called
        mock_delay.assert_called_once_with(self.submission.id)
