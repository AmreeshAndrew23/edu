import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.exam import Exam
from app.models.exam_blueprint import ExamBlueprint
from app.models.topic import Topic
from app.models.subject import Subject
from app.models.question import Question
from app.models.exam_session import ExamSession
from app.models.student_answer import StudentAnswer
from app.models.student import Student
from app.models.ai_usage_log import AiUsageLog
from app.schemas.session_schema import (
    SessionStartRequest,
    SubmitAnswersRequest,
    SessionStartResponse,
    SessionResultResponse,
    QuestionPayload,
    AnswerResultItem,
)

logger = logging.getLogger(__name__)

DIFFICULTY_COUNTS: dict[str, int] = {
    "easy": 10,
    "medium": 15,
    "hard": 20,
}


async def get_adaptive_difficulty(db: AsyncSession, student_id: int) -> str:
    """
    Determine recommended difficulty based on last 3 completed sessions.
    - Easy: < 50% stay on Easy, >= 70% move to Medium
    - Medium: < 50% go to Easy, >= 70% go to Hard
    - Hard: < 60% go to Medium, >= 75% stay on Hard
    """
    # Get last 3 completed sessions
    recent = (await db.execute(
        select(ExamSession)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
        )
        .order_by(ExamSession.completed_at.desc())
        .limit(3)
    )).scalars().all()

    if not recent:
        return "easy"

    # Calculate average score of recent sessions
    avg_score = sum(s.score_percentage or 0 for s in recent) / len(recent)
    current_diff = recent[0].difficulty_level or "easy"

    logger.info(f"Adaptive difficulty: student_id={student_id}, avg_score={avg_score:.1f}%, current={current_diff}")

    if current_diff == "easy":
        return "medium" if avg_score >= 70 else "easy"
    elif current_diff == "medium":
        if avg_score < 50:
            return "easy"
        return "hard" if avg_score >= 70 else "medium"
    else:  # hard
        if avg_score < 60:
            return "medium"
        return "hard"


async def _ensure_questions(
    db: AsyncSession,
    exam: Exam,
    difficulty: str,
    topic_id: int | None = None,
) -> None:
    """Generate questions via OpenAI for topics in this exam that are below blueprint quota.
    Pass topic_id to restrict generation to that topic only (much faster for topic drills).
    Falls back to any available difficulty if the exact one isn't found.
    """
    from app.services.question_service import generate_questions

    logger.info(f"_ensure_questions: exam_id={exam.id}, difficulty={difficulty}, topic_id={topic_id}")

    # First try exact difficulty match
    bp_query = (
        select(ExamBlueprint, Topic, Subject)
        .join(Topic, ExamBlueprint.topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(
            ExamBlueprint.exam_id == exam.id,
            ExamBlueprint.difficulty_level == difficulty,
        )
    )
    if topic_id:
        bp_query = bp_query.where(ExamBlueprint.topic_id == topic_id)

    rows = (await db.execute(bp_query)).all()
    logger.info(f"  Found {len(rows)} blueprints for exam_id={exam.id}, difficulty={difficulty}")

    # If no exact match, try ANY difficulty for this exam/topic
    if not rows and topic_id:
        logger.info(f"  No exact difficulty match, falling back to any difficulty for topic_id={topic_id}")
        bp_query = (
            select(ExamBlueprint, Topic, Subject)
            .join(Topic, ExamBlueprint.topic_id == Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(
                ExamBlueprint.exam_id == exam.id,
                ExamBlueprint.topic_id == topic_id,
            )
        )
        rows = (await db.execute(bp_query)).all()
        logger.info(f"  Found {len(rows)} blueprints with any difficulty")

    for bp, topic, subject in rows:
        existing = (await db.execute(
            select(func.count()).select_from(Question).where(
                Question.exam_id == exam.id,
                Question.topic_id == topic.id,
                Question.difficulty_level == difficulty,
            )
        )).scalar() or 0

        # Generate 2x the blueprint requirement for variety
        needed = max(bp.expected_questions * 2 - existing, 0)
        if needed <= 0:
            continue

        logger.info("Auto-generating %d %s questions for topic '%s' (need %d beyond blueprint)", needed, difficulty, topic.topic_name, bp.expected_questions)
        try:
            generated, usage = await generate_questions(
                exam_name=exam.exam_name,
                subject_name=subject.name,
                topic_name=topic.topic_name,
                difficulty=difficulty,
                count=needed,
            )
        except Exception as exc:
            logger.error("Question generation failed for topic '%s': %s", topic.topic_name, exc)
            continue  # skip this topic, don't abort everything

        db.add(AiUsageLog(
            endpoint="question_generation",
            model="gpt-4o-mini",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=round(
                (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1_000_000, 6
            ),
            context=f"{topic.topic_name} | {difficulty} | {exam.exam_name}",
        ))

        required = {"question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"}
        for q in generated:
            if not required.issubset(q.keys()):
                continue
            db.add(Question(
                exam_id=exam.id,
                topic_id=topic.id,
                question_text=q["question_text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_option=q["correct_option"].upper(),
                explanation=q.get("explanation"),
                difficulty_level=difficulty,
            ))

    await db.commit()


async def start_session(db: AsyncSession, payload: SessionStartRequest) -> SessionStartResponse:
    logger.info(f"start_session: student_id={payload.student_id}, exam_id={payload.exam_id}, subject_id={payload.subject_id}, topic_id={payload.topic_id}, count={payload.count}")

    student = await db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    exam = await db.get(Exam, payload.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    logger.info(f"  Exam: {exam.exam_name} {exam.exam_year}")

    # Use adaptive difficulty if not specified
    if payload.difficulty:
        difficulty = payload.difficulty.lower()
    else:
        difficulty = await get_adaptive_difficulty(db, payload.student_id)
        logger.info(f"  Using adaptive difficulty: {difficulty}")

    if difficulty not in DIFFICULTY_COUNTS:
        raise HTTPException(status_code=400, detail="difficulty must be easy, medium, or hard")

    count = payload.count if payload.count else DIFFICULTY_COUNTS[difficulty]
    logger.info(f"  Difficulty: {difficulty}, Count: {count}")

    # For topic-specific sessions, use the blueprint's difficulty (not the client-supplied value).
    # Most topics are "medium" or "hard" in the blueprint; the frontend always sends "easy",
    # so without this override no blueprint would match and no questions would be generated.
    if payload.topic_id:
        bp_row = (await db.execute(
            select(ExamBlueprint).where(
                ExamBlueprint.exam_id == payload.exam_id,
                ExamBlueprint.topic_id == payload.topic_id,
            )
        )).scalar_one_or_none()
        if bp_row and bp_row.difficulty_level:
            difficulty = bp_row.difficulty_level

    q_filters = [
        Question.exam_id == payload.exam_id,
        Question.difficulty_level == difficulty,
    ]
    if payload.topic_id:
        q_filters.append(Question.topic_id == payload.topic_id)
    elif payload.subject_id:
        q_filters.append(
            Question.topic_id.in_(
                select(Topic.id).where(Topic.subject_id == payload.subject_id)
            )
        )

    seen_sq = (
        select(StudentAnswer.question_id)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .where(ExamSession.student_id == payload.student_id)
        .distinct()
    )

    questions = (await db.execute(
        select(Question)
        .where(*q_filters, Question.id.notin_(seen_sq))
        .distinct(Question.id)
        .order_by(Question.id, func.random())
        .limit(count)
    )).scalars().all()

    if not questions:
        logger.info("No unseen questions — generating more for exam_id=%d topic_id=%s difficulty=%s",
                    payload.exam_id, payload.topic_id, difficulty)
        await _ensure_questions(db, exam, difficulty, topic_id=payload.topic_id)
        questions = (await db.execute(
            select(Question)
            .where(*q_filters, Question.id.notin_(seen_sq))
            .distinct(Question.id)
            .order_by(Question.id, func.random())
            .limit(count)
        )).scalars().all()

    if not questions:
        # All questions in pool already seen — repeat from full pool
        questions = (await db.execute(
            select(Question).where(*q_filters).distinct(Question.id).order_by(Question.id, func.random()).limit(count)
        )).scalars().all()

    if not questions:
        raise HTTPException(status_code=503, detail="No blueprints found for this exam — seed may not have run yet.")

    session = ExamSession(
        student_id=payload.student_id,
        exam_id=payload.exam_id,
        subject_id=payload.subject_id,
        topic_id=payload.topic_id,
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
    and mark the session completed. Idempotent — retries don't duplicate answers.
    """

    session = await db.get(ExamSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "in_progress":
        # Already submitted — return cached results instead of failing
        return await get_session_results(db, session_id)

    # Fetch all questions for this session in one query
    question_ids = [a.question_id for a in payload.answers]
    q_result = await db.execute(
        select(Question).where(Question.id.in_(question_ids))
    )
    questions_by_id = {q.id: q for q in q_result.scalars().all()}

    # Check for existing answers (idempotency — delete old ones if resubmitting)
    existing = (await db.execute(
        select(StudentAnswer.question_id).where(StudentAnswer.session_id == session_id)
    )).scalars().all()
    existing_qids = set(existing)

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

        # Skip if answer already exists for this question in this session
        if item.question_id not in existing_qids:
            answer_rows.append(
                StudentAnswer(
                    session_id=session_id,
                    question_id=item.question_id,
                    selected_option=item.selected_option,
                    is_correct=is_correct,
                )
            )

    # Only add new answers, don't duplicate
    if answer_rows:
        db.add_all(answer_rows)

    score_pct = round((correct_count / session.total_questions) * 100, 2) if session.total_questions else 0.0

    session.status = "completed"
    session.correct_count = correct_count
    session.score_percentage = score_pct
    session.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    # Update student's adaptive difficulty based on this session's performance
    student = await db.get(Student, session.student_id)
    if student:
        next_difficulty = await get_adaptive_difficulty(db, session.student_id)
        if next_difficulty != student.current_difficulty:
            student.current_difficulty = next_difficulty
            await db.commit()
            logger.info(f"Updated student {session.student_id} difficulty: {student.current_difficulty} → {next_difficulty}")

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
