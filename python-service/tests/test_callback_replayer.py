import json
import pathlib
import tempfile
from unittest.mock import patch, MagicMock
from app.callback_replayer import replay_failed_callbacks


def test_replayer_empty_no_file():
    with patch("app.callback_replayer._get_failed_path") as mock_path:
        mock_path.return_value = pathlib.Path("/nonexistent.jsonl")
        total, ok, remain = replay_failed_callbacks()
        assert total == 0 and ok == 0 and remain == 0


def test_replayer_success_clears_file(tmp_path):
    dlq = tmp_path / "failed.jsonl"
    dlq.write_text(
        json.dumps(
            {
                "url": "http://example.com/callback",
                "payload": {"submissionId": "test-123", "callbackToken": "tok"},
                "error": "prev fail",
            }
        )
        + "\n"
    )
    with patch("app.callback_replayer._get_failed_path", return_value=dlq), patch(
        "app.callback_replayer._post_with_retry", return_value=MagicMock()
    ) as mock_post:
        total, ok, remain = replay_failed_callbacks()
        assert total == 1 and ok == 1 and remain == 0
        assert not dlq.exists(), "file should be deleted after success"
        mock_post.assert_called_once()


def test_replayer_keeps_failed(tmp_path):
    dlq = tmp_path / "failed.jsonl"
    dlq.write_text(
        json.dumps(
            {
                "url": "http://example.com/callback",
                "payload": {"submissionId": "fail-123", "callbackToken": "tok"},
                "error": "prev",
            }
        )
        + "\n"
    )
    with patch("app.callback_replayer._get_failed_path", return_value=dlq), patch(
        "app.callback_replayer._post_with_retry", side_effect=Exception("still down")
    ):
        total, ok, remain = replay_failed_callbacks()
        assert total == 1 and ok == 0 and remain == 1
        assert dlq.exists()
        content = dlq.read_text()
        assert "fail-123" in content
