import os
from pathlib import Path
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# --- Constants with intention revealing names ---
IGNORED_DIRECTORIES = {
    ".git", "node_modules", "vendor", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".idea", ".vscode", "storage", "var", "tmp"
}

IGNORED_FILE_NAMES = {
    "package-lock.json", "yarn.lock", "composer.lock", "poetry.lock",
    ".DS_Store", "thumbs.db"
}

RELEVANT_EXTENSIONS = {
    ".md", ".txt", ".py", ".php", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".html", ".css",
    ".java", ".go", ".rs", ".rb", ".sh", ".sql", ".toml", ".ini",
}

RELEVANT_EXACT_NAMES = {
    ".env.example", "Dockerfile", ".gitignore", "Makefile", "makefile",
    "composer.json", "package.json", "requirements.txt", "pyproject.toml",
    "docker-compose.yml", "main.py", "app.py", "index.php",
}

PRIORITY_FILE_NAMES_LOWERCASE = {
    "readme.md", "readme.txt", "readme",
}

MAX_FILE_SIZE_BYTES = 100 * 1024  # 100KB
MAX_CHARS_PER_FILE = 2000
TREE_DISPLAY_LIMIT = 200
FILE_LIST_DISPLAY_LIMIT = 100
MIN_FILES_GUARANTEE = 5
SMALL_REPO_THRESHOLD = 30
TRUNCATION_MARKER = "\n...[truncated]..."


# Backward compatible aliases for tests and legacy code
def should_ignore(path: Path) -> bool:  # pragma: no cover - legacy wrapper
    return should_ignore_path(path)


def is_relevant_file(path: Path) -> bool:  # pragma: no cover - legacy wrapper
    return is_relevant_for_evaluation(path)


def should_ignore_path(relative_path: Path) -> bool:
    """Check if a relative path should be ignored based on directory and file rules."""
    if _is_in_ignored_directory(relative_path):
        return True
    if _is_hidden_path_except_allowed(relative_path):
        return True
    if relative_path.name in IGNORED_FILE_NAMES:
        return True
    return False


def _is_in_ignored_directory(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def _is_hidden_path_except_allowed(path: Path) -> bool:
    allowed_hidden = {".env.example"}
    return any(
        part.startswith(".") and part not in allowed_hidden
        for part in path.parts
    )


def is_relevant_for_evaluation(file_path: Path) -> bool:
    """Determine if file content is relevant for AI evaluation."""
    if file_path.is_dir():
        return False
    if file_path.name in IGNORED_FILE_NAMES:
        return False
    if file_path.suffix.lower() in RELEVANT_EXTENSIONS:
        return True
    if file_path.name in RELEVANT_EXACT_NAMES:
        return True
    if file_path.name.lower() in PRIORITY_FILE_NAMES_LOWERCASE:
        return True
    # Files without extension that are typically important
    if file_path.name in {"Makefile", "Dockerfile"}:
        return True
    return False


def _filter_directories_in_place(directories: List[str]) -> None:
    """Modify dirs list in-place to skip ignored directories (os.walk contract)."""
    directories[:] = [
        d for d in directories
        if d not in IGNORED_DIRECTORIES and not d.startswith(".")
    ]


def _format_tree_entry(relative_root: str, name: str, is_directory: bool) -> str:
    """Format a single tree entry with proper indentation."""
    level = relative_root.count(os.sep) if relative_root else 0
    indent = "  " * level
    if is_directory and relative_root:
        return f"{indent}{name}/"
    if not relative_root and is_directory:
        return "./"
    return f"{indent}  {name}"


def _read_file_safely(file_path: Path) -> str | None:
    """Read file content with UTF-8, return None on failure or too large."""
    try:
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return None
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if len(content) > MAX_CHARS_PER_FILE:
            content = content[:MAX_CHARS_PER_FILE] + TRUNCATION_MARKER
        return content
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return None


def collect_files(repo_path: Path, max_files: int = 100, max_total_chars: int = 25000) -> Tuple[str, str, Dict]:
    """
    Walks repo and collects file tree, contents, and metadata.

    Returns:
        Tuple of (tree_string, concatenated_contents, metadata_dict)
    """
    collector = _FileCollector(repo_path, max_files, max_total_chars)
    return collector.collect()


class _FileCollector:
    """Encapsulates file collection state - SRP and small methods."""

    def __init__(self, repo_path: Path, max_files: int, max_total_chars: int):
        self.repo_path = repo_path
        self.max_files = max_files
        self.max_total_chars = max_total_chars
        self.tree_lines: List[str] = []
        self.content_entries: List[str] = []
        self.all_files: List[Path] = []
        self.total_chars = 0
        self.collected_count = 0

    def collect(self) -> Tuple[str, str, Dict]:
        self._walk_repository()
        tree_str = self._build_tree_string()
        contents_str = self._build_contents_string()
        metadata = self._build_metadata()
        logger.info(
            f"Collected {self.collected_count} files out of {len(self.all_files)} total, "
            f"{self.total_chars} chars"
        )
        return tree_str, contents_str, metadata

    def _walk_repository(self) -> None:
        for root, dirs, files in os.walk(self.repo_path):
            _filter_directories_in_place(dirs)
            relative_root = self._get_relative_root(root)
            self._add_directory_to_tree(relative_root, root)
            self._process_files_in_directory(root, relative_root, files)

    def _get_relative_root(self, absolute_root: str) -> str:
        rel = os.path.relpath(absolute_root, self.repo_path)
        return "" if rel == "." else rel

    def _add_directory_to_tree(self, rel_root: str, abs_root: str) -> None:
        if rel_root:
            entry = _format_tree_entry(rel_root, os.path.basename(abs_root), True)
        else:
            entry = _format_tree_entry("", "", True)
        self.tree_lines.append(entry)

    def _process_files_in_directory(self, root: str, rel_root: str, files: List[str]) -> None:
        for file_name in files:
            file_path = Path(root) / file_name
            rel_path = file_path.relative_to(self.repo_path)

            if should_ignore_path(rel_path):
                continue

            self.all_files.append(rel_path)
            self.tree_lines.append(_format_tree_entry(rel_root, file_name, False))

            if not self._should_collect_content(file_path):
                continue
            self._collect_single_file(file_path, rel_path)

    def _should_collect_content(self, file_path: Path) -> bool:
        if self.collected_count >= self.max_files:
            return False
        if not is_relevant_for_evaluation(file_path):
            # For small repos, include non-relevant files too
            return len(self.all_files) <= SMALL_REPO_THRESHOLD
        return True

    def _collect_single_file(self, file_path: Path, rel_path: Path) -> None:
        file_size = file_path.stat().st_size if file_path.exists() else 0
        if file_size > MAX_FILE_SIZE_BYTES:
            self.content_entries.append(
                f"\n--- File: {rel_path} (skipped, too large: {file_size} bytes) ---\n"
            )
            return

        content = _read_file_safely(file_path)
        if content is None and file_size > MAX_FILE_SIZE_BYTES:
            return  # Already logged as too large
        if content is None:
            return  # Failed to read

        entry = f"\n--- File: {rel_path} ---\n{content}\n"
        entry_len = len(entry)

        if self.total_chars + entry_len > self.max_total_chars:
            if self.collected_count < MIN_FILES_GUARANTEE:
                # Guarantee minimum files even if over limit
                pass
            else:
                return

        self.content_entries.append(entry)
        self.total_chars += entry_len
        self.collected_count += 1

    def _build_tree_string(self) -> str:
        tree = "\n".join(self.tree_lines[:TREE_DISPLAY_LIMIT])
        if len(self.tree_lines) > TREE_DISPLAY_LIMIT:
            remaining = len(self.tree_lines) - TREE_DISPLAY_LIMIT
            tree += f"\n... and {remaining} more files ..."
        return tree

    def _build_contents_string(self) -> str:
        contents = "".join(self.content_entries)
        if self.total_chars >= self.max_total_chars:
            contents += (
                f"\n\n[Truncated after {self.max_total_chars} chars for LLM context limit. "
                f"Total files collected: {self.collected_count}]"
            )
        return contents

    def _build_metadata(self) -> Dict:
        return {
            "total_files": len(self.all_files),
            "collected_files": self.collected_count,
            "total_chars": self.total_chars,
            "file_list": [str(p) for p in self.all_files[:FILE_LIST_DISPLAY_LIMIT]],
        }
