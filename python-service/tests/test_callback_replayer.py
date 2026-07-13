import json
import pathlib
from unittest.mock import patch, MagicMock

from app.callback_replayer import (
    ReplayResult,
    get_failed_callbacks_count,
    get_failed_path,
    replay_failed_callbacks,
)


def test_replayer_empty_no_file():
    with patch("app.callback_replayer.get_failed_path") as mock_path:
        mock_path.return_value = pathlib.Path("/nonexistent.jsonl")
        result = replay_failed_callbacks()
        assert isinstance(result, ReplayResult)
        assert result.total == 0 and result.succeeded == 0 and result.still_failing == 0


def test_replayer_tuple_unpacking_backward_compat():
    with patch("app.callback_replayer.get_failed_path") as mock_path:
        mock_path.return_value = pathlib.Path("/nonexistent.jsonl")
        total, ok, remain = replay_failed_callbacks()
        assert (total, ok, remain) == (0, 0, 0)


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
    with patch("app.callback_replayer.get_failed_path", return_value=dlq), patch(
        "app.callback_replayer._post_with_retry", return_value=MagicMock()
    ) as mock_post:
        result = replay_failed_callbacks()
        assert result.total == 1 and result.succeeded == 1 and result.still_failing == 0
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
    with patch("app.callback_replayer.get_failed_path", return_value=dlq), patch(
        "app.callback_replayer._post_with_retry", side_effect=Exception("still down")
    ):
        result = replay_failed_callbacks()
        assert result.total == 1 and result.succeeded == 0 and result.still_failing == 1
        assert dlq.exists()
        assert "fail-123" in dlq.read_text()


def test_get_failed_callbacks_count(tmp_path):
    dlq = tmp_path / "failed.jsonl"
    dlq.write_text('{"a":1}\n\n  \n{"b":2}\n')
    with patch("app.callback_replayer.get_failed_path", return_value=dlq):
        count = get_failed_callbacks_count()
        assert count == 2


def test_get_failed_path_uses_config():
    path = get_failed_path()
    assert isinstance(path, pathlib.Path)
    # Should be Path from settings
    assert path.name == "failed_callbacks.jsonl"
