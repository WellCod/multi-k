"""Rotas de renovação — carteira próxima do vencimento (D-60/D-45/D-30)."""

import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import Cotacao, Proposta

router = APIRouter(prefix="/renovacoes", tags=["renovacoes"])

_VIGENCIA_DIAS = 365


class RenovacaoOut(BaseModel):
    proposta_id: uuid.UUID
    cotacao_id: uuid.UUID
    cliente_id: uuid.UUID | None
    protocolo: str
    ramo: str
    inicio_vigencia: date
    fim_vigencia: date
    dias_para_vencer: int
    janela: str  # "D60" | "D45" | "D30"
    premio_total: Decimal | None


def _janela(dias: int) -> str:
    if dias <= 30:
        return "D30"
    if dias <= 45:
        return "D45"
    return "D60"


async def _query_renovacoes(
    usuario_id: uuid.UUID,
    db: AsyncSession,
    dias: int,
    ramo: str | None,
    janela: str | None,
) -> list[RenovacaoOut]:
    result = await db.execute(
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.usuario_id == usuario_id)
        .where(Proposta.inicio_vigencia.is_not(None))
        .order_by(Proposta.inicio_vigencia)
    )

    hoje = date.today()
    renovacoes: list[RenovacaoOut] = []
    for proposta, cotacao in result.all():
        fim_vigencia = proposta.inicio_vigencia + timedelta(days=_VIGENCIA_DIAS)
        dias_para_vencer = (fim_vigencia - hoje).days
        if not (0 <= dias_para_vencer <= dias):
            continue
        j = _janela(dias_para_vencer)
        if ramo and cotacao.ramo != ramo:
            continue
        if janela and j != janela:
            continue
        renovacoes.append(
            RenovacaoOut(
                proposta_id=proposta.id,
                cotacao_id=proposta.cotacao_id,
                cliente_id=cotacao.cliente_id,
                protocolo=proposta.protocolo,
                ramo=cotacao.ramo,
                inicio_vigencia=proposta.inicio_vigencia,
                fim_vigencia=fim_vigencia,
                dias_para_vencer=dias_para_vencer,
                janela=j,
                premio_total=cotacao.premio_total,
            )
        )

    return renovacoes


class RenovacaoCountOut(BaseModel):
    D30: int
    D45: int
    D60: int
    total: int


@router.get("/count", response_model=RenovacaoCountOut)
async def contar_renovacoes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RenovacaoCountOut:
    """Contagem de renovações por janela — usado pelo badge do sidebar."""
    result = await db.execute(
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.usuario_id == usuario.id)
        .where(Proposta.inicio_vigencia.is_not(None))
    )
    hoje = date.today()
    d30 = d45 = d60 = 0
    for proposta, _cotacao in result.all():
        fim = proposta.inicio_vigencia + timedelta(days=_VIGENCIA_DIAS)
        dias = (fim - hoje).days
        if 0 <= dias <= 30:
            d30 += 1
        elif dias <= 45:
            d45 += 1
        elif dias <= 60:
            d60 += 1
    return RenovacaoCountOut(D30=d30, D45=d45, D60=d60, total=d30 + d45 + d60)


@router.get("/csv")
async def exportar_renovacoes_csv(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=60, ge=1, le=180),
    ramo: Annotated[str | None, Query()] = None,
    janela: Annotated[str | None, Query(pattern="^(D30|D45|D60)$")] = None,
) -> StreamingResponse:
    """Exporta renovações filtradas como CSV."""
    renovacoes = await _query_renovacoes(usuario.id, db, dias, ramo, janela)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "protocolo",
            "ramo",
            "inicio_vigencia",
            "fim_vigencia",
            "dias_para_vencer",
            "janela",
            "premio_total",
        ]
    )
    for r in renovacoes:
        writer.writerow(
            [
                r.protocolo,
                r.ramo,
                r.inicio_vigencia,
                r.fim_vigencia,
                r.dias_para_vencer,
                r.janela,
                str(r.premio_total or ""),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=renovacoes.csv"},
    )


@router.get("", response_model=list[RenovacaoOut])
async def listar_renovacoes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=60, ge=1, le=180),
    ramo: Annotated[str | None, Query()] = None,
    janela: Annotated[str | None, Query(pattern="^(D30|D45|D60)$")] = None,
) -> list[RenovacaoOut]:
    """Retorna propostas com vigência expirando nos próximos `dias` dias."""
    return await _query_renovacoes(usuario.id, db, dias, ramo, janela)
