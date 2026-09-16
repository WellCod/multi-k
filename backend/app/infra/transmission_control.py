"""Diário append-only de transmissão; o lock da cotação serializa decisões.

Usa a auditoria existente para sobreviver a falhas sem exigir migração do banco
em uso. Nenhum payload da seguradora ou dado de risco entra neste diário.
"""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra import audit
from app.infra.models import Auditoria, Cotacao

TYPES = (
    "transmissao.iniciada",
    "transmissao.incerta",
    "transmissao.liberada",
    "transmissao.confirmada",
    "transmissao.concluida",
)


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID
    tenant_id: uuid.UUID
    papel: str


async def restore_context(db: AsyncSession, user: Actor) -> None:
    # SET LOCAL é apagado pelo commit anterior à chamada externa.
    await db.execute(
        text("SELECT set_config('app.usuario_id', :uid, true)"), {"uid": str(user.id)}
    )
    await db.execute(
        text("SELECT set_config('app.papel', :role, true)"), {"role": user.papel}
    )


async def quote_for_user(
    db: AsyncSession,
    quote_id: uuid.UUID,
    user: Actor,
    *,
    lock: bool = False,
    admin_review: bool = False,
) -> Cotacao:
    if user.papel not in ("corretor", "admin"):
        raise HTTPException(403, "Perfil sem permissão para esta ação.")
    stmt = select(Cotacao).where(
        Cotacao.id == quote_id, Cotacao.tenant_id == user.tenant_id
    )
    if not (admin_review and user.papel == "admin"):
        stmt = stmt.where(Cotacao.usuario_id == user.id)
    if lock:
        stmt = stmt.with_for_update(nowait=True)
    try:
        quote = (await db.execute(stmt)).scalar_one_or_none()
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == "55P03":
            await db.rollback()
            raise HTTPException(
                409, "Há uma operação em andamento. Aguarde e atualize a conferência."
            ) from exc
        raise
    if quote is None:
        raise HTTPException(404, "Cotação não encontrada.")
    return quote


async def latest(db: AsyncSession, quote: Cotacao) -> Auditoria | None:
    return (
        await db.execute(
            select(Auditoria)
            .where(
                Auditoria.tipo.in_(TYPES),
                Auditoria.tenant_id == quote.tenant_id,
                Auditoria.dados["cotacao_id"].astext == str(quote.id),
            )
            .order_by(Auditoria.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def record(
    db: AsyncSession,
    quote: Cotacao,
    user: Actor,
    kind: str,
    attempt_id: uuid.UUID,
    cia: str,
    *,
    ip: str | None = None,
    key: uuid.UUID | None = None,
    fingerprint: str | None = None,
    justification: str | None = None,
    reference: str | None = None,
) -> None:
    data = {"cotacao_id": str(quote.id), "tentativa_id": str(attempt_id), "cia": cia}
    if key is not None:
        data["chave_idempotencia"] = str(key)
    if fingerprint is not None:
        data["fingerprint"] = fingerprint
    if justification is not None:
        data["justificativa"] = justification
    if reference is not None:
        data["referencia_conferencia"] = reference
    await audit.registrar(
        db, kind, data, usuario_id=user.id, ip_origem=ip, tenant_id=quote.tenant_id
    )


async def mark_uncertain(
    db: AsyncSession,
    quote_id: uuid.UUID,
    user: Actor,
    attempt_id: uuid.UUID,
    cia: str,
    ip: str | None,
) -> None:
    await db.rollback()
    await restore_context(db, user)
    quote = await quote_for_user(db, quote_id, user, lock=True)
    previous = await latest(db, quote)
    if (
        previous is not None
        and previous.tipo == "transmissao.iniciada"
        and previous.dados.get("tentativa_id") == str(attempt_id)
    ):
        await record(db, quote, user, "transmissao.incerta", attempt_id, cia, ip=ip)
    await db.commit()
