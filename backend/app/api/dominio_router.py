"""Rotas para consultar a tabela de domínios."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import Dominio

router = APIRouter(prefix="/dominios", tags=["dominios"])

_DOMINIO_TTL = 30 * 60  # 30 minutos — domínios mudam só via migration
_DominioCache = dict[tuple[str | None, str | None], tuple[float, list["DominioOut"]]]
_dominio_cache: _DominioCache = {}


class DominioOut(BaseModel):
    tipo: str
    codigo: str
    descricao: str
    cia: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DominioOut])
async def listar_dominios(
    _usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    tipo: str | None = Query(None),
    cia: str | None = Query(None),
) -> list[DominioOut]:
    cache_key = (tipo, cia)
    now = time.monotonic()
    if cache_key in _dominio_cache:
        expiry, cached = _dominio_cache[cache_key]
        if now < expiry:
            return cached

    stmt = select(Dominio).where(Dominio.ativo.is_(True))
    if tipo:
        stmt = stmt.where(Dominio.tipo == tipo)
    if cia:
        stmt = stmt.where(Dominio.cia == cia)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [DominioOut.model_validate(r) for r in rows]

    _dominio_cache[cache_key] = (now + _DOMINIO_TTL, items)
    return items
