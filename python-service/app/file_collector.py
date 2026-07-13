import os
from pathlib import Path
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

IGNORE_DIRS = {
    '.git', 'node_modules', 'vendor', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', '.nuxt', 'coverage', '.pytest_cache',
    '.idea', '.vscode', 'storage', 'var', 'tmp'
}

IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'composer.lock', 'poetry.lock',
    '.DS_Store', 'thumbs.db'
}

INCLUDE_EXTENSIONS = {
    '.md', '.txt', '.py', '.php', '.js', '.ts', '.jsx', '.tsx',
    '.json', '.yaml', '.yml', '.env.example', '.html', '.css',
    '.java', '.go', '.rs', '.rb', '.sh', '.sql', '.toml', '.ini',
    '.dockerfile', 'Dockerfile', '.gitignore'
}

# Priority files to always include if present
PRIORITY_FILES = [
    'README.md', 'readme.md', 'README.txt', 'README',
    'composer.json', 'package.json', 'requirements.txt', 'pyproject.toml',
    'Dockerfile', 'docker-compose.yml', 'main.py', 'app.py', 'index.php',
    'src', 'app', 'lib'
]

def should_ignore(path: Path) -> bool:
    """Check if path should be ignored"""
    # Ignore hidden files/dirs except .env.example
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
        if part.startswith('.') and part != '.env.example':
            # Allow .env.example but ignore other dotfiles at root
            if len(path.parts) <= 2:  # root level dotfile
                if part not in ['.env.example']:
                    # But allow README etc? Already handled
                    pass
    if path.name in IGNORE_FILES:
        return True
    return False

def is_relevant_file(path: Path) -> bool:
    """Check if file is relevant for evaluation"""
    if path.is_dir():
        return False
    if path.name in ['package-lock.json', 'yarn.lock']:
        return False
    # Check extension or exact name
    if path.suffix.lower() in INCLUDE_EXTENSIONS:
        return True
    if path.name in INCLUDE_EXTENSIONS:
        return True
    if path.name.lower() in [f.lower() for f in PRIORITY_FILES]:
        return True
    # Include files without extension but small? e.g., Makefile
    if path.name in ['Makefile', 'makefile', 'Dockerfile']:
        return True
    return False

def collect_files(repo_path: Path, max_files: int = 100, max_total_chars: int = 25000) -> Tuple[str, str, Dict]:
    """
    Walks repo and collects:
    - file tree string
    - concatenated file contents (truncated)
    - metadata dict
    """
    file_tree_lines = []
    file_contents = []
    total_chars = 0
    files_collected = 0
    file_list = []

    # Walk
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to skip ignored
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]

        # Compute relative root
        rel_root = os.path.relpath(root, repo_path)
        if rel_root == '.':
            rel_root = ''

        # Add to tree
        level = rel_root.count(os.sep) if rel_root else 0
        indent = '  ' * level
        if rel_root:
            file_tree_lines.append(f"{indent}{os.path.basename(root)}/")
        else:
            file_tree_lines.append(f"./")

        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(repo_path)

            if should_ignore(rel_path):
                continue

            file_list.append(rel_path)

            # Tree entry
            file_tree_lines.append(f"{indent}  {file}")

            # Content collection if relevant and within limits
            if files_collected >= max_files:
                continue
            if not is_relevant_file(file_path):
                # still count but don't read if not relevant and we have many files
                # For small repos, include anyway if total files < 30
                if len(file_list) > 30:
                    continue

            try:
                # Skip large files > 100KB
                size = file_path.stat().st_size
                if size > 100 * 1024:
                    file_contents.append(f"\n--- File: {rel_path} (skipped, too large: {size} bytes) ---\n")
                    continue

                # Try to read as text
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                # Truncate individual file to 2000 chars
                if len(content) > 2000:
                    content = content[:2000] + "\n...[truncated]..."

                entry = f"\n--- File: {rel_path} ---\n{content}\n"
                entry_len = len(entry)

                if total_chars + entry_len > max_total_chars:
                    # Allow at least 5 files
                    if files_collected < 5:
                        pass
                    else:
                        continue

                file_contents.append(entry)
                total_chars += entry_len
                files_collected += 1

            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                continue

    tree_str = "\n".join(file_tree_lines[:200])  # limit tree lines
    if len(file_tree_lines) > 200:
        tree_str += f"\n... and {len(file_tree_lines) - 200} more files ..."

    contents_str = "".join(file_contents)
    if total_chars >= max_total_chars:
        contents_str += f"\n\n[Truncated after {max_total_chars} chars for LLM context limit. Total files collected: {files_collected}]"

    metadata = {
        "total_files": len(file_list),
        "collected_files": files_collected,
        "total_chars": total_chars,
        "file_list": [str(p) for p in file_list[:100]]
    }

    logger.info(f"Collected {files_collected} files out of {len(file_list)} total, {total_chars} chars")

    return tree_str, contents_str, metadata
