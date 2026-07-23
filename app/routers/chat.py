import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, status

from app.schemas import ChatRequest, ChatResponse
from app.services.assistant import CustomerServiceAssistant
from app.services.session_store import SessionOwnershipError

router = APIRouter(tags=["chat"])
assistant = CustomerServiceAssistant.from_default_files()
executor = ThreadPoolExecutor(max_workers=int(os.getenv("CHAT_WORKER_THREADS", "8")))


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Smart customer service chat",
    description=(
        "Send a user message and receive a customer-service reply. Supports FAQ matching, "
        "intent classification, order lookup, refund follow-up, human handoff, and LLM fallback.\n\n"
        "Omit session_id on the first request; reuse the returned session_id for multi-turn context."
    ),
    response_description="Customer-service reply result",
)
def chat(
    request: ChatRequest = Body(
        examples=[
            {
                "summary": "FAQ question",
                "description": "Ask about refund timing.",
                "value": {
                    "user_id": "u001",
                    "message": "退款多久到账",
                    "session_id": None,
                },
            },
            {
                "summary": "Order lookup",
                "description": "Start an order or logistics lookup.",
                "value": {
                    "user_id": "u001",
                    "message": "我要查订单",
                    "session_id": None,
                },
            },
            {
                "summary": "Order ID follow-up",
                "description": "Reuse the previous session_id and provide the order ID.",
                "value": {
                    "user_id": "u001",
                    "message": "A123456",
                    "session_id": "u001-xxxxxxxx",
                },
            },
        ],
    ),
) -> ChatResponse:
    request = _ensure_session_id(request)
    try:
        future = executor.submit(assistant.handle, request)
        return future.result(timeout=_answer_timeout_seconds())
    except TimeoutError:
        return assistant.build_timeout_response(request)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="session_id does not belong to this user",
        ) from exc


def _answer_timeout_seconds() -> float:
    try:
        return float(os.getenv("ANSWER_TIMEOUT_SECONDS", "3"))
    except ValueError:
        return 3.0


def _ensure_session_id(request: ChatRequest) -> ChatRequest:
    if request.session_id:
        return request
    return request.model_copy(update={"session_id": f"{request.user_id}-{uuid4().hex[:8]}"})
