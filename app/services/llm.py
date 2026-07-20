from __future__ import annotations

import os
import logging
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 1


@dataclass
class LlmResult:
    reply: str
    confidence: float = 0.72


class LlmService:
    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.timeout_seconds = _read_float_env("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        self.max_retries = _read_int_env("OPENAI_MAX_RETRIES", DEFAULT_MAX_RETRIES)
        self.enabled = bool(self.api_key)
        self._client = None

    def generate_reply(
        self,
        message: str,
        context: dict[str, str],
        history: list[dict[str, str]],
    ) -> LlmResult | None:
        if not self.enabled:
            return None

        try:
            client = self._get_client()
            prompt = self._build_prompt(message, context, history)

            response = client.responses.create(
                model=self.model,
                reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")},
                input=prompt,
                timeout=self.timeout_seconds,
            )
            reply = getattr(response, "output_text", "").strip()
        except Exception as exc:
            logger.warning("LLM fallback failed; using rule fallback. error=%s", exc)
            return None

        if not reply:
            return None
        return LlmResult(reply=reply)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                max_retries=self.max_retries,
                timeout=self.timeout_seconds,
            )
        return self._client

    def _build_prompt(
        self,
        message: str,
        context: dict[str, str],
        history: list[dict[str, str]],
    ) -> str:
        recent_history = history[-8:]
        return f"""
你是一个中文智能客服助手。请用简洁、礼貌、可执行的方式回答用户。

规则：
1. 不要编造订单、退款、物流的真实状态；如果需要业务数据，请提示用户提供订单号或转人工。
2. 如果问题涉及投诉、强烈不满、法律风险、隐私信息或高金额售后，建议转人工。
3. 回答应尽量短，默认 1-3 句话。
4. 如果上下文里有 pending_intent 或 order_id，请结合上下文继续对话。

当前上下文：{context}
最近对话：{recent_history}
用户最新消息：{message}
""".strip()


def _read_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
