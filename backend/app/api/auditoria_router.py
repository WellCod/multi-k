"""Rotas de auditoria — visível apenas para admins."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.infra.db import get_db
from app.infra.models import Auditoria, Usuario

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


class AuditoriaOut(BaseModel):
    id: int
    tipo: str
    usuario_id: uuid.UUID | None
    usuario_nome: str | None
    ip_origem: str | None
    dados: dict[str, Any]
    criado_em: datetime

    model_config = {"from_attributes": True}


class AuditoriaListOut(BaseModel):
    items: list[AuditoriaOut]
    total: int
    page: int
    page_size: int


class AuditoriaUsuarioOut(BaseModel):
    id: uuid.UUID
    nome: str


@router.get("/usuarios", response_model=list[AuditoriaUsuarioOut])
async def listar_usuarios_auditoria(
    _usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditoriaUsuarioOut]:
    """Retorna os usuários distintos que aparecem no log de auditoria."""
    from sqlalchemy import func

    subq = (
        select(Auditoria.usuario_id)
        .where(Auditoria.usuario_id.is_not(None))
        .distinct()
        .subquery()
    )
    result = await db.execute(
        select(Usuario).where(Usuario.id.in_(select(subq))).order_by(Usuario.nome)
    )
    return [
        AuditoriaUsuarioOut(id=u.id, nome=u.nome) for u in result.scalars().all()
    ]


@router.get("", response_model=AuditoriaListOut)
async def listar_auditoria(
    _usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tipo: str | None = Query(None),
    usuario_id: uuid.UUID | None = Query(None),
) -> AuditoriaListOut:
    from sqlalchemy import func

    base = select(Auditoria)
    if tipo:
        base = base.where(Auditoria.tipo == tipo)
    if usuario_id:
        base = base.where(Auditoria.usuario_id == usuario_id)

    total_r = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = int(total_r.scalar_one())

    result = await db.execute(
        base.order_by(Auditoria.criado_em.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()

    # resolve user names in a single query
    uid_set = {r.usuario_id for r in rows if r.usuario_id is not None}
    nome_map: dict[uuid.UUID, str] = {}
    if uid_set:
        u_result = await db.execute(
            select(Usuario).where(Usuario.id.in_(uid_set))
        )
        nome_map = {u.id: u.nome for u in u_result.scalars().all()}

    items = [
        AuditoriaOut(
            id=r.id,
            tipo=r.tipo,
            usuario_id=r.usuario_id,
            usuario_nome=nome_map.get(r.usuario_id) if r.usuario_id else None,
            ip_origem=r.ip_origem,
            dados=r.dados,
            criado_em=r.criado_em,
        )
        for r in rows
    ]
    return AuditoriaListOut(items=items, total=total, page=page, page_size=page_size)
