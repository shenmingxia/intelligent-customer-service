from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MIN_MATCH_SCORE = 0.28

# Small domain synonym table keeps semantic FAQ retrieval useful without external services.
DOMAIN_SYNONYMS = {
    "运费": ["邮费", "配送费", "快递费", "物流费", "包邮", "免邮", "shipping"],
    "退款": ["退钱", "返款", "返钱", "退回", "到账", "原路退", "refund"],
    "发票": ["开票", "票据", "抬头", "税号", "invoice"],
    "客服时间": ["工作时间", "营业时间", "在线时间", "几点", "上班", "下班", "休息"],
}


@dataclass(frozen=True)
class FaqDocument:
    item: dict
    vector: Counter[str]


class FaqService:
    def __init__(self, faq_path: Path) -> None:
        self.items = json.loads(faq_path.read_text(encoding="utf-8-sig"))
        self.documents = [FaqDocument(item=item, vector=self._build_item_vector(item)) for item in self.items]

    def search(self, message: str) -> dict | None:
        if self._looks_like_transaction_command(message):
            return None

        query_vector = self._vectorize(message)
        if not query_vector:
            return None

        best_item = None
        best_score = 0.0

        for document in self.documents:
            keyword_score = self._keyword_score(message, document.item.get("keywords", []))
            semantic_score = self._cosine_similarity(query_vector, document.vector)
            score = max(keyword_score, semantic_score)

            if score > best_score:
                best_item = document.item
                best_score = score

        if best_item is None or best_score < MIN_MATCH_SCORE:
            return None

        return {
            "answer": best_item["answer"],
            "intent": best_item.get("intent", "faq"),
            "score": round(min(best_score, 1.0), 2),
        }

    def _build_item_vector(self, item: dict) -> Counter[str]:
        text_parts = [item.get("question", ""), item.get("intent", "")]
        text_parts.extend(item.get("keywords", []))
        return self._vectorize(" ".join(text_parts))

    def _keyword_score(self, message: str, keywords: list[str]) -> float:
        if not keywords:
            return 0.0

        normalized = message.lower()
        hits = sum(1 for keyword in keywords if keyword.lower() in normalized)
        if hits == 0:
            return 0.0

        coverage = hits / len(keywords)
        return 0.55 + 0.35 * coverage

    def _vectorize(self, text: str) -> Counter[str]:
        normalized = self._normalize(text)
        tokens = self._tokens(normalized)
        expanded_tokens = self._expand_synonyms(normalized, tokens)
        return Counter(expanded_tokens)

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", "", text.lower())

    def _tokens(self, text: str) -> list[str]:
        tokens: list[str] = []
        tokens.extend(re.findall(r"[a-z0-9]+", text))
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
        tokens.extend(cjk_chars)
        tokens.extend(a + b for a, b in zip(cjk_chars, cjk_chars[1:]))
        tokens.extend(a + b + c for a, b, c in zip(cjk_chars, cjk_chars[1:], cjk_chars[2:]))
        return tokens

    def _expand_synonyms(self, text: str, tokens: list[str]) -> list[str]:
        expanded = list(tokens)
        for canonical, variants in DOMAIN_SYNONYMS.items():
            terms = [canonical, *variants]
            if any(term.lower() in text for term in terms):
                expanded.extend([canonical] * 3)
                expanded.extend(term.lower() for term in terms)
        return expanded

    def _cosine_similarity(self, left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0

        common = left.keys() & right.keys()
        dot_product = sum(left[token] * right[token] for token in common)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot_product / (left_norm * right_norm)

    def _looks_like_transaction_command(self, message: str) -> bool:
        text = self._normalize(message)
        refund_actions = ["我要退款", "我要退货", "申请退款", "申请退货", "取消订单"]
        refund_time_terms = ["多久", "到账", "什么时候", "几天", "时间", "退回", "原路"]
        if any(action in text for action in refund_actions):
            return not any(term in text for term in refund_time_terms)
        return False
