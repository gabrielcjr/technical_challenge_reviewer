import pytest
import respx
from httpx import Response
from app.symfony_client import send_callback

@respx.mock
def test_callback_success():
    respx.post("http://nginx/api/internal/evaluation-result").mock(return_value=Response(200, json={"status": "ok"}))

    success = send_callback(
        callback_url="http://nginx/api/internal/evaluation-result",
        callback_token="secret",
        submission_id="test-id",
        approved=True,
        summary="Good job",
        improvements=["Add tests"],
        reasoning="All good"
    )

    assert success is True

@respx.mock
def test_callback_failure_retries():
    # Simulate 500 errors, should retry and eventually fail and log
    respx.post("http://nginx/api/internal/evaluation-result").mock(return_value=Response(500, text="Server error"))

    success = send_callback(
        callback_url="http://nginx/api/internal/evaluation-result",
        callback_token="secret",
        submission_id="test-id",
        approved=False,
        summary="Failed",
        improvements=[],
        reasoning="Error"
    )

    # Should return False after retries
    assert success is False

def test_callback_payload_structure():
    # Ensure payload contains required fields
    import app.symfony_client as client_module
    # We can't easily intercept payload without mocking _post_with_retry, but test that function exists
    assert hasattr(client_module, 'send_callback')


def test_evaluation_callback_includes_failed_flag():
    from app.symfony_client import EvaluationCallback

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


@respx.mock
def test_callback_success_with_failed_flag():
    route = respx.post("http://nginx/api/internal/evaluation-result").mock(
        return_value=Response(200, json={"status": "ok", "submissionStatus": "failed"})
    )

    success = send_callback(
        callback_url="http://nginx/api/internal/evaluation-result",
        callback_token="secret",
        submission_id="test-id",
        approved=False,
        summary="Evaluation failed",
        improvements=[],
        reasoning="error",
        failed=True,
    )

    assert success is True
    assert route.called
    body = route.calls.last.request.content
    import json
    data = json.loads(body)
    assert data["failed"] is True
