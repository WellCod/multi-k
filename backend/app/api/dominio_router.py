"""Rotas para consultar a tabela de domínios."""

import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import CatalogoRenovacao
from app.adapters.registry import catalogo_seguradoras, get_adapter
from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import Dominio

router = APIRouter(prefix="/dominios", tags=["dominios"])


@router.get("/seguradoras")
async def seguradoras(_usuario: CurrentUser) -> list[dict[str, object]]:
    return catalogo_seguradoras()


class SeguradoraAnteriorOut(BaseModel):
    codigo: int
    nome: str


@router.get("/seguradoras-anteriores", response_model=list[SeguradoraAnteriorOut])
async def seguradoras_anteriores(
    _usuario: CurrentUser,
    cia: str = Query(..., min_length=1),
) -> list[SeguradoraAnteriorOut]:
    """Seguradoras aceitas como apólice anterior na renovação (J2 §4.2)."""
    try:
        adapter = get_adapter(cia)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Seguradora desconhecida."
        ) from exc
    if not isinstance(adapter, CatalogoRenovacao):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{cia} não publica catálogo de seguradora anterior.",
        )
    try:
        catalogo = await adapter.seguradoras_anteriores()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Não foi possível consultar o catálogo da seguradora. "
            "Tente novamente antes de cotar a renovação.",
        ) from exc
    return [SeguradoraAnteriorOut(codigo=s.codigo, nome=s.nome) for s in catalogo]


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
