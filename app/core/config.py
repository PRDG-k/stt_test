import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("key.env")

class Settings(BaseSettings):
    GROQ_API_KEY: str = os.getenv("GROK", "")
    VLLM_API_BASE: str = "http://192.168.0.18:8001/v1"
    VLLM_MODEL_NAME: str = "/models/gemma-4-E4B-it"
    DATABASE_URL: str = "sqlite:///./stt_actions.db"
    ALLOWED_ORIGINS: list[str] = ["*"] 
    ALLOWED_DOMAINS: list[str] = ["www.google.com", "github.com", "naver.com"]
    
    # Simple RBAC: API Key -> Role mapping
    # Roles: ADMIN (all permissions), OPERATOR (control + view), VIEWER (view only)
    API_KEYS: dict[str, str] = {
        "admin-key-123": "ADMIN",
        "operator-key-456": "OPERATOR",
        "viewer-key-789": "VIEWER"
    }
    
    # Permissions: Role -> List of allowed Actions
    ROLE_PERMISSIONS: dict[str, list[str]] = {
        "ADMIN": ["MOVE_PAGE", "DATA_FETCH", "FILE_DOWNLOAD", "DEVICE_CONTROL", "SHOW_MSG"],
        "OPERATOR": ["MOVE_PAGE", "DATA_FETCH", "DEVICE_CONTROL", "SHOW_MSG"],
        "VIEWER": ["MOVE_PAGE", "DATA_FETCH", "SHOW_MSG"]
    }

settings = Settings()

# Centralized vLLM Client
vllm_client = OpenAI(
    api_key="none",
    base_url=settings.VLLM_API_BASE
)
