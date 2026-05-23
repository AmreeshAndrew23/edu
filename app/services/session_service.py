from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.exam import Exam
from app.models.question import Question
from app.models.exam_session import ExamSession
from app.models.student_answer import StudentAnswer
from app.models.student import Student
from app.schemas.session_schema import (
    SessionStartRequest,
    SubmitAnswersRequest,
    SessionStartResponse,
    SessionResultResponse,
    QuestionPayload,
    AnswerResultItem,
)

DIFFICULTY_COUNTS: dict[str, int] = {
    "easy": 10,
    "medium": 15,
    "hard": 20,
}


async def start_session(db: AsyncSession, payload: SessionStartRequest) -> SessionStartResponse:
    """
    Difficulty-based random question selection:
      easy → 10 questions, medium → 15, hard → 20
    Questions are sampled randomly from those matching exam_id + difficulty_level.
    correct_option is NOT returned to the client.
    """

    student = await db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    exam = await db.get(Exam, payload.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    difficulty = payload.difficulty.lower()
    if difficulty not in DIFFICULTY_COUNTS:
        raise HTTPException(status_code=400, detail="difficulty must be easy, medium, or hard")

    count = DIFFICULTY_COUNTS[difficulty]

    questions = (await db.execute(
        select(Question)
        .where(
            Question.exam_id == payload.exam_id,
            Question.difficulty_level == difficulty,
        )
        .order_by(func.random())
        .limit(count)
    )).scalars().all()

    if not questions:
        raise HTTPException(
            status_code=404,
            detail=f"No {difficulty} questions found for this exam. Generate questions first.",
        )

    session = ExamSession(
        student_id=payload.student_id,
        exam_id=payload.exam_id,
        status="in_progress",
        total_questions=len(questions),
        started_at=datetime.utcnow(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionStartResponse(
        session_id=session.id,
        total_questions=session.total_questions,
        exam_id=session.exam_id,
        difficulty=difficulty,
        questions=[QuestionPayload.model_validate(q) for q in questions],
    )


async def submit_session(
    db: AsyncSession,
    session_id: int,
    payload: SubmitAnswersRequest,
) -> SessionResultResponse:
    """
    Score the student's answers, record each StudentAnswer row,
    and mark the session completed.
    """

    session = await db.get(ExamSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session is already submitted")

    # Fetch all questions for this session in one query
    question_ids = [a.question_id for a in payload.answers]
    q_result = await db.execute(
        select(Question).where(Question.id.in_(question_ids))
    )
    questions_by_id = {q.id: q for q in q_result.scalars().all()}

    correct_count = 0
    answer_rows: list[StudentAnswer] = []

    for item in payload.answers:
        question = questions_by_id.get(item.question_id)
        if not question:
            raise HTTPException(
                status_code=400,
                detail=f"Question {item.question_id} does not exist",
            )

        is_correct = (
            item.selected_option is not None
            and item.selected_option.upper() == question.correct_option.upper()
        )
        if is_correct:
            correct_count += 1

        answer_rows.append(
            StudentAnswer(
                session_id=session_id,
                question_id=item.question_id,
                selected_option=item.selected_option,
                is_correct=is_correct,
            )
        )

    db.add_all(answer_rows)

    score_pct = round((correct_count / session.total_questions) * 100, 2) if session.total_questions else 0.0

    session.status = "completed"
    session.correct_count = correct_count
    session.score_percentage = score_pct
    session.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    return await get_session_results(db, session_id)


async def get_session_results(db: AsyncSession, session_id: int) -> SessionResultResponse:
    """Return full results with correct options and explanations revealed."""

    session = await db.get(ExamSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch all answers for this session with their questions
    ans_result = await db.execute(
        select(StudentAnswer).where(StudentAnswer.session_id == session_id)
    )
    student_answers = ans_result.scalars().all()

    question_ids = [a.question_id for a in student_answers]
    q_result = await db.execute(
        select(Question).where(Question.id.in_(question_ids))
    )
    questions_by_id = {q.id: q for q in q_result.scalars().all()}

    result_items = [
        AnswerResultItem(
            question_id=ans.question_id,
            question_text=questions_by_id[ans.question_id].question_text,
            option_a=questions_by_id[ans.question_id].option_a,
            option_b=questions_by_id[ans.question_id].option_b,
            option_c=questions_by_id[ans.question_id].option_c,
            option_d=questions_by_id[ans.question_id].option_d,
            correct_option=questions_by_id[ans.question_id].correct_option,
            explanation=questions_by_id[ans.question_id].explanation,
            selected_option=ans.selected_option,
            is_correct=ans.is_correct,
        )
        for ans in student_answers
        if ans.question_id in questions_by_id
    ]

    return SessionResultResponse(
        session_id=session.id,
        status=session.status,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        score_percentage=session.score_percentage,
        started_at=session.started_at,
        completed_at=session.completed_at,
        answers=result_items,
    )
