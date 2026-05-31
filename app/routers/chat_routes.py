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

    system = (
        "You are QuizThala's AI tutor helping NEET students prepare for their medical entrance exam. "
        "Be concise (3–5 sentences unless asked for more), accurate, and encouraging. "
        "Use clear scientific language appropriate for NEET level."
    )
    if payload.quiz_summary:
        system += f"\n\nThe student just completed this quiz:\n{payload.quiz_summary}"

    messages = [{"role": "system", "content": system}]
    for m in payload.history[-10:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": payload.message})

    client = get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=600,
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
