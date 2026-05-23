from openai import OpenAI
from app.core.config import settings


def get_openai_client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file to use AI question generation."
        )
    return OpenAI(api_key=settings.OPENAI_API_KEY)
