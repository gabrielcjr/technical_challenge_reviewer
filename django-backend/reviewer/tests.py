import json

from django.conf import settings
from django.test import Client, TestCase
from reviewer.models import MAX_LOG_LENGTH, Submission, SubmissionStatus


class ReviewerApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.callback_token = getattr(settings, "CALLBACK_TOKEN", "default_secret_callback_token_123")

    def test_health_check(self):
        response = self.client.get("/api/internal/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "django")

    def test_challenge_creation_and_listing(self):
        # Create challenge
        payload = {
            "title": "Backend Challenge",
            "description": "Build a scalable REST API microservice with comprehensive tests.",
        }
        response = self.client.post(
            "/api/challenges",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["title"], "Backend Challenge")

        # List challenges
        response = self.client.get("/api/challenges")
        self.assertEqual(response.status_code, 200)
        challenges = response.json()
        self.assertEqual(len(challenges), 1)
        self.assertEqual(challenges[0]["title"], "Backend Challenge")

    def test_challenge_validation(self):
        # Short description
        payload = {"title": "Test", "description": "Too short"}
        response = self.client.post(
            "/api/challenges",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_submission_creation_and_retrieval(self):
        payload = {
            "userName": "Jane Developer",
            "githubRepoUrl": "https://github.com/example/sample-repo",
            "customChallengeText": "Implement an optimized key-value store in Python.",
        }
        response = self.client.post(
            "/api/submissions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        sub_id = data["id"]

        # Retrieve submission
        response = self.client.get(f"/api/submissions/{sub_id}")
        self.assertEqual(response.status_code, 200)
        sub_data = response.json()
        self.assertEqual(sub_data["userName"], "Jane Developer")
        self.assertEqual(sub_data["githubRepoUrl"], "https://github.com/example/sample-repo")

    def test_submission_invalid_github_url(self):
        payload = {
            "userName": "Jane Developer",
            "githubRepoUrl": "https://gitlab.com/example/sample-repo",
            "customChallengeText": "Implement an optimized key-value store in Python.",
        }
        response = self.client.post(
            "/api/submissions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_submission_retry_allowed_and_forbidden(self):
        sub_failed = Submission.objects.create(
            user_name="Retry Candidate",
            github_repo_url="https://github.com/user/retry-repo",
            challenge_snapshot="Sample prompt snapshot",
            status=SubmissionStatus.FAILED,
        )

        # Retry allowed on FAILED
        response = self.client.post(f"/api/submissions/{sub_failed.id}/retry")
        self.assertEqual(response.status_code, 200)
        sub_failed.refresh_from_db()
        self.assertIn(sub_failed.status, [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING])

        # Retry forbidden on finalized APPROVED
        sub_approved = Submission.objects.create(
            user_name="Approved Candidate",
            github_repo_url="https://github.com/user/approved-repo",
            challenge_snapshot="Sample prompt snapshot",
            status=SubmissionStatus.APPROVED,
            approved=True,
        )
        response = self.client.post(f"/api/submissions/{sub_approved.id}/retry")
        self.assertEqual(response.status_code, 400)

    def test_submission_not_found(self):
        response = self.client.get("/api/submissions/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)

    def test_log_truncation(self):
        sub = Submission.objects.create(
            user_name="Log Test",
            github_repo_url="https://github.com/user/log-repo",
            challenge_snapshot="Sample snapshot text",
        )
        for i in range(500):
            sub.append_processing_log(f"Iteration message {i} with additional context string")

        self.assertLessEqual(len(sub.processing_logs), MAX_LOG_LENGTH)

    def test_internal_callback_authentication_and_update(self):
        sub = Submission.objects.create(
            user_name="John Doe",
            github_repo_url="https://github.com/user/repo",
            challenge_snapshot="Instructions",
            status=SubmissionStatus.PROCESSING,
        )

        callback_payload = {
            "submissionId": str(sub.id),
            "approved": True,
            "summary": "Great implementation!",
            "improvements": ["Add more inline comments"],
            "reasoning": "Solid architecture.",
        }

        # Unauthorized attempt without token
        response = self.client.post(
            "/api/internal/evaluation-result",
            data=json.dumps(callback_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

        # Authorized attempt
        response = self.client.post(
            "/api/internal/evaluation-result",
            data=json.dumps(callback_payload),
            content_type="application/json",
            headers={"X-Internal-Token": self.callback_token},
        )
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertEqual(res_data["submissionStatus"], "approved")

        sub.refresh_from_db()
        self.assertEqual(sub.status, SubmissionStatus.APPROVED)
        self.assertTrue(sub.approved)
