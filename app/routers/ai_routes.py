from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

from app.models.exam import Exam
from app.models.topic import Topic  
from app.models.subject import Subject
from app.models.question import Question
from app.services.question_service import generate_questions


router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


@router.post("/generate-questions")
async def generate_ai_questions(
    exam_id: int,
    subject_id: int,
    topic_id: int,
    difficulty: str,
    question_count: int,
    db: AsyncSession = Depends(get_db)
):

    # validate exam
    exam = await db.get(Exam, exam_id)

    if not exam:
        raise HTTPException(404, "Exam not found")

    # validate subject
    subject = await db.get(Subject, subject_id)

    if not subject:
        raise HTTPException(404, "Subject not found")

    # validate topic
    topic = await db.get(Topic, topic_id)

    if not topic:
        raise HTTPException(404, "Topic not found")

    # generate AI questions
    generated_questions = await generate_questions(
        exam_name=exam.exam_name,
        subject_name=subject.name,
        topic_name=topic.topic_name,
        difficulty=difficulty,
        question_count=question_count
    )

    saved_questions = []

    # store in DB
    for q in generated_questions:

        question = Question(
            subject_id=subject.id,
            topic_id=topic.id,
            question_text=q["question_text"],
            options=q["options"],
            correct_answer=q["correct_answer"],
            explanation=q.get("explanation"),
            difficulty=difficulty,
            generated_by_ai=True
        )

        db.add(question)
        saved_questions.append(question)

    await db.commit()

    return {
        "message": "Questions generated successfully",
        "count": len(saved_questions),
        "questions": generated_questions
    }