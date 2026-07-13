import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from .file_collector import collect_files
from .prompts import build_evaluation_prompt, build_fallback_prompt
from .llm_provider import evaluate_with_llm
from .config import settings

logger = logging.getLogger(__name__)

def evaluate_repository(repo_path: Path, challenge_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Evaluate a cloned repository against challenge text.
    Returns (evaluation_result, metadata)
    """

    logger.info(f"Starting evaluation for repo at {repo_path}")

    # Collect files
    try:
        file_tree, file_contents, metadata = collect_files(
            repo_path,
            max_files=settings.max_files_to_read,
            max_total_chars=settings.max_file_content_chars
        )
    except Exception as e:
        logger.error(f"File collection failed: {e}")
        file_tree = "Failed to collect file tree"
        file_contents = ""
        metadata = {"error": str(e), "total_files": 0}

    logger.info(f"File collection done: {metadata}")

    # Build prompt
    if file_contents and len(file_contents) > 100:
        prompt = build_evaluation_prompt(challenge_text, file_tree, file_contents)
    else:
        prompt = build_fallback_prompt(challenge_text, file_tree)

    # Evaluate via LLM
    try:
        result, provider_used = evaluate_with_llm(prompt)
        metadata["llm_provider_used"] = provider_used
        metadata["prompt_length"] = len(prompt)

        logger.info(f"Evaluation result: approved={result['approved']} via {provider_used}")

        return result, metadata

    except Exception as e:
        logger.error(f"LLM evaluation failed: {e}")
        # Return failure result
        fallback_result = {
            'approved': False,
            'summary': f'Evaluation failed due to error: {str(e)[:200]}',
            'improvements': ['Check evaluator logs', 'Ensure LLM API keys are valid', 'Try retry'],
            'reasoning': str(e),
            'raw': {'error': str(e)}
        }
        metadata["error"] = str(e)
        return fallback_result, metadata
