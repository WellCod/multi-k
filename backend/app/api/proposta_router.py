"""Rotas de proposta — transmissão, consulta e parcelas."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PortaSeguradora, PropostaCanonica, RiscoCanonico
from app.api._utils import get_or_404
from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.db import get_db
from app.infra.models import Cotacao, EventoDB, Proposta
from app.infra.worker import get_adapter

router = APIRouter(tags=["propostas"])


# ---------------------------------------------------------------------------
# Dependência injetável — sobrescrita nos testes com FakeSeguradora(0, 0)
# ---------------------------------------------------------------------------


def _adapter_dep() -> PortaSeguradora:
    return get_adapter("fake")


AdapterDep = Annotated[PortaSeguradora, Depends(_adapter_dep)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TransmitirInput(BaseModel):
    plano_pagamento: str
    n_parcelas: int = Field(ge=1, le=12)
    comissao_pct: Decimal = Field(gt=0, le=1)
    inicio_vigencia: date | None = None
    dados_negocio: dict[str, Any] = Field(default_factory=dict)


class PropostaOut(BaseModel):
    id: uuid.UUID
    cotacao_id: uuid.UUID
    protocolo: str
    plano_pagamento: str
    n_parcelas: int
    valor_parcela: Decimal
    comissao_parcela: Decimal
    comissao_pct: Decimal
    inicio_vigencia: date | None
    transmitida_em: str


class ParcelaOut(BaseModel):
    numero: int
    vencimento: date | None
    valor: Decimal
    comissao: Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _proposta_out(p: Proposta) -> PropostaOut:
    return PropostaOut(
        id=p.id,
        cotacao_id=p.cotacao_id,
        protocolo=p.protocolo,
        plano_pagamento=p.plano_pagamento,
        n_parcelas=p.n_parcelas,
        valor_parcela=p.valor_parcela,
        comissao_parcela=p.comissao_parcela,
        comissao_pct=p.comissao_pct,
        inicio_vigencia=p.inicio_vigencia,
        transmitida_em=p.transmitida_em.isoformat(),
    )


async def _get_proposta_ou_404(
    proposta_id: uuid.UUID, usuario_id: uuid.UUID, db: AsyncSession
) -> Proposta:
    stmt = (
        select(Proposta)
        .where(Proposta.id == proposta_id)
        .where(Proposta.usuario_id == usuario_id)
    )
    return await get_or_404(stmt, db, "Proposta não encontrada.")


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.post(
    "/cotacoes/{cotacao_id}/transmitir",
    response_model=PropostaOut,
    status_code=201,
)
async def transmitir(
    cotacao_id: uuid.UUID,
    body: TransmitirInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: AdapterDep,
) -> PropostaOut:
    """Transmite uma cotação aprovada para a seguradora e cria a proposta."""
    stmt = (
        select(Cotacao)
        .where(Cotacao.id == cotacao_id)
        .where(Cotacao.usuario_id == usuario.id)
    )
    cotacao: Cotacao = await get_or_404(stmt, db, "Cotação não encontrada.")
    if cotacao.status not in ("sucesso", "restricao"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status '{cotacao.status}' não permite transmissão.",
        )
    if cotacao.premio_total is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cotação sem prêmio calculado.",
        )

    risco = RiscoCanonico(ramo=cotacao.ramo, dados=dict(cotacao.dados_risco))
    # Mescla payload_original (ex: coverages_selected da Justos) sob dados_negocio
    # do body — o body tem precedência para sobrescrever valores se necessário
    merged_negocio: dict[str, Any] = {
        **dict(cotacao.payload_original or {}),
        **dict(body.dados_negocio),
    }
    proposta_canonica = PropostaCanonica(
        cotacao_id=str(cotacao.cotacao_id_cia or cotacao_id),
        risco=risco,
        dados_negocio=merged_negocio,
    )

    resultado = await adapter.transmitir(proposta_canonica)
    if not resultado.sucesso or resultado.protocolo is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Transmissão recusada: {'; '.join(resultado.mensagens)}",
        )

    valor_parcela = (cotacao.premio_total / body.n_parcelas).quantize(Decimal("0.01"))
    comissao_parcela = (valor_parcela * body.comissao_pct).quantize(Decimal("0.01"))

    proposta = Proposta(
        id=uuid.uuid4(),
        cotacao_id=cotacao_id,
        protocolo=resultado.protocolo,
        comissao_pct=body.comissao_pct,
        plano_pagamento=body.plano_pagamento,
        n_parcelas=body.n_parcelas,
        valor_parcela=valor_parcela,
        comissao_parcela=comissao_parcela,
        inicio_vigencia=body.inicio_vigencia,
        usuario_id=usuario.id,
    )
    db.add(proposta)

    db.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="proposta.transmitida",
            payload={
                "protocolo": resultado.protocolo,
                "cotacao_id": str(cotacao_id),
                "proposta_id": str(proposta.id),
            },
            usuario_id=usuario.id,
        )
    )

    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "proposta.transmitida",
        {"protocolo": resultado.protocolo, "cotacao_id": str(cotacao_id)},
        usuario_id=usuario.id,
        ip_origem=ip,
    )

    await db.commit()
    await db.refresh(proposta)
    return _proposta_out(proposta)


@router.get("/propostas/{proposta_id}", response_model=PropostaOut)
async def obter_proposta(
    proposta_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PropostaOut:
    return _proposta_out(await _get_proposta_ou_404(proposta_id, usuario.id, db))


@router.get("/propostas/{proposta_id}/parcelas", response_model=list[ParcelaOut])
async def listar_parcelas(
    proposta_id: uuid.UUID,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ParcelaOut]:
    p = await _get_proposta_ou_404(proposta_id, usuario.id, db)
    parcelas: list[ParcelaOut] = []
    for i in range(p.n_parcelas):
        vencimento: date | None = None
        if p.inicio_vigencia is not None:
            vencimento = p.inicio_vigencia + timedelta(days=30 * i)
        parcelas.append(
            ParcelaOut(
                numero=i + 1,
                vencimento=vencimento,
                valor=p.valor_parcela,
                comissao=p.comissao_parcela,
            )
        )
    return parcelas
