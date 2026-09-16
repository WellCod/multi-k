"""Conferência manual de resultados indefinidos, sem reenvio externo."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra import transmission_control as control
from app.infra.db import get_db
from app.infra.models import Auditoria, Cotacao, Proposta

router = APIRouter(prefix="/transmissoes", tags=["transmissoes"])
Db = Annotated[AsyncSession, Depends(get_db)]


class TransmissionState(BaseModel):
    cotacao_id: uuid.UUID
    tentativa_id: uuid.UUID | None = None
    versao: int | None = None
    cia: str | None = None
    estado: str
    bloqueada: bool
    atualizado_em: datetime | None = None


def state(quote_id: uuid.UUID, entry: Auditoria | None) -> TransmissionState:
    if entry is None:
        return TransmissionState(
            cotacao_id=quote_id, estado="sem_tentativa", bloqueada=False
        )
    kind = entry.tipo.removeprefix("transmissao.")
    return TransmissionState(
        cotacao_id=quote_id,
        tentativa_id=entry.dados["tentativa_id"],
        versao=entry.id,
        cia=entry.dados["cia"],
        estado=kind,
        bloqueada=kind != "liberada",
        atualizado_em=entry.criado_em,
    )


@router.get("/cotacoes/{cotacao_id}", response_model=TransmissionState)
async def get_state(
    cotacao_id: uuid.UUID, usuario: CurrentUser, db: Db
) -> TransmissionState:
    actor = control.Actor(usuario.id, usuario.tenant_id, usuario.papel)
    quote = await control.quote_for_user(db, cotacao_id, actor, admin_review=True)
    result = state(quote.id, await control.latest(db, quote))
    existing = (
        await db.execute(
            select(Proposta.id)
            .where(
                Proposta.cotacao_id == quote.id, Proposta.tenant_id == actor.tenant_id
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        result.estado = "concluida"
        result.bloqueada = True
    return result


class PendingPage(BaseModel):
    items: list[TransmissionState]
    page: int
    pages: int
    total: int


@router.get("/pendentes", response_model=PendingPage)
async def pending(
    usuario: CurrentUser,
    db: Db,
    page: int = Query(1, ge=1),
) -> PendingPage:
    if usuario.papel not in ("corretor", "admin"):
        raise HTTPException(403, "Perfil sem permissão para esta ação.")
    quote_key = Auditoria.dados["cotacao_id"].astext
    latest_ids = (
        select(func.max(Auditoria.id))
        .where(
            Auditoria.tipo.in_(control.TYPES), Auditoria.tenant_id == usuario.tenant_id
        )
        .group_by(quote_key)
    )
    stmt = (
        select(Auditoria)
        .join(Cotacao, Cotacao.id.cast(String) == quote_key)
        .where(
            Auditoria.id.in_(latest_ids),
            Cotacao.tenant_id == usuario.tenant_id,
            Auditoria.tipo.in_(
                (
                    "transmissao.iniciada",
                    "transmissao.incerta",
                    "transmissao.confirmada",
                )
            ),
        )
    )
    if usuario.papel != "admin":
        stmt = stmt.where(Cotacao.usuario_id == usuario.id)
    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    entries = (
        await db.execute(
            stmt.order_by(Auditoria.id.desc()).offset((page - 1) * 20).limit(20)
        )
    ).scalars()
    return PendingPage(
        items=[state(uuid.UUID(e.dados["cotacao_id"]), e) for e in entries],
        page=page,
        pages=max(1, (total + 19) // 20),
        total=total,
    )


class ReviewInput(BaseModel):
    tentativa_id: uuid.UUID
    versao: int = Field(ge=1)
    resultado: Literal["nao_aceita", "aceita"]
    conferido_na_seguradora: Literal[True]
    justificativa: str = Field(min_length=10, max_length=500)
    referencia: str | None = Field(default=None, min_length=3, max_length=100)

    @field_validator("justificativa", "referencia", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def accepted_requires_reference(self) -> "ReviewInput":
        if self.resultado == "aceita" and not self.referencia:
            raise ValueError("Informe a referência confirmada na seguradora.")
        return self


@router.post("/cotacoes/{cotacao_id}/conferir", response_model=TransmissionState)
async def review(
    cotacao_id: uuid.UUID,
    body: ReviewInput,
    request: Request,
    usuario: CurrentUser,
    db: Db,
) -> TransmissionState:
    actor = control.Actor(usuario.id, usuario.tenant_id, usuario.papel)
    quote = await control.quote_for_user(
        db, cotacao_id, actor, lock=True, admin_review=True
    )
    previous = await control.latest(db, quote)
    if (
        previous is None
        or previous.id != body.versao
        or previous.dados.get("tentativa_id") != str(body.tentativa_id)
        or previous.tipo not in ("transmissao.iniciada", "transmissao.incerta")
    ):
        raise HTTPException(
            409, "A tentativa mudou ou já foi conferida. Atualize os dados."
        )
    existing = (
        await db.execute(
            select(Proposta.id)
            .where(
                Proposta.cotacao_id == quote.id, Proposta.tenant_id == actor.tenant_id
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            409, "Já existe uma proposta local. O reenvio permanece bloqueado."
        )
    kind = (
        "transmissao.liberada"
        if body.resultado == "nao_aceita"
        else "transmissao.confirmada"
    )
    await control.record(
        db,
        quote,
        actor,
        kind,
        body.tentativa_id,
        previous.dados["cia"],
        ip=request.client.host if request.client else None,
        justification=body.justificativa,
        reference=body.referencia,
    )
    result = state(quote.id, await control.latest(db, quote))
    await db.commit()
    return result
