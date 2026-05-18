import json

from app.services.open_ai_client import client


async def generate_syllabus(
    exam_name: str,
    subject_name: str
):

    prompt = f"""
    Generate important syllabus topics for:

    Exam: {exam_name}
    Subject: {subject_name}

    Return ONLY valid JSON.

    Example:
    {{
      "topics": [
        "Cell Biology",
        "Human Physiology"
      ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content

    return json.loads(content)