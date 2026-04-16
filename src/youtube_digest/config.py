from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_owner_id: int
    openrouter_api_key: str
    openrouter_model: str = "google/gemini-2.5-flash"
    output_dir: Path = Path("/opt/dev/knowledge_base/video-digest")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
