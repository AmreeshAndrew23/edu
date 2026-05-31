from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    OPENAI_API_KEY: str | None = None

    # Brevo — set BREVO_API_KEY in Railway env vars (or .env locally)
    BREVO_API_KEY: str | None = None
    EMAIL_FROM_NAME: str = "QuizThala"
    EMAIL_FROM_ADDRESS: str = "quizthala@gmail.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()