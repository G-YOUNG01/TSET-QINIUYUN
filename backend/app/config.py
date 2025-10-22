from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Novel2Comic API"
    environment: str = Field("development", env="APP_ENV")

    database_url: str = Field(
        "sqlite+aiosqlite:///./novel2comic.db", env="DATABASE_URL"
    )

    jwt_secret_key: str = Field("change-me", env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    openai_api_key: str = Field("sk-4mTSiqiQNy9oI8iYAT4eW6a7yFK8xJ4SbaWYo23f7Soh7PbJ", env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field("https://api.ruyun.fun/v1", env="OPENAI_BASE_URL")
    openai_outline_model: str = Field("gpt-4.1-mini", env="OPENAI_OUTLINE_MODEL")
    openai_prompt_model: str = Field("gpt-4o-mini", env="OPENAI_PROMPT_MODEL")
    openai_tts_voice: str = Field("alloy", env="OPENAI_TTS_VOICE")
    openai_image_model: str = Field("dall-e-3", env="OPENAI_IMAGE_MODEL")

    storage_bucket: Optional[str] = Field(None, env="STORAGE_BUCKET")
    storage_base_url: Optional[str] = Field("http://localhost:8000/static", env="STORAGE_BASE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
