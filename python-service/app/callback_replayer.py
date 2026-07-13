import asyncio
import json
import logging
import pathlib
from dataclasses import dataclass
from typing import List

from .config import settings
from .symfony_client import _post_with_retry

logger = logging.getLogger(__name__)


# --- Value Objects ---


@dataclass(frozen=True)
class FailedCallbackEntry:
    url: str
    payload: dict
    error: str | None = None

    @property
    def submission_id(self) -> str:
        return self.payload.get("submissionId", "unknown")


@dataclass(frozen=True)
class ReplayResult:
    total: int
    succeeded: int
    still_failing: int

    def __iter__(self):
        # Backward compatible tuple unpacking: total, ok, remaining = result
        return iter((self.total, self.succeeded, self.still_failing))

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "replayed": self.succeeded,
            "still_failing": self.still_failing,
        }


# --- Path resolution - single source of truth from config ---


def get_failed_path() -> pathlib.Path:
    return pathlib.Path(settings.failed_callbacks_path)


def get_failed_callbacks_count() -> int:
    path = get_failed_path()
    if not path.exists():
        return 0
    try:
        return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
    except Exception as read_error:
        logger.error(f"Failed to count DLQ file {path}: {read_error}")
        return -1


# --- Parsing ---


def _safe_parse_line(line: str, line_no: int) -> FailedCallbackEntry | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as decode_error:
        logger.warning(f"Skipping invalid JSON DLQ line {line_no}: {decode_error}")
        return None

    if not isinstance(data, dict) or "url" not in data or "payload" not in data:
        logger.warning(f"Skipping malformed DLQ line {line_no}: missing url/payload")
        return None

    return FailedCallbackEntry(
        url=data.get("url", ""),
        payload=data.get("payload", {}),
        error=data.get("error"),
    )


def _read_entries(path: pathlib.Path) -> List[FailedCallbackEntry]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as read_error:
        logger.error(f"Failed to read DLQ file {path}: {read_error}")
        return []

    entries: List[FailedCallbackEntry] = []
    for idx, raw in enumerate(raw_lines, start=1):
        entry = _safe_parse_line(raw, idx)
        if entry is not None:
            entries.append(entry)
    return entries


# --- Replay attempt - single responsibility ---


def _resolve_token(entry: FailedCallbackEntry) -> str:
    return (
        entry.payload.get("callbackToken")
        or entry.payload.get("token")
        or settings.callback_token
    )


def _attempt_single_replay(entry: FailedCallbackEntry) -> bool:
    token = _resolve_token(entry)
    try:
        _post_with_retry(entry.url, entry.payload, token)
        logger.info(f"DLQ replay succeeded for submissionId={entry.submission_id}")
        return True
    except Exception as replay_error:
        logger.warning(
            f"DLQ replay still failing for {entry.submission_id}: {replay_error}"
        )
        return False


# --- Atomic write ---


def _write_remaining(path: pathlib.Path, remaining: List[FailedCallbackEntry]) -> None:
    try:
        if not remaining:
            path.unlink(missing_ok=True)
            logger.info("DLQ file cleared after successful replay")
            return

        tmp_path = path.with_name(path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file_handle:
            for entry in remaining:
                file_handle.write(
                    json.dumps(
                        {
                            "url": entry.url,
                            "payload": entry.payload,
                            "error": entry.error,
                        }
                    )
                    + "\n"
                )
        tmp_path.replace(path)
    except Exception as write_error:
        logger.error(f"Failed to rewrite DLQ file {path}: {write_error}")


# --- Public API - orchestrator with single level of abstraction ---


def replay_failed_callbacks() -> ReplayResult:
    path = get_failed_path()
    if not path.exists() or path.stat().st_size == 0:
        return ReplayResult(total=0, succeeded=0, still_failing=0)

    entries = _read_entries(path)
    if not entries:
        # File contained only blank / malformed lines - clean it
        _write_remaining(path, [])
        return ReplayResult(total=0, succeeded=0, still_failing=0)

    succeeded = 0
    remaining: List[FailedCallbackEntry] = []

    for entry in entries:
        if _attempt_single_replay(entry):
            succeeded += 1
        else:
            remaining.append(entry)

    _write_remaining(path, remaining)

    total = len(entries)
    still_failing = len(remaining)
    if succeeded == total:
        logger.info(f"DLQ replay complete: {succeeded}/{total} recovered, file cleared")
    else:
        logger.info(
            f"DLQ replay: {succeeded}/{total} recovered, {still_failing} still failing"
        )

    return ReplayResult(total=total, succeeded=succeeded, still_failing=still_failing)


async def replay_loop(interval_seconds: int | None = None) -> None:
    interval = interval_seconds or settings.callback_replay_interval_seconds
    path = get_failed_path()
    logger.info(
        f"Starting callback replay loop every {interval}s (path={path})"
    )
    while True:
        try:
            await asyncio.to_thread(replay_failed_callbacks)
        except Exception as loop_error:
            logger.exception(f"Unexpected error in replay loop: {loop_error}")
        await asyncio.sleep(interval)
