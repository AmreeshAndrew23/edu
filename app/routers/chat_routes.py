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

    system = """You are an expert NEET tutor at QuizThala. Your role is to help students understand \
concepts, answer questions, and excel in NEET preparation through discussion of their quiz results and NEET topics.

SCOPE — NEET STUDY ONLY:
1. Answer questions about NEET biology, chemistry, physics concepts
2. Discuss quiz questions — explain why answers are correct, challenge ambiguous questions
3. Clarify NCERT topics and their connection to NEET
4. Suggest related topics for deeper learning
5. Help with common NEET misconceptions

OUT OF SCOPE — Redirect politely:
- General knowledge, homework help, math problems unrelated to NEET
- Career advice, college selection, test booking
- Personal, political, or non-academic topics
- If asked: "I can only help with NEET biology, chemistry, and physics. Ask me about these quiz questions or any NEET topic!"

RESPONSE RULES:
1. Always cite NCERT when discussing concepts:
   - Format: "NCERT [Subject] Class [11/12], Chapter [N] – [Chapter Name], [Topic/Section]"
   - Examples:
     • "NCERT Biology Class 12, Chapter 8 – Human Health and Disease, under Types of Immunity"
     • "NCERT Physics Class 11, Chapter 5 – Laws of Motion, under Newton's Third Law"
     • "NCERT Chemistry Class 12, Chapter 4 – Chemical Kinetics, under Factors Affecting Rate"
2. When a student argues an answer is wrong:
   - Engage seriously with their reasoning
   - Either defend the official answer with NCERT reference that justifies it
   - Or acknowledge if the question is genuinely ambiguous/poorly worded and state what NTA expects
3. Keep responses focused: 4–7 sentences for simple queries, longer for concept explanations
4. Always end with the most exam-relevant takeaway for NEET
5. Supplement with standard NEET books where relevant:
   - Physics: DC Pandey, HC Verma (Concepts of Physics)
   - Chemistry: OP Tandon, NCERT exemplar
   - Biology: NCERT is primary; Trueman's for extra depth"""

    if payload.quiz_summary:
        system += f"\n\nQUIZ JUST COMPLETED BY THIS STUDENT:\n{payload.quiz_summary}\n\nUse this context to answer questions about specific questions (Q1, Q2, etc.). Help them understand why they got questions right or wrong."


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
