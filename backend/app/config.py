"""Application settings, loaded from environment variables / backend/.env."""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Export provider API keys (OPENAI_API_KEY, ...) so the LangChain clients can read them.
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # LLM
    llm_provider: str = "openai"  # openai | anthropic | google_genai
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    llm_requests_per_minute: float = 0  # 0 = unlimited; set for free-tier API quotas

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "procurement"
    mongo_collection: str = "purchases"

    # Agent guard-rails
    max_result_docs: int = 50
    query_timeout_ms: int = 20_000
    max_retries: int = 2


settings = Settings()
