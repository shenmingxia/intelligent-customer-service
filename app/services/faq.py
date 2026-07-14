import json
from pathlib import Path


class FaqService:
    def __init__(self, faq_path: Path) -> None:
        self.items = json.loads(faq_path.read_text(encoding="utf-8-sig"))

    def search(self, message: str) -> dict | None:
        normalized = message.lower()
        best_item = None
        best_score = 0.0

        for item in self.items:
            keywords = item.get("keywords", [])
            hits = sum(1 for keyword in keywords if keyword.lower() in normalized)
            if not keywords or hits == 0:
                continue
            score = hits / len(keywords)
            if score > best_score:
                best_item = item
                best_score = score

        if best_item is None or best_score < 0.34:
            return None

        return {
            "answer": best_item["answer"],
            "intent": best_item.get("intent", "faq"),
            "score": round(best_score, 2),
        }
