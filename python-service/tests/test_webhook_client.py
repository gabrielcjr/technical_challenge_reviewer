from unittest.mock import patch

import pytest
import respx
from app.webhook_client import (
    EvaluationCallback,
    send_callback,
    send_evaluation_callback_task,
)
from httpx import HTTPStatusError, Response


def test_callback_enqueues_task():
    """Test that send_callback enqueues a Celery task instead of sending directly."""
    with patch("app.webhook_client.send_evaluation_callback_task.delay") as mock_delay:
        success = send_callback(
            callback_url="http://test/api/result",
            callback_token="secret",
            submission_id="test-id",
            approved=True,
            summary="Good job",
            improvements=["Add tests"],
            reasoning="All good",
        )

        assert success is True
        mock_delay.assert_called_once()
        args, _ = mock_delay.call_args
        assert args[0] == "http://test/api/result"
        assert args[1] == "secret"
        assert args[2]["submissionId"] == "test-id"
        assert args[2]["approved"] is True


@respx.mock
def test_send_evaluation_callback_task_success():
    """Test that the Celery task successfully sends the HTTP POST request."""
    route = respx.post("http://test/api/result").mock(return_value=Response(200, json={"status": "ok"}))

    payload = {"submissionId": "test-id", "approved": True}
    send_evaluation_callback_task("http://test/api/result", "secret", payload)

    assert route.called
    assert route.calls.last.request.headers["X-Internal-Token"] == "secret"


@respx.mock
def test_send_evaluation_callback_task_failure_raises():
    """Test that the Celery task raises an exception on HTTP error to trigger retries."""
    respx.post("http://test/api/result").mock(return_value=Response(500, text="Server error"))

    payload = {"submissionId": "test-id", "approved": False}
    with pytest.raises(HTTPStatusError):
        send_evaluation_callback_task("http://test/api/result", "secret", payload)


def test_evaluation_callback_includes_failed_flag():
    """Ensure the callback payload formats correctly."""
    callback = EvaluationCallback(
        submission_id="sub-1",
        approved=False,
        summary="Clone failed",
        improvements=["Check URL"],
        reasoning="git error",
        failed=True,
    )
    payload = callback.to_payload("token")
    assert payload["failed"] is True
    assert payload["submissionId"] == "sub-1"
    assert payload["approved"] is False
    assert payload["callbackToken"] == "token"
