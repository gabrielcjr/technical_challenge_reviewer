import json
import logging
import pathlib
import asyncio
from typing import Tuple

from .config import settings
from .symfony_client import FAILED_CALLBACKS_LOG_PATH, _post_with_retry

logger = logging.getLogger(__name__)

# Use config path so tests can override
REPLAY_BATCH_SIZE = 100


def _get_failed_path() -> pathlib.Path:
    return pathlib.Path(getattr(settings, "failed_callbacks_path", FAILED_CALLBACKS_LOG_PATH))


def _safe_parse_line(line: str, line_no: int) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        if not isinstance(data, dict) or "url" not in data or "payload" not in data:
            logger.warning(f"Skipping malformed DLQ line {line_no}: missing url/payload")
            return None
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Skipping invalid JSON DLQ line {line_no}: {e}")
        return None


def replay_failed_callbacks() -> Tuple[int, int, int]:
    """
    Attempt to replay callbacks stored in failed_callbacks.jsonl.
    Returns (total, succeeded, still_failed).
    Atomic rewrite: write remaining failures to temp file then rename.
    """
    path = _get_failed_path()
    if not path.exists() or path.stat().st_size == 0:
        return (0, 0, 0)

    total = 0
    succeeded = 0
    remaining = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        logger.error(f"Failed to read DLQ file {path}: {e}")
        return (0, 0, 0)

    for idx, raw in enumerate(lines, start=1):
        entry = _safe_parse_line(raw, idx)
        if entry is None:
            continue
        total += 1
        url = entry.get("url")
        payload = entry.get("payload", {})
        token = payload.get("callbackToken") or entry.get("token") or settings.callback_token

        try:
            _post_with_retry(url, payload, token)
            succeeded += 1
            logger.info(f"DLQ replay succeeded for submissionId={payload.get('submissionId')} (line {idx})")
        except Exception as replay_error:
            logger.warning(f"DLQ replay still failing for {payload.get('submissionId')} line {idx}: {replay_error}")
            remaining.append(entry)

    # Atomic rewrite
    try:
        if not remaining:
            path.unlink(missing_ok=True)
            logger.info(f"DLQ replay complete: {succeeded}/{total} recovered, file cleared")
        else:
            tmp = path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                for ent in remaining:
                    f.write(json.dumps(ent) + "\n")
            tmp.replace(path)
            logger.info(f"DLQ replay: {succeeded}/{total} recovered, {len(remaining)} still failing")
    except Exception as write_err:
        logger.error(f"Failed to rewrite DLQ file {path}: {write_err}")

    return (total, succeeded, len(remaining))


async def replay_loop(interval_seconds: int | None = None) -> None:
    """Infinite async loop — runs every interval_seconds, never raises."""
    interval = interval_seconds or getattr(settings, "callback_replay_interval_seconds", 60)
    logger.info(f"Starting callback replay loop every {interval}s (path={_get_failed_path()})")
    while True:
        try:
            await asyncio.to_thread(replay_failed_callbacks)
        except Exception as loop_err:
            logger.exception(f"Unexpected error in replay loop: {loop_err}")
        await asyncio.sleep(interval)


def replay_once_sync() -> Tuple[int, int, int]:
    """Sync helper for CLI / manual trigger."""
    return replay_failed_callbacks()
