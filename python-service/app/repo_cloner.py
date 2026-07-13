import os
import shutil
import subprocess
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
import logging

logger = logging.getLogger(__name__)

from .config import settings

# Constants
GITHUB_DOMAIN = "github.com"
ALLOWED_URL_SCHEMES = ("https://", "http://", "git@")
CLONE_DEPTH = "1"
TEMP_FOLDER_PREFIX = "repo_"
UUID_SHORT_LENGTH = 8
SUPPORTED_GIT_HOST = GITHUB_DOMAIN


class RepositoryCloneError(RuntimeError):
    """Domain exception for clone failures - clean error handling."""


def validate_github_url(url: str) -> bool:
    """Validate that URL looks like a GitHub HTTPS URL."""
    if not url:
        return False
    if SUPPORTED_GIT_HOST not in url:
        return False
    if not url.startswith(("https://", "http://")):
        return False
    return True


def _validate_url_for_clone(repo_url: str) -> None:
    """Raise ValueError if URL format is invalid for git clone."""
    if not repo_url.startswith(ALLOWED_URL_SCHEMES):
        raise ValueError(f"Invalid repo URL: {repo_url} must start with {ALLOWED_URL_SCHEMES}")
    if SUPPORTED_GIT_HOST not in repo_url:
        logger.warning(f"Repo URL does not contain {SUPPORTED_GIT_HOST}: {repo_url}")


def _prepare_base_directory(base_dir: str) -> Path:
    base_path = Path(base_dir)
    os.makedirs(base_path, exist_ok=True)
    return base_path


def _generate_destination_path(base_path: Path) -> Path:
    unique_suffix = str(uuid.uuid4())[:UUID_SHORT_LENGTH]
    folder_name = f"{TEMP_FOLDER_PREFIX}{unique_suffix}"
    return base_path / folder_name


def _execute_git_clone(repo_url: str, dest_path: Path) -> None:
    clone_command = ["git", "clone", "--depth", CLONE_DEPTH, repo_url, str(dest_path)]
    result = subprocess.run(
        clone_command,
        capture_output=True,
        text=True,
        timeout=settings.clone_timeout_seconds,
    )
    if result.returncode != 0:
        logger.error(f"Git clone failed: {result.stderr}")
        raise RepositoryCloneError(f"Failed to clone repository: {result.stderr}")
    if not dest_path.exists():
        raise RepositoryCloneError("Clone destination does not exist after clone")


def _cleanup_directory(path: Path) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path, ignore_errors=False)
        logger.info(f"Cleaned up {path}")
    except Exception as cleanup_error:
        logger.warning(f"Failed to cleanup {path}: {cleanup_error}")


@contextmanager
def cloned_repo(repo_url: str, base_dir: str | None = None) -> Generator[Path, None, None]:
    """
    Clone a git repository to a temporary directory and yield the path.
    Automatically cleans up afterward.
    """
    resolved_base_dir = base_dir or settings.clone_base_dir
    base_path = _prepare_base_directory(resolved_base_dir)
    destination = _generate_destination_path(base_path)

    try:
        _validate_url_for_clone(repo_url)
        logger.info(f"Cloning {repo_url} to {destination}")
        _execute_git_clone(repo_url, destination)
        logger.info(f"Successfully cloned to {destination}")
        yield destination
    finally:
        _cleanup_directory(destination)
