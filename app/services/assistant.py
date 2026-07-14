from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.schemas import ChatRequest, ChatResponse
from app.services.faq import FaqService
from app.services.intent import IntentClassifier
from app.services.llm import LlmService
from app.services.order import OrderService
from app.services.policy import PolicyService


@dataclass
class AssistantConfig:
    human_keywords: list[str]
    fallback_reply: str


@dataclass
class ConversationState:
    session_id: str
    pending_intent: str | None = None
    slots: dict[str, str] | None = None
    turns: list[dict[str, str]] | None = None

    def __post_init__(self) -> None:
        self.slots = self.slots or {}
        self.turns = self.turns or []


class CustomerServiceAssistant:
    def __init__(
        self,
        faq: FaqService,
        intent_classifier: IntentClassifier,
        policy: PolicyService,
        config: AssistantConfig,
        order_service: OrderService,
        llm: LlmService | None = None,
    ) -> None:
        self.faq = faq
        self.intent_classifier = intent_classifier
        self.policy = policy
        self.config = config
        self.order_service = order_service
        self.llm = llm or LlmService()
        self.sessions: dict[str, ConversationState] = {}

    @classmethod
    def from_default_files(cls) -> "CustomerServiceAssistant":
        root = Path(__file__).resolve().parents[2]
        config_data = json.loads((root / "data" / "config.json").read_text(encoding="utf-8-sig"))
        return cls(
            faq=FaqService(root / "data" / "faq.json"),
            intent_classifier=IntentClassifier(),
            policy=PolicyService(),
            config=AssistantConfig(**config_data),
            order_service=OrderService(root / "data" / "orders.json"),
        )

    def handle(self, request: ChatRequest) -> ChatResponse:
        message = request.message.strip()
        state = self._get_state(request)

        if self.policy.should_transfer_to_human(message, self.config.human_keywords):
            response = ChatResponse(
                reply="我已经为您转接人工客服，请稍等。",
                intent="human_handoff",
                confidence=1.0,
                need_human=True,
                session_id=state.session_id,
                context=self._context(state),
            )
            self._remember(state, message, response.reply)
            return response

        follow_up = self._handle_follow_up(state, message)
        if follow_up is not None:
            self._remember(state, message, follow_up.reply)
            return follow_up

        faq_match = self.faq.search(message)
        if faq_match is not None:
            response = ChatResponse(
                reply=faq_match["answer"],
                intent=faq_match["intent"],
                confidence=faq_match["score"],
                session_id=state.session_id,
                context=self._context(state),
            )
            self._remember(state, message, response.reply)
            return response

        intent, confidence = self.intent_classifier.classify(message)
        if intent == "unknown":
            llm_response = self._reply_with_llm(message, state)
            if llm_response is not None:
                self._remember(state, message, llm_response.reply)
                return llm_response

        reply = self._reply_by_intent(intent, state)
        response = ChatResponse(
            reply=reply,
            intent=intent,
            confidence=confidence,
            session_id=state.session_id,
            context=self._context(state),
        )
        self._remember(state, message, response.reply)
        return response

    def _get_state(self, request: ChatRequest) -> ConversationState:
        session_id = request.session_id or f"{request.user_id}-{uuid4().hex[:8]}"
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationState(session_id=session_id)
        return self.sessions[session_id]

    def _handle_follow_up(self, state: ConversationState, message: str) -> ChatResponse | None:
        if state.pending_intent not in {"order_status", "refund", "refund_reason"}:
            return None

        order_id = self._extract_order_id(message)
        if order_id:
            state.slots["order_id"] = order_id

        if state.pending_intent == "order_status" and order_id:
            state.pending_intent = None
            reply = self._build_order_status_reply(order_id)
            return ChatResponse(
                reply=reply,
                intent="order_status_followup",
                confidence=0.9,
                session_id=state.session_id,
                context=self._context(state),
            )

        if state.pending_intent == "refund" and order_id:
            refund_response = self._build_refund_order_response(state, order_id)
            if refund_response is not None:
                return refund_response

            state.pending_intent = "refund_reason"
            reply = self._build_refund_reason_prompt(order_id)
            return ChatResponse(
                reply=reply,
                intent="refund_followup",
                confidence=0.88,
                session_id=state.session_id,
                context=self._context(state),
            )

        if state.pending_intent == "refund_reason" and "order_id" in state.slots:
            reason = message[:80]
            state.slots["refund_reason"] = reason
            state.pending_intent = None
            reply = self._build_refund_submit_reply(state.slots["order_id"], reason)
            return ChatResponse(
                reply=reply,
                intent="refund_reason_followup",
                confidence=0.86,
                session_id=state.session_id,
                context=self._context(state),
            )

        hint = "请提供订单号，例如：A123456。"
        return ChatResponse(
            reply=hint,
            intent=f"{state.pending_intent}_missing_order_id",
            confidence=0.7,
            session_id=state.session_id,
            context=self._context(state),
        )

    def _reply_by_intent(self, intent: str, state: ConversationState) -> str:
        replies = {
            "greeting": "您好，我是智能客服助手。请问有什么可以帮您？",
            "order_status": "请提供您的订单号，我可以帮您查询订单状态。",
            "refund": "请提供订单号和退款原因，我会帮您查看退款规则。",
            "complaint": "很抱歉给您带来不好的体验。请描述具体问题，我会优先为您处理。",
        }
        if intent in {"order_status", "refund"}:
            state.pending_intent = intent
        return replies.get(intent, self.config.fallback_reply)

    def _build_order_status_reply(self, order_id: str) -> str:
        order = self.order_service.find_by_id(order_id)
        if order is None:
            return f"没有查询到订单 {order_id}。请确认订单号是否正确，或输入“转人工”让客服帮您核对。"

        tracking = "暂无物流单号"
        if order.tracking_company and order.tracking_number:
            tracking = f"{order.tracking_company} {order.tracking_number}"

        return (
            f"订单 {order.order_id} 当前状态：{order.status}。"
            f"物流信息：{tracking}。"
            f"预计送达：{order.estimated_delivery}。"
            f"订单金额：{order.amount:.2f} 元。"
        )

    def _build_refund_order_response(
        self,
        state: ConversationState,
        order_id: str,
    ) -> ChatResponse | None:
        order = self.order_service.find_by_id(order_id)
        if order is None:
            state.slots.pop("order_id", None)
            return ChatResponse(
                reply=f"没有查询到订单 {order_id}。请确认订单号是否正确，或输入“转人工”让客服帮您核对。",
                intent="refund_order_not_found",
                confidence=0.84,
                session_id=state.session_id,
                context=self._context(state),
            )

        state.slots["order_status"] = order.status
        state.slots["refund_status"] = order.refund_status
        state.slots["refund_amount"] = f"{order.amount:.2f}"

        if "未付款" in order.refund_status:
            state.pending_intent = None
            return ChatResponse(
                reply=(
                    f"订单 {order.order_id} 当前状态：{order.status}。"
                    f"{order.refund_tip}订单金额 {order.amount:.2f} 元，您可以在订单详情页直接取消。"
                ),
                intent="refund_unpaid_cancel",
                confidence=0.9,
                session_id=state.session_id,
                context=self._context(state),
            )

        if not order.refundable:
            state.pending_intent = None
            return ChatResponse(
                reply=(
                    f"订单 {order.order_id} 当前状态：{order.status}，退款状态：{order.refund_status}。"
                    f"{order.refund_tip}我建议为您转接人工客服继续处理。"
                ),
                intent="refund_need_human",
                confidence=0.9,
                need_human=True,
                session_id=state.session_id,
                context=self._context(state),
            )

        return None

    def _build_refund_reason_prompt(self, order_id: str) -> str:
        order = self.order_service.find_by_id(order_id)
        if order is None:
            return f"已记录退款订单 {order_id}。请再补充退款原因，我会帮您整理售后申请。"
        return (
            f"已查询到订单 {order.order_id}，当前状态：{order.status}，"
            f"退款状态：{order.refund_status}，可申请金额：{order.amount:.2f} 元。"
            f"{order.refund_tip}请补充退款原因。"
        )

    def _build_refund_submit_reply(self, order_id: str, reason: str) -> str:
        order = self.order_service.find_by_id(order_id)
        if order is None:
            return f"已记录退款原因：{reason}。但没有查询到订单 {order_id}，建议转人工核对。"
        return (
            f"已记录退款原因：{reason}。"
            f"订单 {order.order_id} 的售后申请已进入预处理流程，"
            f"预计退款金额 {order.amount:.2f} 元，当前退款状态：{order.refund_status}。"
        )

    def _reply_with_llm(self, message: str, state: ConversationState) -> ChatResponse | None:
        result = self.llm.generate_reply(
            message=message,
            context=self._context(state),
            history=state.turns,
        )
        if result is None:
            return None
        return ChatResponse(
            reply=result.reply,
            intent="llm_answer",
            confidence=result.confidence,
            session_id=state.session_id,
            context=self._context(state),
        )

    def _remember(self, state: ConversationState, user_message: str, assistant_reply: str) -> None:
        state.turns.append({"role": "user", "content": user_message})
        state.turns.append({"role": "assistant", "content": assistant_reply})
        state.turns = state.turns[-12:]

    def _context(self, state: ConversationState) -> dict[str, str]:
        context = dict(state.slots)
        if state.pending_intent:
            context["pending_intent"] = state.pending_intent
        context["turn_count"] = str(len(state.turns) // 2)
        return context

    def _extract_order_id(self, message: str) -> str | None:
        match = re.search(r"\b[A-Za-z]{0,3}\d{5,18}\b", message)
        return match.group(0).upper() if match else None
