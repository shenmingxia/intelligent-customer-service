from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "u001",
                    "message": "退款多久到账",
                    "session_id": None,
                }
            ]
        }
    )

    user_id: str = Field(default="guest", description="用户标识，用于生成默认会话 ID")
    message: str = Field(..., min_length=1, description="用户消息，不能为空")
    session_id: str | None = Field(
        default=None,
        description="会话 ID。首次请求可为空；后续请求传入响应中的 session_id 以保持多轮上下文。",
    )


class ChatResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "reply": "退款审核通过后，通常 1-3 个工作日原路退回。银行或支付平台处理时间可能略有差异。",
                    "intent": "refund_time",
                    "confidence": 0.5,
                    "need_human": False,
                    "session_id": "u001-xxxxxxxx",
                    "context": {"turn_count": "0"},
                }
            ]
        }
    )

    reply: str = Field(description="客服回复内容")
    intent: str = Field(description="命中的意图或处理分支，例如 greeting、order_status、refund、human_handoff、llm_answer")
    confidence: float = Field(description="置信度，范围通常为 0 到 1")
    need_human: bool = Field(default=False, description="是否建议或已触发人工客服转接")
    session_id: str = Field(description="当前会话 ID，调用方应保存并在后续请求中继续传入")
    context: dict[str, str] = Field(
        default_factory=dict,
        description="当前会话上下文，例如订单号、退款状态、待补充意图、对话轮数等",
    )


class FaqItem(BaseModel):
    intent: str = Field(..., min_length=1, description="FAQ ????????")
    question: str = Field(..., min_length=1, description="FAQ ????")
    keywords: list[str] = Field(default_factory=list, description="????????")
    answer: str = Field(..., min_length=1, description="FAQ ??")


class AdminSettings(BaseModel):
    human_keywords: list[str] = Field(default_factory=list, description="??????????")
    fallback_reply: str = Field(..., min_length=1, description="????")

