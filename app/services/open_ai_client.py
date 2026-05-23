from openai import AsyncOpenAI
from app.core.config import settings


def get_openai_client() -> AsyncOpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
