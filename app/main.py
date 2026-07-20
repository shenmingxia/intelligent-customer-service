from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.errors import setup_exception_handlers
from app.routers.admin import router as admin_router
from app.routers.chat import router as chat_router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="智能客服后端接口",
    description=(
        "智能客服助手接口文档。\n\n"
        "当前后端提供聊天、健康检查和网页客服窗口能力。"
        "Boss 直聘自动打招呼/招呼语生成相关接口已移除。"
    ),
    version="0.1.0",
    contact={"name": "Smart Customer Service"},
    openapi_tags=[
        {"name": "chat", "description": "智能客服聊天接口，支持多轮上下文。"},
        {"name": "system", "description": "系统状态与页面入口。"},
    ],
)

setup_exception_handlers(app)
app.include_router(chat_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get(
    "/",
    tags=["system"],
    summary="网页客服窗口",
    description="返回前端聊天页面。页面会调用 `/api/chat` 并保存 `session_id` 来维持多轮对话。",
)
def chat_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get(
    "/admin",
    tags=["system"],
    summary="管理员后台",
    description="返回 FAQ 和人工转接规则管理页面。",
)
def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


@app.get(
    "/health",
    tags=["system"],
    summary="健康检查",
    description="检查后端服务是否正常运行。正常时返回 `{\"status\":\"ok\"}`。",
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
