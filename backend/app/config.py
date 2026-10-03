from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All secrets come from environment variables / .env. Never hard-code keys."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./xylon.db"  # dev fallback only
    jwt_secret: str  # required: app refuses to start without it
    jwt_expire_minutes: int = 480
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    cors_origins: str = "http://localhost:5173"
    allow_registration: bool = True
    cache_days: int = 30
    sender_name: str = "Xylon Technology"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


settings = Settings()
