"""Rotas de renovação — carteira próxima do vencimento (D-60/D-45/D-30)."""

import csv
import io
import uuid
from collections import Counter
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

# O badge do menu cobre até a janela mais distante, D60.
_HORIZONTE_BADGE_DIAS = 60


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
    """Janela de renovação para quem vence em `dias` dias.

    Só classifica: quem chama garante que a apólice ainda não venceu
    (`dias >= 0`) e está dentro do horizonte consultado.
    """
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
        inicio_vigencia = proposta.inicio_vigencia
        # A consulta já exclui propostas sem início de vigência; a checagem
        # existe para o mypy, que enxerga a coluna como `date | None`.
        if inicio_vigencia is None:
            continue
        fim_vigencia = inicio_vigencia + timedelta(days=_VIGENCIA_DIAS)
        dias_para_vencer = (fim_vigencia - hoje).days
        if not (0 <= dias_para_vencer <= dias):
            continue
        janela_da_proposta = _janela(dias_para_vencer)
        if ramo and cotacao.ramo != ramo:
            continue
        if janela and janela_da_proposta != janela:
            continue
        renovacoes.append(
            RenovacaoOut(
                proposta_id=proposta.id,
                cotacao_id=proposta.cotacao_id,
                cliente_id=cotacao.cliente_id,
                protocolo=proposta.protocolo,
                ramo=cotacao.ramo,
                inicio_vigencia=inicio_vigencia,
                fim_vigencia=fim_vigencia,
                dias_para_vencer=dias_para_vencer,
                janela=janela_da_proposta,
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
    """Contagem de renovações por janela — usado pelo badge do sidebar.

    Conta exatamente as apólices que a tela de renovações lista no horizonte
    padrão de 60 dias, reaproveitando a mesma consulta. Antes havia uma regra
    própria aqui, e ela contava apólices já vencidas como D45.
    """
    renovacoes = await _query_renovacoes(
        usuario.id, db, dias=_HORIZONTE_BADGE_DIAS, ramo=None, janela=None
    )
    quantidade_por_janela = Counter(renovacao.janela for renovacao in renovacoes)
    return RenovacaoCountOut(
        D30=quantidade_por_janela["D30"],
        D45=quantidade_por_janela["D45"],
        D60=quantidade_por_janela["D60"],
        total=len(renovacoes),
    )


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
