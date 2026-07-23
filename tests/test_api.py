from fastapi.testclient import TestClient

import app.routers.chat as chat_router
from app.main import app
from app.schemas import ChatResponse
from app.routers.chat import assistant


client = TestClient(app)


class SlowAssistant:
    def handle(self, request):
        import time

        time.sleep(0.05)
        return ChatResponse(
            reply="slow reply",
            intent="unknown",
            confidence=0.2,
            need_human=False,
            session_id=request.session_id or f"{request.user_id}-slow",
            context={},
        )

    def build_timeout_response(self, request):
        return ChatResponse(
            reply="订单/物流查询暂时响应超时。请稍后重试，或输入“转人工”让客服帮您核对订单。",
            intent="timeout_order_status",
            confidence=0.6,
            need_human=True,
            session_id=request.session_id or f"{request.user_id}-timeout",
            context={},
        )


def setup_function() -> None:
    assistant.session_store.clear()


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
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["details"][0]["loc"] == ["body", "message"]
    assert response.headers["x-request-id"] == payload["error"]["request_id"]


def test_removed_boss_greeting_endpoint_returns_404():
    response = client.post("/api/boss/greeting", json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


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


def test_chat_endpoint_rejects_session_owned_by_another_user():
    first = client.post(
        "/api/chat",
        json={"user_id": "api-owner", "message": "我要查订单", "session_id": None},
    )
    assert first.status_code == 200

    response = client.post(
        "/api/chat",
        json={
            "user_id": "api-other",
            "message": "A123456",
            "session_id": first.json()["session_id"],
        },
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "session_id does not belong to this user"


def test_chat_endpoint_circuit_breaker_returns_intent_fallback(monkeypatch):
    monkeypatch.setenv("ANSWER_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setattr(chat_router, "assistant", SlowAssistant())

    response = client.post(
        "/api/chat",
        headers={"x-forwarded-for": "203.0.113.88"},
        json={"user_id": "timeout-user", "message": "我要查订单", "session_id": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "timeout_order_status"
    assert data["need_human"] is True
    assert "转人工" in data["reply"]


def test_chat_endpoint_rate_limit_returns_429():
    headers = {"x-forwarded-for": "203.0.113.77"}

    for index in range(60):
        response = client.post(
            "/api/chat",
            headers=headers,
            json={"user_id": "rate-limited-user", "message": "hello", "session_id": None},
        )
        assert response.status_code == 200

    limited = client.post(
        "/api/chat",
        headers=headers,
        json={"user_id": "rate-limited-user", "message": "hello", "session_id": None},
    )

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["x-ratelimit-remaining"] == "0"


def test_chat_endpoint_rate_limit_uses_user_before_ip():
    headers = {"x-forwarded-for": "203.0.113.78"}

    for index in range(61):
        response = client.post(
            "/api/chat",
            headers=headers,
            json={"user_id": f"company-user-{index}", "message": "hello", "session_id": None},
        )
        assert response.status_code == 200
