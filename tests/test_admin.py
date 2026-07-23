from fastapi.testclient import TestClient
from pathlib import Path

import app.routers.admin as admin_router
import app.routers.feedback as feedback_router
from app.main import app
from app.schemas import FeedbackRequest
from app.services.admin_store import AdminStore


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

    def list_sensitive_words(self):
        return [{"word": word} for word in self.sensitive_words]

    def upsert_sensitive_word(self, item):
        if item.word not in self.sensitive_words:
            self.sensitive_words.append(item.word)
        return {"word": item.word}

    def update_sensitive_word(self, old_word, item):
        if old_word not in self.sensitive_words:
            return {}
        self.sensitive_words = [item.word if word == old_word else word for word in self.sensitive_words]
        return {"word": item.word}

    def delete_sensitive_word(self, word):
        if word not in self.sensitive_words:
            return False
        self.sensitive_words.remove(word)
        return True


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


class FakeFeedbackStore:
    def __init__(self) -> None:
        self.feedback_items = []

    def add_feedback(self, feedback):
        payload = feedback.model_dump()
        self.feedback_items.append(payload)
        return payload

    def top_downvoted_questions(self, limit=10):
        return [
            {
                "question": "退款多久到账",
                "total_feedback": 3,
                "downvotes": 2,
                "downvote_rate": 0.6667,
                "intent": "refund_time",
                "latest_reply": "退款通常 1-3 个工作日到账。",
                "reasons": {"没解决我的问题": 2},
            }
        ][:limit]

    def update_feedback_status(self, question, status):
        return {"question": question, "status": status}


def test_feedback_endpoint_records_rating():
    feedback_router.store = FakeFeedbackStore()

    response = client.post(
        "/api/feedback",
        json={
            "user_id": "web-user",
            "session_id": "web-user-12345678",
            "user_message": "退款多久到账",
            "assistant_reply": "退款通常 1-3 个工作日到账。",
            "intent": "refund_time",
            "rating": "not_useful",
            "reason": "没解决我的问题",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert feedback_router.store.feedback_items[0]["rating"] == "not_useful"


def test_admin_can_list_top_downvoted_questions():
    admin_router.store = FakeFeedbackStore()

    response = client.get("/api/admin/feedback/top")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["question"] == "退款多久到账"
    assert data[0]["downvote_rate"] == 0.6667


def test_admin_can_update_feedback_status():
    admin_router.store = FakeFeedbackStore()

    response = client.put(
        "/api/admin/feedback/status",
        json={"question": "refund status", "status": "handled"},
    )

    assert response.status_code == 200
    assert response.json() == {"question": "refund status", "status": "handled"}


def test_feedback_store_uses_sqlite_for_top_downvoted_questions(monkeypatch):
    db_path = Path("data/test_feedback_store.db")
    db_path.unlink(missing_ok=True)
    db_path.with_suffix(".db-wal").unlink(missing_ok=True)
    db_path.with_suffix(".db-shm").unlink(missing_ok=True)
    monkeypatch.setenv("FEEDBACK_DATABASE_URL", str(db_path))
    store = AdminStore(Path("data/test_feedback_store_data"))

    store.add_feedback(
        FeedbackRequest(
            user_id="u1",
            session_id="s1",
            user_message="refund status",
            assistant_reply="refund in 1-3 days",
            intent="refund_time",
            rating="not_useful",
            reason="not solved",
        )
    )
    store.add_feedback(
        FeedbackRequest(
            user_id="u2",
            session_id="s2",
            user_message="refund status",
            assistant_reply="refund in 1-3 days",
            intent="refund_time",
            rating="useful",
        )
    )

    top_items = store.top_downvoted_questions()

    assert db_path.exists()
    assert top_items[0]["question"] == "refund status"
    assert top_items[0]["total_feedback"] == 2
    assert top_items[0]["downvotes"] == 1
    assert top_items[0]["downvote_rate"] == 0.5
    assert top_items[0]["reasons"] == {"not solved": 1}
    assert top_items[0]["status"] == "open"

    store.update_feedback_status("refund status", "handled")
    handled_items = store.top_downvoted_questions()
    assert handled_items[0]["status"] == "handled"
    db_path.unlink(missing_ok=True)
    db_path.with_suffix(".db-wal").unlink(missing_ok=True)
    db_path.with_suffix(".db-shm").unlink(missing_ok=True)
    test_data_dir = Path("data/test_feedback_store_data")
    if test_data_dir.exists():
        test_data_dir.rmdir()


def test_admin_store_manages_sensitive_words_file(monkeypatch):
    data_dir = Path("data/test_sensitive_words_data")
    data_dir.mkdir(exist_ok=True)
    words_path = data_dir / "sensitive_words.json"
    words_path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("FEEDBACK_DATABASE_URL", "data/test_sensitive_words_feedback.db")
    db_path = Path("data/test_sensitive_words_feedback.db")
    db_path.unlink(missing_ok=True)

    store = AdminStore(data_dir)
    store.upsert_sensitive_word(type("Item", (), {"word": "blocked"})())
    assert store.list_sensitive_words() == [{"word": "blocked"}]
    assert store.update_sensitive_word("blocked", type("Item", (), {"word": "blocked2"})()) == {"word": "blocked2"}
    assert store.delete_sensitive_word("blocked2") is True
    assert store.list_sensitive_words() == []

    words_path.unlink(missing_ok=True)
    db_path.unlink(missing_ok=True)
    db_path.with_suffix(".db-wal").unlink(missing_ok=True)
    db_path.with_suffix(".db-shm").unlink(missing_ok=True)
    if data_dir.exists():
        data_dir.rmdir()
