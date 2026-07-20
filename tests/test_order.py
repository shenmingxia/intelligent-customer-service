import json
import sqlite3
from pathlib import Path

from app.services.order import HttpOrderRepository, OrderService, SqliteOrderRepository


ORDER_ROW = {
    "order_id": "Z100001",
    "status": "已发货",
    "tracking_company": "顺丰速运",
    "tracking_number": "SF000001",
    "estimated_delivery": "明天 18:00 前",
    "amount": 128.5,
    "refund_status": "未申请退款",
    "refundable": True,
    "refund_tip": "可提交售后申请。",
}


def test_sqlite_order_repository_checks_owner_user_id():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            status TEXT,
            tracking_company TEXT,
            tracking_number TEXT,
            estimated_delivery TEXT,
            amount REAL,
            refund_status TEXT,
            refundable INTEGER,
            refund_tip TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ORDER_ROW["order_id"],
            "owner-user",
            ORDER_ROW["status"],
            ORDER_ROW["tracking_company"],
            ORDER_ROW["tracking_number"],
            ORDER_ROW["estimated_delivery"],
            ORDER_ROW["amount"],
            ORDER_ROW["refund_status"],
            1,
            ORDER_ROW["refund_tip"],
        ),
    )

    repository = SqliteOrderRepository(":memory:", connection_factory=lambda _: connection)

    assert repository.find_by_id("Z100001", "owner-user") is not None
    assert repository.find_by_id("Z100001", "other-user") is None


def test_order_service_uses_sqlite_when_database_url_is_configured(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE orders (order_id TEXT PRIMARY KEY, user_id TEXT, status TEXT)")
    connection.execute("INSERT INTO orders VALUES ('Z100002', 'owner-user', '已发货')")

    monkeypatch.setenv("ORDER_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("ORDER_API_URL", raising=False)
    monkeypatch.setattr("app.services.order.sqlite3.connect", lambda _: connection)

    service = OrderService.from_default_source(Path("unused.json"))

    assert service.find_by_id("Z100002", "owner-user") is not None
    assert service.find_by_id("Z100002", "other-user") is None

def test_http_order_repository_sends_user_id_and_checks_payload_owner(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({**ORDER_ROW, "owner_user_id": "owner-user"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.order.urlopen", fake_urlopen)
    repository = HttpOrderRepository("https://orders.example.test/orders", timeout_seconds=3)

    order = repository.find_by_id("Z100001", "owner-user")
    denied = repository.find_by_id("Z100001", "other-user")

    assert order is not None
    assert denied is None
    assert "user_id=other-user" in captured["url"]
    assert captured["timeout"] == 3
