from fastapi.testclient import TestClient

from app.main import app
from app.routers.chat import assistant


client = TestClient(app)


def setup_function() -> None:
    assistant.sessions.clear()


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_returns_response_contract():
    response = client.post(
        "/api/chat",
        json={"user_id": "api-test", "message": "你好", "session_id": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "greeting"
    assert data["need_human"] is False
    assert data["session_id"].startswith("api-test-")
    assert set(data) == {"reply", "intent", "confidence", "need_human", "session_id", "context"}


def test_chat_endpoint_keeps_multi_turn_session_context():
    first = client.post(
        "/api/chat",
        json={"user_id": "api-order", "message": "我要查订单", "session_id": None},
    )
    assert first.status_code == 200

    session_id = first.json()["session_id"]
    second = client.post(
        "/api/chat",
        json={"user_id": "api-order", "message": "A123456", "session_id": session_id},
    )

    assert second.status_code == 200
    data = second.json()
    assert data["intent"] == "order_status_followup"
    assert data["session_id"] == session_id
    assert data["context"]["order_id"] == "A123456"
    assert "SF1234567890" in data["reply"]


def test_chat_endpoint_validates_required_message():
    response = client.post("/api/chat", json={"user_id": "api-test"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "message"]


def test_removed_boss_greeting_endpoint_returns_404():
    response = client.post("/api/boss/greeting", json={})

    assert response.status_code == 404


def test_openapi_schema_contains_current_routes_only():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "智能客服后端接口"
    assert "/api/chat" in schema["paths"]
    assert "/health" in schema["paths"]
    assert "/" in schema["paths"]
    assert "/api/boss/greeting" not in schema["paths"]
    assert "/boss" not in schema["paths"]
