from fastapi.testclient import TestClient
from app.main import app

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
        "callbackToken": "test-token"
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
        "callbackToken": "test-token"
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 400
