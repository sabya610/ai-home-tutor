"""Health and status endpoints."""

from fastapi import APIRouter

from ..ai_client import get_ai_client
from ..config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "ai_mode": settings.ai_mode,
        "providers": get_ai_client().provider_info(),
        "tapo_configured": bool(settings.tapo_rtsp_url),
    }


@router.get("/health/llm")
def health_llm() -> dict[str, object]:
    """Live connectivity check for the tutor LLM (e.g. cluster llama3)."""
    return get_ai_client().ping_tutor()
