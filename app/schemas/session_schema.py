from datetime import datetime
from pydantic import BaseModel, ConfigDict


# ── Request ──────────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    """
    Student initiates a model exam session.
    difficulty controls how many questions are served:
      easy → 10 questions, medium → 15, hard → 20
    Optional topic_id narrows questions to a single topic (used by Rapid Revision / Weak Area).
    """
    student_id: int
    exam_id: int
    difficulty: str = "medium"   # "easy" | "medium" | "hard"
    topic_id: int | None = None


class AnswerItem(BaseModel):
    question_id: int
    selected_option: str | None = None   # 'A'|'B'|'C'|'D' or null if skipped


class SubmitAnswersRequest(BaseModel):
    answers: list[AnswerItem]


# ── Question payload (served without revealing correct_option) ────────────────

class QuestionPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    difficulty_level: str | None
    topic_id: int


# ── Responses ────────────────────────────────────────────────────────────────

class SessionStartResponse(BaseModel):
    session_id: int
    total_questions: int
    exam_id: int
    difficulty: str
    questions: list[QuestionPayload]


class AnswerResultItem(BaseModel):
    question_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: str | None
    selected_option: str | None
    is_correct: bool


class SessionResultResponse(BaseModel):
    session_id: int
    status: str
    total_questions: int
    correct_count: int | None
    score_percentage: float | None
    started_at: datetime
    completed_at: datetime | None
    answers: list[AnswerResultItem]
