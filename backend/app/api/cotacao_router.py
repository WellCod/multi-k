"""Rotas de cotação — usa PortaSeguradora via injeção de dependência."""

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import PortaSeguradora, RiscoCanonico
from app.adapters.fake.adapter import FakeSeguradora
from app.api.deps import CurrentUser
from app.infra import audit
from app.infra.db import get_db
from app.infra.models import EventoDB

router = APIRouter(prefix="/cotacoes", tags=["cotacoes"])


def get_adapter() -> PortaSeguradora:
    return FakeSeguradora()


class RiscoInput(BaseModel):
    ramo: str
    dados: dict[str, Any]


class RestricaoOut(BaseModel):
    codigo: str
    mensagem: str


class ResultadoCotacaoOut(BaseModel):
    sucesso: bool
    cotacao_id: str | None
    premio_total: Decimal | None
    restricoes: list[RestricaoOut]
    mensagens: list[str]
    necessita_vistoria: bool


@router.post("", response_model=ResultadoCotacaoOut)
async def criar_cotacao(
    body: RiscoInput,
    request: Request,
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    adapter: Annotated[PortaSeguradora, Depends(get_adapter)],
) -> ResultadoCotacaoOut:
    risco = RiscoCanonico(ramo=body.ramo, dados=body.dados)
    resultado = await adapter.cotar(risco)

    db.add(
        EventoDB(
            id=uuid.uuid4(),
            tipo="cotacao.criada",
            payload={
                "ramo": risco.ramo,
                "cotacao_id": resultado.cotacao_id,
                "sucesso": resultado.sucesso,
            },
            usuario_id=usuario.id,
        )
    )
    ip = request.client.host if request.client else None
    await audit.registrar(
        db,
        "cotacao",
        {"ramo": risco.ramo, "sucesso": resultado.sucesso},
        usuario_id=usuario.id,
        ip_origem=ip,
    )
    await db.commit()

    return ResultadoCotacaoOut(
        sucesso=resultado.sucesso,
        cotacao_id=resultado.cotacao_id,
        premio_total=resultado.premio_total,
        restricoes=[
            RestricaoOut(codigo=r.codigo, mensagem=r.mensagem)
            for r in resultado.restricoes
        ],
        mensagens=resultado.mensagens,
        necessita_vistoria=resultado.necessita_vistoria,
    )
