import json
import logging
import re
from typing import Dict, Any, Tuple, List

from .config import settings, SENTINEL_TEST_TOKENS

logger = logging.getLogger(__name__)

# --- Constants ---
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"
GEMINI_MODEL_NAME = "gemini-2.0-flash-lite"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 2000

TRUTHY_STRINGS = ("true", "yes", "1", "approved")
MAX_SUMMARY_LENGTH = 500
MAX_IMPROVEMENT_LENGTH = 300
MAX_REASONING_LENGTH = 2000
MAX_IMPROVEMENTS_COUNT = 10

JSON_FENCE_PATTERN = r"```(?:json)?\s*(\{.*?\})\s*```"
LOG_PREVIEW_LENGTH = 500


def _is_test_token(token: str) -> bool:
    return token in SENTINEL_TEST_TOKENS


def _is_groq_configured() -> bool:
    return settings.is_groq_configured()


def _is_gemini_configured() -> bool:
    return settings.is_gemini_configured()


# --- LLM Factory ---
def get_groq_llm():
    """Create Groq LLM via OpenAI-compatible interface."""
    if not _is_groq_configured():
        raise ValueError("Groq API key not configured")

    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=GROQ_MODEL_NAME,
            api_key=settings.resolved_groq_api_key,
            base_url=GROQ_API_BASE_URL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
    except Exception as e:
        logger.error(f"Failed to create Groq LLM: {e}")
        raise


def get_gemini_llm():
    """Create Gemini LLM via LangChain."""
    if not _is_gemini_configured():
        raise ValueError("Gemini API key not configured")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=GEMINI_MODEL_NAME,
            temperature=LLM_TEMPERATURE,
            max_output_tokens=LLM_MAX_TOKENS,
        )
    except ImportError as import_error:
        logger.error(f"langchain-google-genai not available: {import_error}")
        raise


# --- JSON Parsing ---
def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM output that may contain markdown fences or surrounding text."""
    cleaned = text.strip()
    cleaned = _strip_markdown_fence(cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return _extract_json_between_braces(cleaned)


def _strip_markdown_fence(text: str) -> str:
    match = re.search(JSON_FENCE_PATTERN, text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def _extract_json_between_braces(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Could not extract valid JSON from LLM output: {text[:1000]}")

    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as parse_error:
        logger.warning(f"Failed to parse candidate JSON: {parse_error}, candidate preview: {candidate[:500]}")
        raise ValueError(f"Could not extract valid JSON from LLM output: {text[:1000]}")


# --- Normalization ---
def normalize_evaluation_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure result has required fields and correct types."""
    approved = _normalize_approved_field(data.get("approved"))
    summary = _normalize_summary(data, approved)
    improvements = _normalize_improvements(data.get("improvements", []))
    reasoning = _normalize_reasoning(data)

    return {
        "approved": approved,
        "summary": summary,
        "improvements": improvements,
        "reasoning": reasoning,
        "raw": data,
    }


def _normalize_approved_field(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in TRUTHY_STRINGS
    return bool(value)


def _normalize_summary(data: Dict[str, Any], approved: bool) -> str:
    summary = data.get("summary", "")
    if not summary:
        return "Approved" if approved else "Not approved"
    return str(summary)[:MAX_SUMMARY_LENGTH]


def _normalize_improvements(improvements: Any) -> List[str]:
    if not isinstance(improvements, list):
        improvements = [str(improvements)] if improvements else []
    truncated = [str(item)[:MAX_IMPROVEMENT_LENGTH] for item in improvements]
    return truncated[:MAX_IMPROVEMENTS_COUNT]


def _normalize_reasoning(data: Dict[str, Any]) -> str:
    reasoning = data.get("reasoning", "") or data.get("reason", "") or data.get("explanation", "")
    return str(reasoning)[:MAX_REASONING_LENGTH]


# --- Orchestration ---
def evaluate_with_llm(prompt: str) -> Tuple[Dict[str, Any], str]:
    """
    Evaluate using LLM with fallback logic.
    Returns (normalized_result, provider_used)
    """
    providers = _determine_providers_to_try()
    result = _try_providers_in_sequence(providers, prompt)
    if result:
        return result
    return _handle_all_providers_failed()


def _determine_providers_to_try() -> List[str]:
    provider_env = (settings.llm_provider or "auto").lower()
    if provider_env == "groq":
        return ["groq"]
    if provider_env == "gemini":
        return ["gemini"]
    # auto: try groq first (free, fast), then gemini
    ordered = []
    if _is_groq_configured():
        ordered.append("groq")
    if _is_gemini_configured():
        ordered.append("gemini")
    if not ordered:
        ordered = ["groq", "gemini"]
    return ordered


def _try_providers_in_sequence(providers: List[str], prompt: str) -> Tuple[Dict[str, Any], str] | None:
    last_error: Exception | None = None

    for provider_name in providers:
        try:
            return _evaluate_with_single_provider(provider_name, prompt)
        except Exception as provider_error:
            logger.warning(f"Provider {provider_name} failed: {provider_error}")
            last_error = provider_error
            continue

    # Store last_error for fallback logic
    _try_providers_in_sequence.last_error = last_error  # type: ignore
    return None


def _evaluate_with_single_provider(provider: str, prompt: str) -> Tuple[Dict[str, Any], str]:
    if provider == "groq":
        llm = get_groq_llm()
        used_provider_name = f"groq:{GROQ_MODEL_NAME}"
    else:
        llm = get_gemini_llm()
        used_provider_name = f"gemini:{GEMINI_MODEL_NAME}"

    logger.info(f"Trying {provider} LLM")
    messages = [
        ("system", "You are a senior technical reviewer. Output valid JSON only."),
        ("human", prompt),
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    logger.info(f"LLM response from {provider}: {content[:LOG_PREVIEW_LENGTH]}")

    parsed = extract_json_from_text(content)
    normalized = normalize_evaluation_result(parsed)

    return normalized, used_provider_name


def _handle_all_providers_failed() -> Tuple[Dict[str, Any], str]:
    last_error = getattr(_try_providers_in_sequence, "last_error", None)
    logger.error(f"All LLM providers failed, last error: {last_error}. Returning fallback.")

    if not settings.is_groq_configured() and not settings.is_gemini_configured():
        logger.warning("No LLM keys configured, using heuristic fallback evaluation")
        return _build_no_keys_fallback_result(last_error)

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def _build_no_keys_fallback_result(last_error: Exception | None) -> Tuple[Dict[str, Any], str]:
    return {
        "approved": False,
        "summary": "LLM keys not configured - evaluation skipped. Configure GROQ_API_KEY or GEMINI_API_KEY for real AI evaluation.",
        "improvements": [
            "Configure GROQ_API_KEY (Groq, free) or GEMINI_API_KEY in .env to enable AI evaluation",
            "Once keys are set, re-run evaluation via retry button",
        ],
        "reasoning": f"No LLM provider available. Last error: {last_error}. Set API keys to enable evaluation.",
        "raw": {"error": str(last_error)},
    }, "fallback:no-keys"
