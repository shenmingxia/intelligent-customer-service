from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from app.schemas import AdminSettings, FaqItem, FeedbackRequest


class AdminStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.faq_path = data_dir / "faq.json"
        self.config_path = data_dir / "config.json"
        self.feedback_path = data_dir / "feedback.json"

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

    def add_feedback(self, feedback: FeedbackRequest) -> dict:
        items = self._read_json_list(self.feedback_path)
        payload = feedback.model_dump()
        items.append(payload)
        self._write_json(self.feedback_path, items)
        return payload

    def top_downvoted_questions(self, limit: int = 10) -> list[dict]:
        grouped: dict[str, dict] = {}
        reason_counts: dict[str, Counter] = defaultdict(Counter)

        for item in self._read_json_list(self.feedback_path):
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
                }
            )

        ranked.sort(key=lambda item: (item["downvote_rate"], item["downvotes"], item["total_feedback"]), reverse=True)
        return ranked[:limit]

    def _read_json_list(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []

    def _read_json_dict(self, path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}

    def _write_json(self, path: Path, data) -> None:
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)
