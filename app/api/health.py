from fastapi import APIRouter, status
from app.core.config import settings, vllm_client
from app.models.database import SessionLocal
from sqlalchemy import text
import httpx

router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    health_status = {
        "status": "healthy",
        "components": {
            "database": "unknown",
            "vllm_server": "unknown"
        }
    }
    
    # 1. Database Check
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "connected"
        db.close()
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = f"error: {str(e)}"

    # 2. vLLM Server Check (Timeout 2s)
    try:
        async with httpx.AsyncClient() as client:
            # vLLM API 서버의 기본 경로(/v1/models 등)를 가볍게 호출
            response = await client.get(f"{settings.VLLM_API_BASE}/models", timeout=2.0)
            if response.status_code == 200:
                health_status["components"]["vllm_server"] = "connected"
            else:
                health_status["components"]["vllm_server"] = f"unhealthy (status: {response.status_code})"
    except Exception as e:
        health_status["components"]["vllm_server"] = f"error: {str(e)}"
        # vLLM은 외부 의존성이므로 서버 자체의 status를 즉시 unhealthy로 바꾸진 않으나 경고 표시

    return health_status
