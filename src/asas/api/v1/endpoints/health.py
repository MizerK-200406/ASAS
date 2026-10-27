from fastapi import APIRouter, Depends
from asas.api.deps import get_app_settings
from asas.core.config import Settings
import asas

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(settings: Settings = Depends(get_app_settings)):
    return {
        "status": "ok",
        "app": "ASAS",
        "version": getattr(asas, "__version__", "0.1.0"),
        "model": settings.default_model,
    }
