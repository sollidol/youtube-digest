from pydantic_settings import BaseSettings


MODELS = {
    "haiku": "anthropic/claude-haiku-4-5",
    "sonnet": "anthropic/claude-sonnet-4-6",
    "flash": "google/gemini-2.5-flash",
}

MODEL_LABELS = {
    "haiku": "Haiku 4.5 (~$0.05/видео)",
    "sonnet": "Sonnet 4.6 (~$0.25/видео)",
    "flash": "Gemini Flash (~$0.01/видео)",
}


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_owner_id: int
    openrouter_api_key: str
    openrouter_model: str = "anthropic/claude-haiku-4-5"
    owner_context: str = "Владелец бизнеса. Интересы: AI, маркетинг, продажи, управление, стратегия"
    idea_tags: str = "ai, marketing, sales, management, strategy"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Runtime model override (persists until restart, switchable via /model)
active_model: str = settings.openrouter_model
