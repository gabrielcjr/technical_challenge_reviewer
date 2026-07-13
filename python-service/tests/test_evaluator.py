import tempfile
from pathlib import Path
from app.evaluator import evaluate_repository

def test_evaluate_repository_no_keys(monkeypatch):
    # Mock no LLM keys -> fallback path
    import app.config as config_module
    monkeypatch.setattr(config_module.settings, "grok_api_key", "gsk_test")
    monkeypatch.setattr(config_module.settings, "gemini_api_key", "test")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "README.md").write_text("# TODO API\nImplements CRUD")
        (tmp / "app.py").write_text("def get_todos(): pass")

        result, meta = evaluate_repository(tmp, "Build a TODO API with CRUD")

        assert "approved" in result
        assert "summary" in result
        assert "improvements" in result
        assert isinstance(result["improvements"], list)
        # With no keys, should be not approved fallback
        assert result["approved"] is False or "LLM keys" in result["summary"]
        assert meta["total_files"] >= 1

def test_evaluate_repository_empty_repo(monkeypatch):
    import app.config as config_module
    monkeypatch.setattr(config_module.settings, "grok_api_key", "gsk_test")
    monkeypatch.setattr(config_module.settings, "gemini_api_key", "test")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Empty repo
        result, meta = evaluate_repository(tmp, "Some challenge")

        assert "approved" in result
        assert meta["total_files"] == 0
