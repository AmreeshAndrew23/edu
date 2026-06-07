import json
import random

from app.services.open_ai_client import get_openai_client


def _shuffle_options(q: dict) -> dict:
    """Randomly re-order A-D so the correct answer is distributed evenly."""
    keys = ['option_a', 'option_b', 'option_c', 'option_d']
    values = [q[k] for k in keys]
    correct_value = values[ord(q['correct_option'].upper()) - ord('A')]

    random.shuffle(values)

    result = dict(q)
    for i, val in enumerate(values):
        result[keys[i]] = val
        if val == correct_value:
            result['correct_option'] = chr(ord('A') + i)

    return result


async def generate_questions(
    exam_name: str,
    subject_name: str,
    topic_name: str,
    difficulty: str,
    count: int,
) -> tuple[list[dict], object]:  # (questions, usage)
    prompt = f"""Generate {count} NEET-style multiple-choice questions.

Exam: {exam_name}
Subject: {subject_name}
Topic: {topic_name}
Difficulty: {difficulty}

Rules:
- Exactly 4 options per question (option_a through option_d)
- One correct answer — distribute correct_option EVENLY across A, B, C, D (do NOT always use A or B)
- Include a brief explanation for the correct answer
- No duplicate questions
- All content must be factually accurate for NEET preparation

Return ONLY a valid JSON array — no markdown, no code fences:
[
  {{
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_option": "C",
    "explanation": "..."
  }}
]

correct_option must be exactly one character: A, B, C, or D — vary it across questions."""

    client = get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    questions = json.loads(content)
    return [_shuffle_options(q) for q in questions], response.usage
