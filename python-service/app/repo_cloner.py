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

@contextmanager
def cloned_repo(repo_url: str, base_dir: str = None) -> Generator[Path, None, None]:
    """
    Clone a git repository to a temporary directory and yield the path.
    Cleans up after.
    """
    if base_dir is None:
        base_dir = settings.clone_base_dir

    os.makedirs(base_dir, exist_ok=True)

    unique_id = str(uuid.uuid4())[:8]
    # Sanitize repo url to folder name
    folder_name = f"repo_{unique_id}"
    dest_path = Path(base_dir) / folder_name

    try:
        logger.info(f"Cloning {repo_url} to {dest_path}")

        # Basic validation
        if not repo_url.startswith("https://") and not repo_url.startswith("http://") and not repo_url.startswith("git@"):
            raise ValueError(f"Invalid repo URL: {repo_url}")

        if "github.com" not in repo_url:
            logger.warning(f"Repo URL does not contain github.com: {repo_url}")

        # Use git clone --depth 1 for shallow clone
        cmd = ["git", "clone", "--depth", "1", repo_url, str(dest_path)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.clone_timeout_seconds,
        )

        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

        if not dest_path.exists():
            raise RuntimeError("Clone destination does not exist after clone")

        logger.info(f"Successfully cloned to {dest_path}")
        yield dest_path

    finally:
        # Cleanup
        if dest_path.exists():
            try:
                shutil.rmtree(dest_path, ignore_errors=True)
                logger.info(f"Cleaned up {dest_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {dest_path}: {e}")

def validate_github_url(url: str) -> bool:
    """Basic validation for GitHub URL"""
    if not url:
        return False
    if "github.com" not in url:
        return False
    if not (url.startswith("https://") or url.startswith("http://")):
        return False
    return True
