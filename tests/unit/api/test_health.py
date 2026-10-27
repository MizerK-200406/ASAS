from fastapi.testclient import TestClient
from asas.api.app import create_app


def test_health_check_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ASAS"
    assert "version" in data
    assert "model" in data


def test_openapi_documentation_schema():
    app = create_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/students" in paths
    assert "/api/v1/students/{student_id}" in paths
    assert "/api/v1/quiz/generate" in paths
    assert "/api/v1/quiz/grade" in paths
    assert "/api/v1/flashcards/generate" in paths
    assert "/api/v1/flashcards/due" in paths
    assert "/api/v1/flashcards/review" in paths
    assert "/api/v1/chat/message" in paths
    assert "/api/v1/chat/sessions/{session_id}" in paths
