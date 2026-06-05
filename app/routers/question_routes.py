import base64
import io
import json
import logging

from fastapi import APIRouter, Depends, Form, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.exam import Exam
from app.services.open_ai_client import get_openai_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/questions", tags=["Questions"])

_CORE_SUBJECTS = ['Physics', 'Chemistry', 'Biology']
_FULL_SUBJECT  = 'All Subjects'

_SYSTEM_PROMPT = (
    "You are a NEET question extractor. "
    "Given content from a NEET exam paper, extract EVERY MCQ question and return ONLY a JSON object "
    "with a single key 'questions' whose value is an array. Each element must have:\n"
    "  question_text (string), option_a, option_b, option_c, option_d (strings, no letter prefix),\n"
    "  correct_option ('A'|'B'|'C'|'D'), explanation (string or null),\n"
    "  subject (exactly one of: 'Physics', 'Chemistry', 'Biology'),\n"
    "  topic_name (the closest NEET syllabus topic name), difficulty ('easy'|'medium'|'hard').\n"
    "Do NOT skip any question. Return ONLY valid JSON. No markdown, no commentary."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _ai_extract_text(text: str) -> list[dict]:
    client = get_openai_client()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": text[:28000]},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=4096,
    )
    return json.loads(resp.choices[0].message.content).get("questions", [])


async def _ai_extract_image(image_bytes: bytes, mime: str) -> list[dict]:
    client = get_openai_client()
    b64 = base64.b64encode(image_bytes).decode()
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text",      "text": _SYSTEM_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=4096,
    )
    return json.loads(resp.choices[0].message.content).get("questions", [])


def _pdf_to_text(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def _scanned_pdf_to_questions(content: bytes) -> list[dict]:
    """Render each page of a scanned PDF as an image, extract MCQs via GPT-4o vision."""
    import fitz  # pymupdf

    doc = fitz.open(stream=content, filetype="pdf")
    # Render all pages at 2× zoom (≈144 DPI) for legible text
    pages_png: list[bytes] = []
    for page_num in range(len(doc)):
        pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(2, 2))
        pages_png.append(pix.tobytes("png"))

    client = get_openai_client()
    all_questions: list[dict] = []
    BATCH = 3  # pages per GPT-4o call

    for i in range(0, len(pages_png), BATCH):
        batch = pages_png[i:i + BATCH]
        parts: list[dict] = [{"type": "text", "text": _SYSTEM_PROMPT}]
        for img in batch:
            b64 = base64.b64encode(img).decode()
            parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": parts}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=4096,
        )
        batch_qs = json.loads(resp.choices[0].message.content).get("questions", [])
        all_questions.extend(batch_qs)
        logger.info("Scanned PDF batch %d-%d: extracted %d questions", i + 1, i + len(batch), len(batch_qs))

    return all_questions


# ── Schemas ───────────────────────────────────────────────────────────────────

class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exam_id: int
    topic_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    difficulty_level: str | None


class UploadResult(BaseModel):
    extracted: int
    uploaded: int
    skipped: int
    created_topics: list[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[QuestionResponse])
async def list_questions(
    exam_id: int | None = None,
    topic_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Question)
    if exam_id:
        query = query.where(Question.exam_id == exam_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)
    return (await db.execute(query)).scalars().all()


@router.post("/upload", response_model=UploadResult)
async def upload_questions_file(
    year: int = Form(..., description="NEET paper year, e.g. 2023"),
    file: UploadFile = File(..., description="PDF, TXT, JPG, or PNG of the NEET paper"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a NEET previous-year question paper. Only two fields needed:
      - year: the NEET paper year (e.g. 2023)
      - file: PDF, TXT, JPG, or PNG

    AI extracts every MCQ, auto-detects subject and topic, and inserts all
    questions into the bank tagged with source='neet_paper'.
    """
    content      = await file.read()
    fname        = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    # ── Step 1: extract raw question dicts via AI ─────────────────────────────

    if content_type.startswith("image/") or fname.endswith((".jpg", ".jpeg", ".png")):
        mime = content_type if content_type.startswith("image/") else "image/jpeg"
        raw = await _ai_extract_image(content, mime)

    elif "pdf" in content_type or fname.endswith(".pdf"):
        try:
            text = _pdf_to_text(content)
        except Exception as exc:
            raise HTTPException(400, f"Could not read PDF: {exc}")
        if not text.strip():
            logger.info("Scanned PDF detected — rendering pages via pymupdf")
            try:
                raw = await _scanned_pdf_to_questions(content)
            except Exception as exc:
                raise HTTPException(400, f"Could not process scanned PDF: {exc}")
        else:
            raw = await _ai_extract_text(text)

    elif "text" in content_type or fname.endswith(".txt"):
        raw = await _ai_extract_text(content.decode("utf-8", errors="replace"))

    else:
        raise HTTPException(400, "Unsupported file type. Use PDF, TXT, JPG, or PNG.")

    extracted = len(raw)
    logger.info("Extracted %d questions from '%s' year=%d", extracted, fname, year)

    if not extracted:
        return UploadResult(extracted=0, uploaded=0, skipped=0, created_topics=[])

    # ── Step 2: resolve exam, subjects, topics ────────────────────────────────

    full_sub = (await db.execute(
        select(Subject).where(Subject.name == _FULL_SUBJECT)
    )).scalar_one_or_none()
    if not full_sub:
        raise HTTPException(400, "Full-exam subject not found — ensure seed has run.")

    exam = (await db.execute(
        select(Exam).where(Exam.subject_id == full_sub.id).order_by(Exam.exam_year.desc())
    )).scalars().first()
    if not exam:
        raise HTTPException(400, "No exam found — ensure seed has run.")

    # Map lowercase subject name → Subject row  (Physics, Chemistry, Biology)
    core_subs: dict[str, Subject] = {
        s.name.lower(): s for s in (await db.execute(
            select(Subject).where(Subject.name.in_(_CORE_SUBJECTS))
        )).scalars().all()
    }
    fallback_sub = core_subs.get('biology') or next(iter(core_subs.values()))

    # Map (subject_id, topic_name_lower) → Topic
    existing_topics = (await db.execute(
        select(Topic).where(Topic.subject_id.in_([s.id for s in core_subs.values()]))
    )).scalars().all()
    topic_map: dict[tuple[int, str], Topic] = {
        (t.subject_id, t.topic_name.lower()): t for t in existing_topics
    }

    # ── Step 3: insert questions ──────────────────────────────────────────────

    uploaded: int = 0
    skipped:  int = 0
    created_topics: list[str] = []
    order_counter: int = 0

    for q in raw:
        required = ("question_text", "option_a", "option_b", "option_c", "option_d", "correct_option")
        if not all(q.get(k) for k in required):
            skipped += 1
            continue

        correct = str(q["correct_option"]).upper().strip()
        if correct not in ("A", "B", "C", "D"):
            skipped += 1
            continue

        # Resolve subject from AI response; fall back to Biology
        ai_subject = (q.get("subject") or "").strip().lower()
        sub = core_subs.get(ai_subject) or fallback_sub

        # Find or create topic under that subject
        topic_name = (q.get("topic_name") or "General").strip()
        topic_key  = (sub.id, topic_name.lower())
        topic = topic_map.get(topic_key)
        if not topic:
            topic = Topic(topic_name=topic_name, subject_id=sub.id)
            db.add(topic)
            await db.flush()
            topic_map[topic_key] = topic
            created_topics.append(topic_name)

        # Skip exact duplicate
        dup = (await db.execute(
            select(Question.id).where(
                Question.question_text == q["question_text"],
                Question.topic_id == topic.id,
            )
        )).scalar_one_or_none()
        if dup:
            skipped += 1
            continue

        order_counter += 1
        db.add(Question(
            exam_id=exam.id,
            topic_id=topic.id,
            question_text=q["question_text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_option=correct,
            explanation=q.get("explanation"),
            difficulty_level=q.get("difficulty", "medium"),
            source='neet_paper',
            neet_year=year,
            paper_order=order_counter,
        ))
        uploaded += 1

    await db.commit()
    logger.info("Upload done: extracted=%d uploaded=%d skipped=%d", extracted, uploaded, skipped)
    return UploadResult(extracted=extracted, uploaded=uploaded, skipped=skipped, created_topics=created_topics)
