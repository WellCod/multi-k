from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")
