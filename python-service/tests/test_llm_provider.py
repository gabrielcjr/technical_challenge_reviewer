import pytest
from app.llm_provider import extract_json_from_text, normalize_evaluation_result

def test_extract_json_direct():
    text = '{"approved": true, "summary": "ok", "improvements": [], "reasoning": "good"}'
    data = extract_json_from_text(text)
    assert data["approved"] is True

def test_extract_json_with_markdown_fence():
    text = """Here is result:
```json
{"approved": false, "summary": "bad", "improvements": ["fix"], "reasoning": "missing"}
```
"""
    data = extract_json_from_text(text)
    assert data["approved"] is False
    assert data["summary"] == "bad"

def test_extract_json_with_extra_text():
    text = 'Some intro text {"approved": true, "summary": "good", "improvements": [], "reasoning": "ok"} some outro'
    data = extract_json_from_text(text)
    assert data["approved"] is True

def test_normalize_result():
    data = {
        "approved": "true",
        "summary": "test",
        "improvements": ["a", "b"],
        "reasoning": "reason"
    }
    normalized = normalize_evaluation_result(data)
    assert normalized["approved"] is True
    assert normalized["summary"] == "test"
    assert len(normalized["improvements"]) == 2

def test_normalize_result_bool_string():
    data = {"approved": "yes", "summary": "", "improvements": [], "reasoning": ""}
    norm = normalize_evaluation_result(data)
    assert norm["approved"] is True
    assert norm["summary"]  # Should have default

def test_evaluate_with_no_keys(monkeypatch):
    # Simulate no keys configured -> fallback
    import app.config as config_module
    monkeypatch.setattr(config_module.settings, "grok_api_key", "gsk_test")
    monkeypatch.setattr(config_module.settings, "gemini_api_key", "test")
    monkeypatch.setattr(config_module.settings, "llm_provider", "auto")

    from app.llm_provider import evaluate_with_llm

    prompt = "Test challenge"
    result, provider = evaluate_with_llm(prompt)

    assert "approved" in result
    assert "summary" in result
    assert provider == "fallback:no-keys"
    assert result["approved"] is False
    assert "LLM keys not configured" in result["summary"]
