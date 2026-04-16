from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_owner_id: int
    openrouter_api_key: str
    openrouter_model: str = "anthropic/claude-sonnet-4-6"
    owner_context: str = "Владелец бизнеса. Интересы: AI, маркетинг, продажи, управление, стратегия"
    idea_tags: str = "ai, marketing, sales, management, strategy"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
