from __future__ import annotations

import json
import re
from pathlib import Path


DEFAULT_SENSITIVE_REPLY = "您的提问涉及暴力倾向，暂时无法解答。"


class SensitiveWordFilter:
    def __init__(self, words_path: Path, replacement: str = "***") -> None:
        self.words_path = words_path
        self.replacement = replacement
        self.words = self._load_words()

    def contains(self, text: str) -> bool:
        normalized = self._normalize(text)
        return any(self._normalize(word) in normalized for word in self.words)

    def mask(self, text: str) -> str:
        masked = text
        for word in self.words:
            if not word:
                continue
            masked = re.sub(re.escape(word), self.replacement, masked, flags=re.IGNORECASE)
        return masked

    def _load_words(self) -> list[str]:
        if not self.words_path.exists():
            return []
        data = json.loads(self.words_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            return []
        return [str(item).strip() for item in data if str(item).strip()]

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()
