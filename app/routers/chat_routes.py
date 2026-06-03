import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chat_log import ChatLog
from app.services.open_ai_client import get_openai_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


class HistoryMsg(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    student_id: int | None = None
    message: str
    history: list[HistoryMsg] = []
    quiz_summary: str | None = None
    context: str | None = None


class ChatResponse(BaseModel):
    reply: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@router.post("/message", response_model=ChatResponse)
async def chat_message(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Log user message
    db.add(ChatLog(
        student_id=payload.student_id,
        role="user",
        message=payload.message,
        context=payload.context,
    ))

    system = """You are an expert NEET tutor at QuizThala. Students may ask you to explain \
answers, challenge answers they think are wrong, or explore topics in depth.

RESPONSE RULES:
1. Always cite the exact NCERT source when discussing biology, chemistry, or physics:
   - Format: "NCERT [Subject] Class [11/12], Chapter [N] – [Chapter Name], under [Topic/Section]"
   - Examples:
     • "NCERT Biology Class 12, Chapter 8 – Human Health and Disease, under Types of Immunity"
     • "NCERT Physics Class 11, Chapter 5 – Laws of Motion, under Newton's Third Law"
     • "NCERT Chemistry Class 12, Chapter 4 – Chemical Kinetics, under Factors Affecting Rate"
2. Supplement with standard NEET books where relevant:
   - Physics: DC Pandey, HC Verma (Concepts of Physics)
   - Chemistry: OP Tandon, NCERT exemplar
   - Biology: NCERT is primary; Trueman's for extra depth
3. If a student argues an answer is wrong:
   - Engage with their reasoning seriously
   - Either defend the official answer with the NCERT reference that justifies it
   - Or acknowledge if the question is genuinely ambiguous/poorly worded and state what NTA expects
4. When referencing a specific question from the quiz (e.g. "Q3"), use the full question text and options from the quiz summary below
5. Keep responses focused: 4–7 sentences for simple queries, longer for detailed concept explanations
6. Always end with the most exam-relevant takeaway for NEET"""

    if payload.quiz_summary:
        system += f"\n\nQUIZ JUST COMPLETED BY THIS STUDENT:\n{payload.quiz_summary}\n\nUse this to answer questions about specific questions (Q1, Q2, etc.)."

    messages = [{"role": "system", "content": system}]
    for m in payload.history[-10:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": payload.message})

    client = get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.4,
        max_tokens=900,
    )

    reply = response.choices[0].message.content.strip()
    usage = response.usage

    logger.info(
        "Chat — student=%s context=%s prompt_tokens=%d completion_tokens=%d total=%d",
        payload.student_id, payload.context,
        usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
    )

    db.add(ChatLog(
        student_id=payload.student_id,
        role="assistant",
        message=reply,
        context=payload.context,
        model="gpt-4o-mini",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    ))
    await db.commit()

    return ChatResponse(
        reply=reply,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )
