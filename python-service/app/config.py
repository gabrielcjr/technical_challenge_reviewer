from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


# Constants for clean code - intention revealing
SENTINEL_TEST_TOKENS = ("", "gsk_test", "xai_test", "test")
DEFAULT_CALLBACK_URL = "http://nginx/api/internal/evaluation-result"
DEFAULT_CLONE_BASE_DIR = "/tmp/challenge_clones"
DEFAULT_MAX_CONTENT_CHARS = 25_000
DEFAULT_MAX_FILES = 100
DEFAULT_CLONE_TIMEOUT_SECONDS = 60


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_file_encoding="utf-8",
    )

    # LLM Keys - support multiple env names via properties
    grok_api_key: str = ""
    xai_api_key: str = ""
    gemini_api_key: str = ""

    llm_provider: Literal["auto", "grok", "gemini"] = "auto"
    symfony_callback_url: str = DEFAULT_CALLBACK_URL
    callback_token: str = "s3cr3t_shared_token_change_me"
    clone_base_dir: str = DEFAULT_CLONE_BASE_DIR

    # Evaluation limits - named constants with units
    max_file_content_chars: int = DEFAULT_MAX_CONTENT_CHARS
    max_files_to_read: int = DEFAULT_MAX_FILES
    clone_timeout_seconds: int = DEFAULT_CLONE_TIMEOUT_SECONDS

    @property
    def resolved_grok_api_key(self) -> str:
        """Resolve Grok key supporting both GROK_API_KEY and XAI_API_KEY."""
        return self.grok_api_key or self.xai_api_key or ""

    def is_grok_configured(self) -> bool:
        return bool(
            self.resolved_grok_api_key
            and self.resolved_grok_api_key not in SENTINEL_TEST_TOKENS
        )

    def is_gemini_configured(self) -> bool:
        return bool(
            self.gemini_api_key and self.gemini_api_key not in SENTINEL_TEST_TOKENS
        )


settings = Settings()
