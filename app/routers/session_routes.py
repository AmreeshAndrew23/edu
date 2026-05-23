from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.session_schema import (
    SessionStartRequest,
    SessionStartResponse,
    SubmitAnswersRequest,
    SessionResultResponse,
)
from app.services.session_service import start_session, submit_session, get_session_results

router = APIRouter(prefix="/sessions", tags=["Exam Sessions"])


@router.post("/start", response_model=SessionStartResponse)
async def start_exam_session(
    payload: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a model exam session.

    Selection rules (blueprint-driven):
    - exam_id only               → full exam (all subjects + all topics)
    - exam_id + subject_id       → one subject, all its topics in that exam
    - exam_id + subject_id + topic_id → single topic only

    Returns session_id + question list (correct options hidden).
    """
    return await start_session(db, payload)


@router.post("/{session_id}/submit", response_model=SessionResultResponse)
async def submit_exam_session(
    session_id: int,
    payload: SubmitAnswersRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit answers for a session. Returns score + per-question breakdown
    with correct options and explanations revealed.
    """
    return await submit_session(db, session_id, payload)


@router.get("/{session_id}/results", response_model=SessionResultResponse)
async def get_exam_results(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve results for an already-submitted session."""
    return await get_session_results(db, session_id)
