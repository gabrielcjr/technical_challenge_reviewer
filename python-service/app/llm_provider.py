import json
import logging
import re
from typing import Dict, Any, Tuple

from .config import settings

logger = logging.getLogger(__name__)

def get_grok_llm():
    """Create Grok (xAI) LLM via LangChain"""
    if not settings.grok_api_key or settings.grok_api_key in ("gsk_test", "xai_test", "test", ""):
        raise ValueError("Grok API key not configured")

    try:
        from langchain_xai import ChatXAI
        # Free models from xAI:
        # - grok-3-mini (recommended free, fast, cheap)
        # - grok-3 (flagship, free tier with $5 credits)
        # - grok-3-fast
        # - grok-2-1212 (Grok 2)
        # - grok-beta (legacy free)
        llm = ChatXAI(
            model="grok-3-mini",  # free tier model
            api_key=settings.grok_api_key,
            temperature=0.2,
            max_tokens=2000,
        )
        return llm
    except ImportError as e:
        logger.error(f"langchain-xai not available: {e}. Trying fallback to openai-compatible client.")
        # Fallback: try using ChatOpenAI with xAI base URL (xAI is OpenAI-compatible)
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="grok-3-mini",
                api_key=settings.grok_api_key,
                base_url="https://api.x.ai/v1",
                temperature=0.2,
                max_tokens=2000,
            )
            return llm
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            raise e

def get_gemini_llm():
    """Create Gemini LLM via LangChain"""
    if not settings.gemini_api_key or settings.gemini_api_key == "test":
        raise ValueError("Gemini API key not configured")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model="gemini-1.5-flash",
            temperature=0.2,
            max_output_tokens=2000,
        )
        return llm
    except ImportError as e:
        logger.error(f"langchain-google-genai not available: {e}")
        raise

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Robustly extract JSON from LLM output that might have markdown fences or extra text"""
    text = text.strip()

    # Remove markdown code fences if present
    # ```json ... ```
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find first { to last } 
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse candidate JSON: {e}, candidate: {candidate[:500]}")
            pass

    raise ValueError(f"Could not extract valid JSON from LLM output: {text[:1000]}")

def normalize_evaluation_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure result has required fields and correct types"""
    approved = data.get('approved')
    if isinstance(approved, str):
        approved = approved.lower() in ('true', 'yes', '1', 'approved')
    approved = bool(approved)

    summary = data.get('summary', '')
    if not summary:
        summary = "Approved" if approved else "Not approved"

    improvements = data.get('improvements', [])
    if not isinstance(improvements, list):
        improvements = [str(improvements)] if improvements else []

    reasoning = data.get('reasoning', '') or data.get('reason', '') or data.get('explanation', '')

    return {
        'approved': approved,
        'summary': summary[:500],
        'improvements': [str(i)[:300] for i in improvements][:10],
        'reasoning': str(reasoning)[:2000],
        'raw': data
    }

def evaluate_with_llm(prompt: str) -> Tuple[Dict[str, Any], str]:
    """
    Evaluate using LLM with fallback logic.
    Returns (normalized_result, provider_used)
    """
    providers_to_try = []

    # Normalize provider - support legacy grok spelling
    provider_env = settings.llm_provider.lower() if settings.llm_provider else "auto"
    if provider_env == "grok":
        provider_env = "grok"  # backward compat

    if provider_env == "grok":
        providers_to_try = ["grok"]
    elif provider_env == "gemini":
        providers_to_try = ["gemini"]
    else:  # auto
        # Try grok first, then gemini
        providers_to_try = ["grok", "gemini"]

    last_error = None

    for provider in providers_to_try:
        try:
            if provider == "grok":
                logger.info("Trying Grok (xAI) LLM")
                if not settings.grok_api_key or settings.grok_api_key in ("gsk_test", "xai_test", "test", ""):
                    raise ValueError("Grok API key not set")
                llm = get_grok_llm()
                used = "grok:grok-3-mini"
            else:
                logger.info("Trying Gemini LLM")
                if not settings.gemini_api_key or settings.gemini_api_key in ("test", ""):
                    raise ValueError("Gemini API key not set")
                llm = get_gemini_llm()
                used = "gemini:gemini-1.5-flash"

            messages = [
                ("system", "You are a senior technical reviewer. Output valid JSON only."),
                ("human", prompt)
            ]

            response = llm.invoke(messages)
            content = response.content if hasattr(response, 'content') else str(response)

            logger.info(f"LLM response from {provider}: {content[:500]}")

            parsed = extract_json_from_text(content)
            normalized = normalize_evaluation_result(parsed)

            return normalized, used

        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}")
            last_error = e
            continue

    # If all providers fail, return a fallback heuristic result
    logger.error(f"All LLM providers failed, last error: {last_error}. Returning fallback REJECTED with improvements.")

    if settings.grok_api_key in ("gsk_test", "xai_test", "test", "") and settings.gemini_api_key in ("test", ""):
        logger.warning("No LLM keys configured, using heuristic fallback evaluation")
        return {
            'approved': False,
            'summary': 'LLM keys not configured - evaluation skipped. Configure GROK_API_KEY or GEMINI_API_KEY for real AI evaluation.',
            'improvements': ['Configure GROK_API_KEY (xAI) or GEMINI_API_KEY in .env to enable AI evaluation', 'Once keys are set, re-run evaluation via retry button'],
            'reasoning': f'No LLM provider available. Last error: {last_error}. Set API keys to enable evaluation.',
            'raw': {'error': str(last_error)}
        }, 'fallback:no-keys'

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
