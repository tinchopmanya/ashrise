from fastapi import APIRouter, Depends

from app.auth import require_bearer_token
from app.config import Settings, get_settings


router = APIRouter(tags=["health"], dependencies=[Depends(require_bearer_token)])


@router.get("/health")
def get_health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": settings.app_name,
    }
