from fastapi.testclient import TestClient

import app.routers.admin as admin_router
from app.main import app


client = TestClient(app)


class FakeAdminStore:
    def __init__(self) -> None:
        self.faq_items = [
            {
                "intent": "shipping_fee",
                "question": "运费怎么算？",
                "keywords": ["运费"],
                "answer": "满 99 元免运费。",
            }
        ]
        self.settings = {
            "human_keywords": ["人工", "投诉"],
            "fallback_reply": "抱歉，我暂时没有理解您的问题。",
        }

    def list_faq(self):
        return self.faq_items

    def upsert_faq(self, item):
        payload = item.model_dump()
        self.faq_items = [existing for existing in self.faq_items if existing["intent"] != item.intent]
        self.faq_items.append(payload)
        return payload

    def delete_faq(self, intent):
        before = len(self.faq_items)
        self.faq_items = [item for item in self.faq_items if item["intent"] != intent]
        return len(self.faq_items) != before

    def get_settings(self):
        return self.settings

    def update_settings(self, settings):
        self.settings = settings.model_dump()
        return self.settings


def setup_function() -> None:
    admin_router.store = FakeAdminStore()
    admin_router.refresh_assistant = lambda: None


def test_admin_page_returns_html():
    response = client.get("/admin")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_can_list_and_upsert_faq():
    listed = client.get("/api/admin/faq")
    assert listed.status_code == 200
    assert listed.json()[0]["intent"] == "shipping_fee"

    response = client.put(
        "/api/admin/faq/invoice",
        json={
            "intent": "ignored",
            "question": "可以开发票吗？",
            "keywords": ["发票", "开票"],
            "answer": "可以开发票。",
        },
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "invoice"
    assert any(item["intent"] == "invoice" for item in admin_router.store.faq_items)


def test_admin_can_delete_faq():
    response = client.delete("/api/admin/faq/shipping_fee")

    assert response.status_code == 204
    assert admin_router.store.faq_items == []


def test_admin_can_update_human_handoff_settings():
    response = client.put(
        "/api/admin/settings",
        json={
            "human_keywords": ["人工", "经理"],
            "fallback_reply": "请换一种说法，或输入转人工。",
        },
    )

    assert response.status_code == 200
    assert response.json()["human_keywords"] == ["人工", "经理"]
    assert admin_router.store.settings["fallback_reply"] == "请换一种说法，或输入转人工。"


def test_admin_token_is_required_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")

    denied = client.get("/api/admin/faq")
    allowed = client.get("/api/admin/faq", headers={"x-admin-token": "secret"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
