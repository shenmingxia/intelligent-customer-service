from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Order:
    order_id: str
    status: str
    tracking_company: str
    tracking_number: str
    estimated_delivery: str
    amount: float
    refund_status: str
    refundable: bool
    refund_tip: str


class OrderService:
    def __init__(self, orders_path: Path) -> None:
        items = json.loads(orders_path.read_text(encoding="utf-8-sig"))
        self.orders = {
            item["order_id"].upper(): Order(
                order_id=item["order_id"].upper(),
                status=item["status"],
                tracking_company=item.get("tracking_company", ""),
                tracking_number=item.get("tracking_number", ""),
                estimated_delivery=item.get("estimated_delivery", ""),
                amount=float(item.get("amount", 0)),
                refund_status=item.get("refund_status", ""),
                refundable=bool(item.get("refundable", False)),
                refund_tip=item.get("refund_tip", ""),
            )
            for item in items
        }

    def find_by_id(self, order_id: str) -> Order | None:
        return self.orders.get(order_id.upper())
