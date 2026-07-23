from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.schemas import AdminSettings, FaqItem, FeedbackStatusUpdate, FeedbackTopItem, SensitiveWordItem
from app.services.admin_store import AdminStore
from app.services.assistant import AssistantConfig
from app.services.faq import FaqService
from app.services.safety import SensitiveWordFilter

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"

router = APIRouter(prefix="/admin", tags=["admin"])
store = AdminStore(DATA_DIR)


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected_token = os.getenv("ADMIN_TOKEN")
    if expected_token and x_admin_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin token",
        )


def refresh_assistant() -> None:
    from app.routers.chat import assistant

    config_data = json.loads((DATA_DIR / "config.json").read_text(encoding="utf-8-sig"))
    assistant.faq = FaqService(DATA_DIR / "faq.json")
    assistant.config = AssistantConfig(**config_data)
    assistant.sensitive_filter = SensitiveWordFilter(DATA_DIR / "sensitive_words.json")


@router.get("/faq", response_model=list[FaqItem], summary="List FAQ items")
def list_faq(_: None = Depends(require_admin_token)) -> list[dict]:
    return store.list_faq()


@router.post("/faq", response_model=FaqItem, status_code=status.HTTP_201_CREATED, summary="Create or replace FAQ")
def create_faq(item: FaqItem, _: None = Depends(require_admin_token)) -> dict:
    saved_item = store.upsert_faq(item)
    refresh_assistant()
    return saved_item


@router.put("/faq/{intent}", response_model=FaqItem, summary="Update FAQ by intent")
def update_faq(intent: str, item: FaqItem, _: None = Depends(require_admin_token)) -> dict:
    saved_item = store.upsert_faq(item.model_copy(update={"intent": intent}))
    refresh_assistant()
    return saved_item


@router.delete("/faq/{intent}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete FAQ by intent")
def delete_faq(intent: str, _: None = Depends(require_admin_token)) -> None:
    deleted = store.delete_faq(intent)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ item not found")
    refresh_assistant()


@router.get("/settings", response_model=AdminSettings, summary="Get handoff settings")
def get_settings(_: None = Depends(require_admin_token)) -> dict:
    return store.get_settings()


@router.put("/settings", response_model=AdminSettings, summary="Update handoff settings")
def update_settings(settings: AdminSettings, _: None = Depends(require_admin_token)) -> dict:
    saved_settings = store.update_settings(settings)
    refresh_assistant()
    return saved_settings


@router.get("/feedback/top", response_model=list[FeedbackTopItem], summary="Top downvoted questions")
def top_feedback(_: None = Depends(require_admin_token)) -> list[dict]:
    return store.top_downvoted_questions(limit=10)


@router.put("/feedback/status", summary="Update feedback optimization status")
def update_feedback_status(payload: FeedbackStatusUpdate, _: None = Depends(require_admin_token)) -> dict:
    return store.update_feedback_status(payload.question, payload.status)


@router.get("/sensitive-words", response_model=list[SensitiveWordItem], summary="List sensitive words")
def list_sensitive_words(_: None = Depends(require_admin_token)) -> list[dict]:
    return store.list_sensitive_words()


@router.post(
    "/sensitive-words",
    response_model=SensitiveWordItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create sensitive word",
)
def create_sensitive_word(item: SensitiveWordItem, _: None = Depends(require_admin_token)) -> dict:
    saved_item = store.upsert_sensitive_word(item)
    refresh_assistant()
    return saved_item


@router.put("/sensitive-words/{word}", response_model=SensitiveWordItem, summary="Update sensitive word")
def update_sensitive_word(word: str, item: SensitiveWordItem, _: None = Depends(require_admin_token)) -> dict:
    saved_item = store.update_sensitive_word(word, item)
    if not saved_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensitive word not found")
    refresh_assistant()
    return saved_item


@router.delete("/sensitive-words/{word}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete sensitive word")
def delete_sensitive_word(word: str, _: None = Depends(require_admin_token)) -> None:
    deleted = store.delete_sensitive_word(word)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensitive word not found")
    refresh_assistant()
