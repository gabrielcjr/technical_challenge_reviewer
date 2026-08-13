import uuid

from django.db import models
from django.utils import timezone

MAX_LOG_LENGTH = 10000


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    FAILED = "failed", "Failed"


class Challenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "challenges"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or "Challenge"

    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "createdAt": self.created_at.isoformat(),
        }


class SafeJSONField(models.JSONField):
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return value
        try:
            return super().from_db_value(value, expression, connection)
        except TypeError:
            if isinstance(value, (dict, list)):
                return value
            raise


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_name = models.CharField(max_length=180)
    github_repo_url = models.CharField(max_length=500)
    challenge = models.ForeignKey(
        Challenge, on_delete=models.SET_NULL, null=True, blank=True, related_name="submissions"
    )
    challenge_snapshot = models.TextField()
    status = models.CharField(max_length=30, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING)
    evaluation_result = SafeJSONField(null=True, blank=True)
    approved = models.BooleanField(null=True, blank=True)
    processing_logs = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submissions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Submission {self.id} ({self.user_name})"

    def associate_with_challenge(self, challenge: Challenge | None) -> None:
        self.challenge = challenge
        if challenge is not None:
            self.challenge_snapshot = challenge.description

    def can_be_retried(self) -> bool:
        return self.status in [
            SubmissionStatus.PENDING,
            SubmissionStatus.PROCESSING,
            SubmissionStatus.FAILED,
        ]

    def is_final(self) -> bool:
        return self.status in [SubmissionStatus.APPROVED, SubmissionStatus.REJECTED]

    def mark_as_processing(self) -> None:
        if self.is_final():
            return
        self.status = SubmissionStatus.PROCESSING
        self.append_processing_log("Status changed to PROCESSING")

    def mark_as_failed(self, reason: str) -> None:
        self.status = SubmissionStatus.FAILED
        self.approved = False
        self.append_processing_log(f"Marked as FAILED: {reason}")

    def apply_evaluation_result(self, evaluation_result: dict, approved: bool, failed: bool = False) -> None:
        self.evaluation_result = evaluation_result
        self.approved = approved

        if failed:
            self.status = SubmissionStatus.FAILED
            self.approved = False
            self.append_processing_log(f"Evaluation failed (infrastructure/process error): status={self.status}")
            return

        self.status = SubmissionStatus.APPROVED if approved else SubmissionStatus.REJECTED
        self.append_processing_log(
            f"Evaluation applied: approved={'true' if approved else 'false'}, status={self.status}"
        )

    def append_processing_log(self, message: str) -> None:
        timestamp = timezone.now().isoformat()
        entry = f"[{timestamp}] {message}"

        if not self.processing_logs:
            self.processing_logs = entry
        else:
            self.processing_logs = f"{self.processing_logs}\n{entry}"

        if len(self.processing_logs) > MAX_LOG_LENGTH:
            self.processing_logs = self.processing_logs[-MAX_LOG_LENGTH:]

    def to_dict(self):
        return {
            "id": str(self.id),
            "userName": self.user_name,
            "githubRepoUrl": self.github_repo_url,
            "challengeId": str(self.challenge.id) if self.challenge else None,
            "challengeSnapshot": self.challenge_snapshot,
            "status": self.status,
            "approved": self.approved,
            "evaluation": self.evaluation_result,
            "processingLogs": self.processing_logs,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }
