"""Rotas de renovação — carteira próxima do vencimento (D-60/D-45/D-30)."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
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


@router.get("", response_model=list[RenovacaoOut])
async def listar_renovacoes(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=60, ge=1, le=180),
) -> list[RenovacaoOut]:
    """Retorna propostas com vigência expirando nos próximos `dias` dias."""
    result = await db.execute(
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.usuario_id == usuario.id)
        .where(Proposta.inicio_vigencia.is_not(None))
        .order_by(Proposta.inicio_vigencia)
    )

    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    renovacoes: list[RenovacaoOut] = []
    for proposta, cotacao in result.all():
        if proposta.inicio_vigencia is None:
            continue
        fim_vigencia = proposta.inicio_vigencia + timedelta(days=_VIGENCIA_DIAS)
        dias_para_vencer = (fim_vigencia - hoje).days
        if 0 <= dias_para_vencer <= (limite - hoje).days:
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
                    janela=_janela(dias_para_vencer),
                    premio_total=cotacao.premio_total,
                )
            )

    return renovacoes
