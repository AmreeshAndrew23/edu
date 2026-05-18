import json

from app.services.open_ai_client import client


async def generate_questions(
    exam_name: str,
    subject_name: str,
    topic_name: str,
    difficulty: str,
    count: int
):

    prompt = f"""
    Generate {count} NEET-style MCQs.

    Exam: {exam_name}
    Subject: {subject_name}
    Topic: {topic_name}
    Difficulty: {difficulty}

    Rules:
    - 4 options
    - one correct answer
    - include explanation
    - no duplicate questions

    Return ONLY valid JSON array.
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5
    )

    content = response.choices[0].message.content

    return json.loads(content)