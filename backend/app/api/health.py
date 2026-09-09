from fastapi import APIRouter
from pydantic import BaseModel

from app.infra.secrets import get_optional_secret

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    justos_env: str


@router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    env = get_optional_secret("JUSTOS_ENV", "staging") or "staging"
    return HealthResponse(status="ok", version="0.1.0", justos_env=env)
