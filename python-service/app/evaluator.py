import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from .file_collector import collect_files
from .prompts import build_evaluation_prompt, build_fallback_prompt
from .llm_provider import evaluate_with_llm
from .config import settings

logger = logging.getLogger(__name__)

# Constants
MIN_FILE_CONTENT_LENGTH_FOR_FULL_PROMPT = 100
FALLBACK_SUMMARY_MAX_LENGTH = 200
ERROR_DETAIL_TRUNCATE_LENGTH = 200


def evaluate_repository(repo_path: Path, challenge_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Evaluate a cloned repository against challenge text.
    Returns (evaluation_result, metadata)
    """
    logger.info(f"Starting evaluation for repo at {repo_path}")

    file_tree, file_contents, metadata = _collect_repository_files(repo_path)
    prompt = _build_prompt_for_contents(challenge_text, file_tree, file_contents)
    return _evaluate_with_llm_and_handle_errors(prompt, metadata)


def _collect_repository_files(repo_path: Path) -> Tuple[str, str, Dict[str, Any]]:
    try:
        file_tree, file_contents, metadata = collect_files(
            repo_path,
            max_files=settings.max_files_to_read,
            max_total_chars=settings.max_file_content_chars,
        )
        logger.info(f"File collection done: {metadata}")
        return file_tree, file_contents, metadata
    except Exception as collection_error:
        logger.error(f"File collection failed: {collection_error}")
        return (
            "Failed to collect file tree",
            "",
            {"error": str(collection_error), "total_files": 0},
        )


def _build_prompt_for_contents(challenge_text: str, file_tree: str, file_contents: str) -> str:
    if file_contents and len(file_contents) > MIN_FILE_CONTENT_LENGTH_FOR_FULL_PROMPT:
        return build_evaluation_prompt(challenge_text, file_tree, file_contents)
    return build_fallback_prompt(challenge_text, file_tree)


def _evaluate_with_llm_and_handle_errors(prompt: str, metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        result, provider_used = evaluate_with_llm(prompt)
        metadata["llm_provider_used"] = provider_used
        metadata["prompt_length"] = len(prompt)
        logger.info(f"Evaluation result: approved={result['approved']} via {provider_used}")
        return result, metadata
    except Exception as evaluation_error:
        logger.error(f"LLM evaluation failed: {evaluation_error}")
        return _build_evaluation_failure_result(evaluation_error, metadata)


def _build_evaluation_failure_result(error: Exception, metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    truncated_error = str(error)[:ERROR_DETAIL_TRUNCATE_LENGTH]
    fallback_result = {
        "approved": False,
        "summary": f"Evaluation failed due to error: {truncated_error}",
        "improvements": [
            "Check evaluator logs",
            "Ensure LLM API keys are valid",
            "Try retry",
        ],
        "reasoning": str(error),
        "raw": {"error": str(error)},
    }
    metadata["error"] = str(error)
    return fallback_result, metadata
