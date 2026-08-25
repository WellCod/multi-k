"""Helpers partilhados pelos routers da API."""

from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

_T = TypeVar("_T")


async def get_or_404(
    stmt: "Select[tuple[_T]]",
    db: AsyncSession,
    detail: str = "Não encontrado.",
) -> _T:
    """Executa stmt e retorna o único resultado ou levanta HTTPException 404."""
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj
