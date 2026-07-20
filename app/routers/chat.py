from fastapi import APIRouter, Body, HTTPException, status

from app.schemas import ChatRequest, ChatResponse
from app.services.assistant import CustomerServiceAssistant
from app.services.session_store import SessionOwnershipError

router = APIRouter(tags=["chat"])
assistant = CustomerServiceAssistant.from_default_files()


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
    try:
        return assistant.handle(request)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="session_id does not belong to this user",
        ) from exc
