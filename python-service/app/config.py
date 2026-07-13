import os
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # Grok (xAI) API key - supports GROK_API_KEY, XAI_API_KEY, plus backward compat with GROK_API_KEY
    grok_api_key: str = os.getenv("GROK_API_KEY", os.getenv("XAI_API_KEY", os.getenv("GROK_API_KEY", "")))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    llm_provider: Literal["auto", "grok", "gemini", "grok"] = os.getenv("LLM_PROVIDER", "auto")
    symfony_callback_url: str = os.getenv("SYMFONY_CALLBACK_URL", "http://nginx/api/internal/evaluation-result")
    callback_token: str = os.getenv("CALLBACK_TOKEN", "s3cr3t_shared_token_change_me")
    clone_base_dir: str = os.getenv("CLONE_BASE_DIR", "/tmp/challenge_clones")
    max_file_content_chars: int = 25000
    max_files_to_read: int = 100
    clone_timeout_seconds: int = 60

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
