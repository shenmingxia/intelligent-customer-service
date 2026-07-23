from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.schemas import AdminSettings, FaqItem, FeedbackRequest, SensitiveWordItem


class AdminStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.faq_path = data_dir / "faq.json"
        self.config_path = data_dir / "config.json"
        self.sensitive_words_path = data_dir / "sensitive_words.json"
        self.feedback_json_path = data_dir / "feedback.json"
        self.feedback_db_path = _sqlite_path_from_url(os.getenv("FEEDBACK_DATABASE_URL", str(data_dir / "feedback.db")))
        self._ensure_feedback_schema()

    def list_faq(self) -> list[dict]:
        return self._read_json_list(self.faq_path)

    def upsert_faq(self, item: FaqItem) -> dict:
        items = self.list_faq()
        payload = item.model_dump()
        for index, existing in enumerate(items):
            if existing.get("intent") == item.intent:
                items[index] = payload
                self._write_json(self.faq_path, items)
                return payload

        items.append(payload)
        self._write_json(self.faq_path, items)
        return payload

    def delete_faq(self, intent: str) -> bool:
        items = self.list_faq()
        kept_items = [item for item in items if item.get("intent") != intent]
        if len(kept_items) == len(items):
            return False
        self._write_json(self.faq_path, kept_items)
        return True

    def get_settings(self) -> dict:
        return self._read_json_dict(self.config_path)

    def update_settings(self, settings: AdminSettings) -> dict:
        payload = settings.model_dump()
        self._write_json(self.config_path, payload)
        return payload

    def list_sensitive_words(self) -> list[dict]:
        return [{"word": word} for word in self._read_string_list(self.sensitive_words_path)]

    def upsert_sensitive_word(self, item: SensitiveWordItem) -> dict:
        word = item.word.strip()
        words = self._read_string_list(self.sensitive_words_path)
        if word not in words:
            words.append(word)
            self._write_json(self.sensitive_words_path, words)
        return {"word": word}

    def update_sensitive_word(self, old_word: str, item: SensitiveWordItem) -> dict:
        words = self._read_string_list(self.sensitive_words_path)
        new_word = item.word.strip()
        updated = False
        next_words: list[str] = []
        for word in words:
            if word == old_word:
                if new_word not in next_words:
                    next_words.append(new_word)
                updated = True
            elif word not in next_words:
                next_words.append(word)
        if not updated:
            return {}
        self._write_json(self.sensitive_words_path, next_words)
        return {"word": new_word}

    def delete_sensitive_word(self, word: str) -> bool:
        words = self._read_string_list(self.sensitive_words_path)
        kept_words = [item for item in words if item != word]
        if len(kept_words) == len(words):
            return False
        self._write_json(self.sensitive_words_path, kept_words)
        return True

    def add_feedback(self, feedback: FeedbackRequest) -> dict:
        payload = feedback.model_dump()
        with self._feedback_connection() as connection:
            connection.execute(
                """
                INSERT INTO feedback (
                    user_id,
                    session_id,
                    user_message,
                    assistant_reply,
                    intent,
                    rating,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["user_id"],
                    payload["session_id"],
                    payload["user_message"],
                    payload["assistant_reply"],
                    payload["intent"],
                    payload["rating"],
                    payload["reason"],
                ),
            )
        return payload

    def top_downvoted_questions(self, limit: int = 10) -> list[dict]:
        grouped: dict[str, dict] = {}
        reason_counts: dict[str, Counter] = defaultdict(Counter)

        with self._feedback_connection() as connection:
            rows = connection.execute(
                """
                SELECT user_message, assistant_reply, intent, rating, reason
                FROM feedback
                ORDER BY id ASC
                """
            ).fetchall()
            status_rows = connection.execute("SELECT question, status FROM feedback_actions").fetchall()
            statuses = {row["question"]: row["status"] for row in status_rows}

        for row in rows:
            item = dict(row)
            question = " ".join(str(item.get("user_message", "")).split())
            if not question:
                continue

            group = grouped.setdefault(
                question,
                {
                    "question": question,
                    "total_feedback": 0,
                    "downvotes": 0,
                    "intent": str(item.get("intent", "unknown")),
                    "latest_reply": str(item.get("assistant_reply", "")),
                },
            )
            group["total_feedback"] += 1
            group["intent"] = str(item.get("intent", group["intent"]))
            group["latest_reply"] = str(item.get("assistant_reply", group["latest_reply"]))

            if item.get("rating") == "not_useful":
                group["downvotes"] += 1
                reason = item.get("reason")
                if reason:
                    reason_counts[question][str(reason)] += 1

        ranked = []
        for question, group in grouped.items():
            total = group["total_feedback"]
            downvotes = group["downvotes"]
            ranked.append(
                {
                    **group,
                    "downvote_rate": round(downvotes / total, 4) if total else 0.0,
                    "reasons": dict(reason_counts[question]),
                    "status": statuses.get(question, "open"),
                }
            )

        ranked.sort(key=lambda item: (item["downvote_rate"], item["downvotes"], item["total_feedback"]), reverse=True)
        return ranked[:limit]

    def update_feedback_status(self, question: str, status: str) -> dict:
        normalized_question = " ".join(question.split())
        with self._feedback_connection() as connection:
            connection.execute(
                """
                INSERT INTO feedback_actions (question, status, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(question) DO UPDATE SET
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (normalized_question, status),
            )
        return {"question": normalized_question, "status": status}

    def _ensure_feedback_schema(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        Path(self.feedback_db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._feedback_connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'guest',
                    session_id TEXT,
                    user_message TEXT NOT NULL,
                    assistant_reply TEXT NOT NULL,
                    intent TEXT NOT NULL DEFAULT 'unknown',
                    rating TEXT NOT NULL CHECK (rating IN ('useful', 'not_useful')),
                    reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_feedback_question ON feedback(user_message)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_actions (
                    question TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN ('open', 'handled', 'ignored')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        self._migrate_feedback_json()

    def _migrate_feedback_json(self) -> None:
        if not self.feedback_json_path.exists():
            return
        items = self._read_json_list(self.feedback_json_path)
        if not items:
            return
        with self._feedback_connection() as connection:
            existing_count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            if existing_count:
                return
            connection.executemany(
                """
                INSERT INTO feedback (
                    user_id,
                    session_id,
                    user_message,
                    assistant_reply,
                    intent,
                    rating,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(item.get("user_id", "guest")),
                        item.get("session_id"),
                        str(item.get("user_message", "")),
                        str(item.get("assistant_reply", "")),
                        str(item.get("intent", "unknown")),
                        str(item.get("rating", "useful")),
                        item.get("reason"),
                    )
                    for item in items
                    if item.get("user_message") and item.get("assistant_reply")
                ],
            )

    @contextmanager
    def _feedback_connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.feedback_db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _read_json_list(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []

    def _read_json_dict(self, path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}

    def _read_string_list(self, path: Path) -> list[str]:
        data = self._read_json_list(path)
        words: list[str] = []
        for item in data:
            word = str(item).strip()
            if word and word not in words:
                words.append(word)
        return words

    def _write_json(self, path: Path, data) -> None:
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)


def _sqlite_path_from_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    if database_url.startswith("sqlite://"):
        return database_url.removeprefix("sqlite://")
    return database_url
