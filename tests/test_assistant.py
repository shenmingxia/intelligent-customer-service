import pytest

from app.schemas import ChatRequest
from app.services.assistant import CustomerServiceAssistant
from app.services.llm import LlmResult
from app.services.session_store import InMemorySessionStore, SessionOwnershipError


class FakeLlmService:
    def generate_reply(self, message, context, history):
        return LlmResult(reply=f"LLM 回复：{message}", confidence=0.8)


class DisabledLlmService:
    def generate_reply(self, message, context, history):
        return None


class FailingLlmService:
    def generate_reply(self, message, context, history):
        raise TimeoutError("LLM timed out")


def test_faq_refund_reply():
    assistant = CustomerServiceAssistant.from_default_files()
    response = assistant.handle(ChatRequest(user_id="test", message="退款多久到账"))
    assert response.intent == "refund_time"
    assert "工作日" in response.reply


def test_human_handoff():
    assistant = CustomerServiceAssistant.from_default_files()
    response = assistant.handle(ChatRequest(user_id="test", message="我要转人工"))
    assert response.need_human is True


def test_order_status_multi_turn_memory():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要查订单"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="A123456")
    )
    assert second.intent == "order_status_followup"
    assert second.context["order_id"] == "A123456"
    assert "顺丰速运" in second.reply
    assert "SF1234567890" in second.reply


def test_order_status_unknown_order():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要查订单"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="X999999")
    )
    assert second.intent == "order_status_followup"
    assert "没有查询到订单 X999999" in second.reply


def test_refund_multi_turn_slots():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要退款"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="订单号 B987654")
    )
    third = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="买错了")
    )
    assert second.context["pending_intent"] == "refund_reason"
    assert second.context["refund_status"] == "可申请售后"
    assert "89.90 元" in second.reply
    assert third.intent == "refund_reason_followup"
    assert third.context["order_id"] == "B987654"
    assert third.context["refund_reason"] == "买错了"
    assert "预计退款金额 89.90 元" in third.reply


def test_refund_unknown_order_keeps_waiting_for_order_id():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要退款"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="订单号 X999999")
    )
    assert second.intent == "refund_order_not_found"
    assert second.context["pending_intent"] == "refund"
    assert "没有查询到订单 X999999" in second.reply


def test_refund_unpaid_order_can_cancel_directly():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要退款"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="订单号 C202406")
    )
    assert second.intent == "refund_unpaid_cancel"
    assert "直接取消" in second.reply
    assert "pending_intent" not in second.context


def test_refund_expired_order_needs_human():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="test", message="我要退款"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="订单号 D111111")
    )
    assert second.intent == "refund_need_human"
    assert second.need_human is True
    assert "转接人工客服" in second.reply


def test_unknown_message_can_fallback_to_llm():
    assistant = CustomerServiceAssistant.from_default_files()
    assistant.llm = FakeLlmService()
    response = assistant.handle(ChatRequest(user_id="test", message="这款商品适合送长辈吗"))
    assert response.intent == "llm_answer"
    assert "LLM 回复" in response.reply


def test_llm_exception_falls_back_to_config_reply():
    assistant = CustomerServiceAssistant.from_default_files()
    assistant.llm = FailingLlmService()
    response = assistant.handle(ChatRequest(user_id="test", message="这款商品适合送长辈吗"))

    assert response.intent == "unknown"
    assert response.reply == assistant.config.fallback_reply


def test_session_is_bound_to_original_user():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="owner", message="我要查订单"))

    with pytest.raises(SessionOwnershipError):
        assistant.handle(
            ChatRequest(user_id="other", session_id=first.session_id, message="A123456")
        )


def test_in_memory_session_ttl_expires_state():
    assistant = CustomerServiceAssistant.from_default_files()
    assistant.llm = DisabledLlmService()
    assistant.session_store = InMemorySessionStore(ttl_seconds=0)
    first = assistant.handle(ChatRequest(user_id="test", message="我要查订单"))
    second = assistant.handle(
        ChatRequest(user_id="test", session_id=first.session_id, message="A123456")
    )

    assert second.intent != "order_status_followup"
    assert second.context["turn_count"] == "0"

def test_order_status_hides_order_from_non_owner():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="not-owner", message="我要查订单"))
    second = assistant.handle(
        ChatRequest(user_id="not-owner", session_id=first.session_id, message="A123456")
    )

    assert second.intent == "order_status_followup"
    assert "没有查询到订单 A123456" in second.reply
    assert "SF1234567890" not in second.reply


def test_refund_hides_order_from_non_owner():
    assistant = CustomerServiceAssistant.from_default_files()
    first = assistant.handle(ChatRequest(user_id="not-owner", message="我要退款"))
    second = assistant.handle(
        ChatRequest(user_id="not-owner", session_id=first.session_id, message="订单号 B987654")
    )

    assert second.intent == "refund_order_not_found"
    assert "89.90" not in second.reply

