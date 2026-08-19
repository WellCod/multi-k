"""Rotas de cotação — fila assíncrona com SKIP LOCKED."""

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.db import get_db
from app.infra.models import Cotacao, CotacaoJob, EventoDB

router = APIRouter(prefix="/cotacoes", tags=["cotacoes"])


class CriarCotacaoInput(BaseModel):
    ramo: str
    dados: dict[str, Any]
    cliente_id: uuid.UUID | None = None
    versao_anterior_id: uuid.UUID | None = None


class CotacaoCriadaOut(BaseModel):
    id: uuid.UUID
    status: str
    ramo: str


class CotacaoOut(BaseModel):
    id: uuid.UUID
    status: str
    ramo: str
    cliente_id: uuid.UUID | None
    cotacao_id_cia: str | None
    premio_total: Decimal | None
    restricoes: list[dict[str, str]]
    mensagens: list[str]
    necessita_vistoria: bool
    versao_anterior_id: uuid.UUID | None
    criado_em: str
    dados_risco: dict[str, Any]


def _cotacao_out(c: Cotacao) -> CotacaoOut:
    restricoes: list[dict[str, str]] = [
        {"codigo": r["codigo"], "mensagem": r["mensagem"]} for r in (c.restricoes or [])
    ]
    mensagens: list[str] = [str(m) for m in (c.mensagens or [])]
    return CotacaoOut(
        id=c.id,
        status=c.status,
        ramo=c.ramo,
        cliente_id=c.cliente_id,
        cotacao_id_cia=c.cotacao_id_cia,
        premio_total=c.premio_total,
        restricoes=restricoes,
        mensagens=mensagens,
        necessita_vistoria=c.necessita_vistoria,
        versao_anterior_id=c.versao_anterior_id,
        criado_em=c.criado_em.isoformat(),
        dados_risco=c.dados_risco,
    )


async def _get_cotacao_ou_404(
    cotacao_id: uuid.UUID,
    usuario_id: uuid.UUID,
    db: AsyncSession,
) -> Cotacao:
    result = await db.execute(
        select(Cotacao)
        .where(Cotacao.id == cotacao_id)
        .where(Cotacao.usuario_id == usuario_id)
    )
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cotação não encontrada.",
        )
    return c


@router.post("", response_model=CotacaoCriadaOut, status_code=202)
async def criar_cotacao(
    body: CriarCotacaoInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoCriadaOut:
    cotacao = Cotacao(
        id=uuid.uuid4(),
        cliente_id=body.cliente_id,
        ramo=body.ramo,
        status="aguardando",
        dados_risco=body.dados,
        versao_anterior_id=body.versao_anterior_id,
        usuario_id=usuario.id,
    )
    db.add(cotacao)
    await db.flush()

    job = CotacaoJob(
        id=uuid.uuid4(),
        cotacao_id=cotacao.id,
        cia="fake",
        status="pendente",
    )
    db.add(job)

    db.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={"ramo": body.ramo, "cotacao_id": str(cotacao.id)},
            usuario_id=usuario.id,
        )
    )

    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "cotacao.criada",
        {"ramo": body.ramo},
        usuario_id=usuario.id,
        ip_origem=ip,
    )

    await db.commit()

    return CotacaoCriadaOut(id=cotacao.id, status=cotacao.status, ramo=cotacao.ramo)


@router.get("/{cotacao_id}", response_model=CotacaoOut)
async def obter_cotacao(
    cotacao_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoOut:
    c = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)
    return _cotacao_out(c)


@router.get("", response_model=list[CotacaoOut])
async def listar_cotacoes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CotacaoOut]:
    result = await db.execute(
        select(Cotacao)
        .where(Cotacao.usuario_id == usuario.id)
        .order_by(Cotacao.criado_em.desc())
    )
    return [_cotacao_out(c) for c in result.scalars().all()]


@router.post("/{cotacao_id}/recotar", response_model=CotacaoCriadaOut, status_code=202)
async def recotar(
    cotacao_id: uuid.UUID,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CotacaoCriadaOut:
    """Cria nova versão a partir de cotação existente, pré-preenchida."""
    original = await _get_cotacao_ou_404(cotacao_id, usuario.id, db)

    nova = Cotacao(
        id=uuid.uuid4(),
        cliente_id=original.cliente_id,
        ramo=original.ramo,
        status="aguardando",
        dados_risco=dict(original.dados_risco),
        versao_anterior_id=cotacao_id,
        usuario_id=usuario.id,
    )
    db.add(nova)
    await db.flush()

    job = CotacaoJob(
        id=uuid.uuid4(),
        cotacao_id=nova.id,
        cia="fake",
        status="pendente",
    )
    db.add(job)

    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "cotacao.recotada",
        {"cotacao_anterior": str(cotacao_id), "nova_cotacao": str(nova.id)},
        usuario_id=usuario.id,
        ip_origem=ip,
    )

    await db.commit()

    return CotacaoCriadaOut(id=nova.id, status=nova.status, ramo=nova.ramo)
