from pathlib import Path

from fastapi import APIRouter, Body

from app.schemas import FeedbackRequest, FeedbackResponse
from app.services.admin_store import AdminStore

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"

router = APIRouter(tags=["feedback"])
store = AdminStore(DATA_DIR)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit answer feedback",
    description="Submit useful/not useful feedback for one assistant answer.",
)
def submit_feedback(feedback: FeedbackRequest = Body(...)) -> FeedbackResponse:
    store.add_feedback(feedback)
    return FeedbackResponse()
