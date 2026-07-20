from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
    owner_user_ids: tuple[str, ...] = ()

    def belongs_to(self, user_id: str) -> bool:
        if not self.owner_user_ids:
            return True
        return user_id in self.owner_user_ids


class OrderRepository(Protocol):
    def find_by_id(self, order_id: str, user_id: str) -> Order | None:
        ...


class JsonOrderRepository:
    def __init__(self, orders_path: Path) -> None:
        items = json.loads(orders_path.read_text(encoding="utf-8-sig"))
        self.orders = {_normalize_order_id(item["order_id"]): _order_from_mapping(item) for item in items}

    def find_by_id(self, order_id: str, user_id: str) -> Order | None:
        order = self.orders.get(_normalize_order_id(order_id))
        if order is None or not order.belongs_to(user_id):
            return None
        return order


class SqliteOrderRepository:
    def __init__(self, database_url: str, connection_factory=None) -> None:
        self.database_path = _sqlite_path_from_url(database_url)
        self.connection_factory = connection_factory or sqlite3.connect

    def find_by_id(self, order_id: str, user_id: str) -> Order | None:
        with self.connection_factory(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            columns = _table_columns(connection, "orders")
            selected_columns = [
                column
                for column in [
                    "order_id",
                    "status",
                    "tracking_company",
                    "tracking_number",
                    "estimated_delivery",
                    "amount",
                    "refund_status",
                    "refundable",
                    "refund_tip",
                    "owner_user_id",
                    "owner_user_ids",
                    "user_id",
                ]
                if column in columns
            ]
            if not selected_columns:
                return None

            owner_checks = []
            params: list[str] = [order_id]
            if "owner_user_id" in columns:
                owner_checks.append("owner_user_id = ?")
                params.append(user_id)
            if "user_id" in columns:
                owner_checks.append("user_id = ?")
                params.append(user_id)
            if "owner_user_ids" in columns:
                owner_checks.append("owner_user_ids IS NULL")
                owner_checks.append("owner_user_ids = ''")
                owner_checks.append("instr(',' || owner_user_ids || ',', ',' || ? || ',') > 0")
                params.append(user_id)

            owner_clause = f"AND ({' OR '.join(owner_checks)})" if owner_checks else ""
            row = connection.execute(
                f"""
                SELECT {", ".join(selected_columns)}
                FROM orders
                WHERE upper(order_id) = upper(?)
                {owner_clause}
                LIMIT 1
                """,
                params,
            ).fetchone()

        if row is None:
            return None
        return _order_from_mapping(dict(row))


class HttpOrderRepository:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def find_by_id(self, order_id: str, user_id: str) -> Order | None:
        query = urlencode({"user_id": user_id})
        url = f"{self.base_url}/{_normalize_order_id(order_id)}?{query}"
        request = Request(url, headers={"Accept": "application/json"})

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {403, 404}:
                return None
            raise
        except URLError:
            return None

        order_data = payload.get("order", payload) if isinstance(payload, dict) else None
        if not order_data:
            return None

        order = _order_from_mapping(order_data)
        if not order.belongs_to(user_id):
            return None
        return order


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    @classmethod
    def from_default_source(cls, orders_path: Path) -> "OrderService":
        order_api_url = os.getenv("ORDER_API_URL")
        if order_api_url:
            timeout_seconds = _read_float_env("ORDER_API_TIMEOUT_SECONDS", 5.0)
            return cls(HttpOrderRepository(order_api_url, timeout_seconds=timeout_seconds))

        order_database_url = os.getenv("ORDER_DATABASE_URL")
        if order_database_url:
            return cls(SqliteOrderRepository(order_database_url))

        return cls(JsonOrderRepository(orders_path))

    def find_by_id(self, order_id: str, user_id: str) -> Order | None:
        return self.repository.find_by_id(order_id, user_id)


def _order_from_mapping(item: dict) -> Order:
    return Order(
        order_id=_normalize_order_id(str(item["order_id"])),
        status=str(item.get("status", "")),
        tracking_company=str(item.get("tracking_company", "")),
        tracking_number=str(item.get("tracking_number", "")),
        estimated_delivery=str(item.get("estimated_delivery", "")),
        amount=float(item.get("amount", 0)),
        refund_status=str(item.get("refund_status", "")),
        refundable=bool(item.get("refundable", False)),
        refund_tip=str(item.get("refund_tip", "")),
        owner_user_ids=_owner_user_ids_from_mapping(item),
    )


def _owner_user_ids_from_mapping(item: dict) -> tuple[str, ...]:
    owners = item.get("owner_user_ids")
    if owners is None:
        owner = item.get("owner_user_id") or item.get("user_id")
        owners = [owner] if owner else []
    if isinstance(owners, str):
        owners = [value.strip() for value in owners.split(",")]
    return tuple(str(owner) for owner in owners if owner)


def _normalize_order_id(order_id: str) -> str:
    return order_id.upper()


def _sqlite_path_from_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    if database_url.startswith("sqlite://"):
        return database_url.removeprefix("sqlite://")
    return database_url


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _read_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
