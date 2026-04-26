from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str | None = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    STT_MODEL: str = "whisper-large-v3"
    LLM_MODEL: str = "openai/gpt-oss-120b"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    LIVE_WINDOW_SECONDS: int = 25
    UI_REFRESH_SECONDS: int = 30
    MEDIA_SLICE_MS: int = 5000
    LIVE_CONTEXT_TOKEN_CAP: int = 1500
    CHAT_CONTEXT_TOKEN_CAP: int = 6000
    RECENT_TOPIC_THRESHOLD: float = 0.78
    FALLBACK_TOPIC_THRESHOLD: float = 0.62
    TOPIC_CANDIDATE_PREFILTER: int = 12
    TOPIC_RANKER_TOP_K: int = 5
    RETRIEVE_CHUNKS_PER_TOPIC: int = 2
    ENABLE_OPTIONAL_PERSISTENCE: bool = False
    OPTIONAL_PERSISTENCE_DIR: str = ".tm_optional_persistence"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
