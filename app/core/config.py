from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    OPENAI_API_KEY: str | None = None

    # Resend — set RESEND_API_KEY in Railway env vars (or .env locally)
    RESEND_API_KEY: str | None = None
    EMAIL_FROM_NAME: str = "QuizThala"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()