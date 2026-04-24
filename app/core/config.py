import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from openai import OpenAI

# Load multiple env files if they exist
load_dotenv(".env")
load_dotenv("key.env")

class Settings(BaseSettings):
    GROQ_API_KEY: str = os.getenv("GROK", "")
    VLLM_API_BASE: str = "http://192.168.0.18:8001/v1"
    VLLM_MODEL_NAME: str = "/models/gemma-4-E4B-it"
    DATABASE_URL: str = "sqlite:///./stt_actions.db"
    ALLOWED_ORIGINS: list[str] = ["*"] 
    ALLOWED_DOMAINS: list[str] = ["www.google.com", "github.com", "naver.com"]

    # Postgres Settings for Checkpointing
    PG_DB_HOST: str = os.getenv("PG_DB_HOST", "localhost")
    PG_DB_PORT: str = os.getenv("PG_DB_PORT", "5432")
    PG_DB_NAME: str = os.getenv("PG_DB_NAME", "postgres")
    PG_DB_USER: str = os.getenv("PG_DB_USER", "postgres")
    PG_DB_PASSWORD: str = os.getenv("PG_DB_PASSWORD", "")
    PG_CHECKPOINT_SCHEMA: str = os.getenv("PG_CHECKPOINT_SCHEMA", "STT_ckpt")

    @property
    def postgres_dsn(self) -> str:
        return (
                f"host={os.environ['PG_DB_HOST']} "
                f"port={os.environ['PG_DB_PORT']} "
                f"dbname={os.environ['PG_DB_NAME']} "
                f"user={os.environ['PG_DB_USER']} "
                f"password={os.environ['PG_DB_PASSWORD']}"
            )

settings = Settings()

# Centralized vLLM Client
vllm_client = OpenAI(
    api_key="none",
    base_url=settings.VLLM_API_BASE
)
