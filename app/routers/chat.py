from fastapi import APIRouter, Body

from app.schemas import ChatRequest, ChatResponse
from app.services.assistant import CustomerServiceAssistant

router = APIRouter(tags=["chat"])
assistant = CustomerServiceAssistant.from_default_files()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="智能客服聊天",
    description=(
        "发送用户消息并返回智能客服回复。支持 FAQ 匹配、简单意图识别、"
        "订单查询、退款多轮对话、人工客服转接，以及配置 OpenAI API Key 后的大模型兜底回复。\n\n"
        "首次调用可以不传 `session_id` 或传 `null`；后续调用建议带上响应中的 `session_id`，"
        "用于保持订单号、退款原因等多轮上下文。"
    ),
    response_description="智能客服回复结果",
)
def chat(
    request: ChatRequest = Body(
        examples=[
            {
                "summary": "普通问答",
                "description": "咨询退款到账时间。",
                "value": {
                    "user_id": "u001",
                    "message": "退款多久到账",
                    "session_id": None,
                },
            },
            {
                "summary": "订单查询",
                "description": "首次发起订单/物流查询。",
                "value": {
                    "user_id": "u001",
                    "message": "我要查订单",
                    "session_id": None,
                },
            },
            {
                "summary": "多轮补充订单号",
                "description": "带上上一轮返回的 session_id，继续补充订单号。",
                "value": {
                    "user_id": "u001",
                    "message": "A123456",
                    "session_id": "u001-xxxxxxxx",
                },
            },
        ],
    ),
) -> ChatResponse:
    return assistant.handle(request)
