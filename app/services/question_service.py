import json

from app.services.open_ai_client import get_openai_client


async def generate_questions(
    exam_name: str,
    subject_name: str,
    topic_name: str,
    difficulty: str,
    count: int,
) -> list[dict]:
    """
    Ask GPT to generate NEET-style MCQs.
    Returns a list of dicts with keys matching the questions table columns:
    question_text, option_a, option_b, option_c, option_d, correct_option, explanation
    """

    prompt = f"""Generate {count} NEET-style multiple-choice questions.

Exam: {exam_name}
Subject: {subject_name}
Topic: {topic_name}
Difficulty: {difficulty}

Rules:
- Exactly 4 options per question
- One correct answer
- Include a brief explanation for the correct answer
- No duplicate questions
- All content must be factually accurate for NEET preparation

Return ONLY a valid JSON array with this exact structure, no markdown:
[
  {{
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_option": "A",
    "explanation": "..."
  }}
]

correct_option must be exactly one character: A, B, C, or D."""

    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if model wraps them
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    return json.loads(content)
