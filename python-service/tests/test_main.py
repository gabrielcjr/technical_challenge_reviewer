from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Challenge Evaluator" in response.text or "message" in response.json()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data


def test_evaluate_endpoint_accepts():
    payload = {
        "submissionId": "test-uuid-123",
        "githubRepoUrl": "https://github.com/octocat/Hello-World",
        "challengeText": "Build a simple API that returns hello world",
        "callbackUrl": "http://nginx/api/internal/evaluation-result",
        "callbackToken": "test-token",
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["submissionId"] == "test-uuid-123"


def test_evaluate_endpoint_invalid_challenge_text():
    payload = {
        "submissionId": "test-uuid-123",
        "githubRepoUrl": "https://github.com/octocat/Hello-World",
        "challengeText": "short",
        "callbackUrl": "http://nginx/api/internal/evaluation-result",
        "callbackToken": "test-token",
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 400


def test_internal_token_auth_enforced(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "callback_token", "secret_custom_token")

    payload = {
        "submissionId": "test-uuid-123",
        "githubRepoUrl": "https://github.com/octocat/Hello-World",
        "challengeText": "Build a simple API that returns hello world",
        "callbackUrl": "http://nginx/api/internal/evaluation-result",
        "callbackToken": "secret_custom_token",
    }
    # Unauthenticated request (no header)
    resp_unauth = client.post("/evaluate", json=payload)
    assert resp_unauth.status_code == 401

    # Authenticated request (with header)
    resp_auth = client.post("/evaluate", json=payload, headers={"X-Internal-Token": "secret_custom_token"})
    assert resp_auth.status_code == 202
