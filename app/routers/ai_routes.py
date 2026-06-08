from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.exam import Exam
from app.models.topic import Topic
from app.models.subject import Subject
from app.models.question import Question
from app.models.ai_usage_log import AiUsageLog
from app.services.question_service import generate_questions

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/generate-questions")
async def generate_ai_questions(
    exam_id: int = Query(...),
    subject_id: int = Query(...),
    topic_id: int = Query(...),
    difficulty: str = Query(..., description="easy | medium | hard"),
    question_count: int = Query(..., ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate AI questions for a specific exam + topic.
    Maps the AI response (option_a/b/c/d, correct_option) directly to the questions table.
    """

    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    generated, usage = await generate_questions(
        exam_name=exam.exam_name,
        subject_name=subject.name,
        topic_name=topic.topic_name,
        difficulty=difficulty,
        count=question_count,
    )

    db.add(AiUsageLog(
        endpoint="ai_generate_questions",
        model="gpt-4o-mini",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=round(
            (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1_000_000, 6
        ),
        context=f"{subject.name} | {topic.topic_name} | {difficulty}",
    ))

    saved: list[dict] = []

    for q in generated:
        question = Question(
            exam_id=exam_id,
            topic_id=topic_id,
            question_text=q["question_text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_option=q["correct_option"].upper(),
            explanation=q.get("explanation"),
            difficulty_level=difficulty,
        )
        db.add(question)
        saved.append(q)

    await db.commit()

    return {
        "message": f"{len(saved)} questions generated and saved",
        "exam": exam.exam_name,
        "exam_year": exam.exam_year,
        "subject": subject.name,
        "topic": topic.topic_name,
        "difficulty": difficulty,
        "count": len(saved),
        "questions": saved,
    }
