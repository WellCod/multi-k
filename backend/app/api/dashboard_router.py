"""Rota de dashboard de métricas — corretor e admin."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra.db import get_db
from app.infra.models import Cotacao, CotacaoJob, Proposta

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardRamoOut(BaseModel):
    ramo: str
    cotacoes: int
    propostas: int
    premio_total: Decimal


class DashboardCiaOut(BaseModel):
    cia: str
    cotacoes: int
    propostas: int
    premio_total: Decimal


class DashboardOut(BaseModel):
    total_cotacoes: int
    total_propostas: int
    taxa_conversao: Decimal
    ticket_medio: Decimal
    por_ramo: list[DashboardRamoOut]
    ranking_cias: list[DashboardCiaOut]


def _corte(periodo: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=periodo)


def _taxa(num: int, den: int) -> Decimal:
    if den == 0:
        return Decimal("0.0000")
    return (Decimal(num) / Decimal(den)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


async def _calcular_dashboard(
    db: AsyncSession,
    inicio: datetime,
    usuario_id: uuid.UUID | None,
    is_admin: bool,
) -> DashboardOut:
    q_cot = (
        select(Cotacao)
        .where(Cotacao.criado_em >= inicio)
        .limit(10_000)
    )
    if usuario_id is not None:
        q_cot = q_cot.where(Cotacao.usuario_id == usuario_id)
    res_cot = await db.execute(q_cot)
    cotacoes = res_cot.scalars().all()

    q_prop = (
        select(Proposta)
        .where(Proposta.transmitida_em >= inicio)
        .limit(10_000)
    )
    if usuario_id is not None:
        q_prop = q_prop.where(Proposta.usuario_id == usuario_id)
    res_prop = await db.execute(q_prop)
    propostas = res_prop.scalars().all()

    ids_com_prop: set[uuid.UUID] = {p.cotacao_id for p in propostas}
    cot_map: dict[uuid.UUID, Cotacao] = {c.id: c for c in cotacoes}

    total_cotacoes = len(cotacoes)
    total_propostas = len(ids_com_prop)

    premios_aprovados = [
        c.premio_total
        for c in cotacoes
        if c.id in ids_com_prop and c.premio_total is not None
    ]
    ticket_medio = (
        (sum(premios_aprovados, Decimal("0")) / len(premios_aprovados)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if premios_aprovados
        else Decimal("0.00")
    )

    ramo_stats: dict[str, dict[str, int | Decimal]] = {}
    for c in cotacoes:
        r = c.ramo
        if r not in ramo_stats:
            ramo_stats[r] = {
                "cotacoes": 0,
                "propostas": 0,
                "premio_total": Decimal("0"),
            }
        ramo_stats[r]["cotacoes"] = int(ramo_stats[r]["cotacoes"]) + 1
        if c.id in ids_com_prop:
            ramo_stats[r]["propostas"] = int(ramo_stats[r]["propostas"]) + 1
            ramo_stats[r]["premio_total"] = Decimal(
                str(ramo_stats[r]["premio_total"])
            ) + (c.premio_total or Decimal("0"))

    por_ramo = [
        DashboardRamoOut(
            ramo=r,
            cotacoes=int(v["cotacoes"]),
            propostas=int(v["propostas"]),
            premio_total=Decimal(str(v["premio_total"])),
        )
        for r, v in ramo_stats.items()
    ]

    ranking_cias: list[DashboardCiaOut] = []
    if is_admin:
        q_jobs = (
            select(CotacaoJob)
            .where(CotacaoJob.criado_em >= inicio)
            .limit(10_000)
        )
        res_jobs = await db.execute(q_jobs)
        jobs = res_jobs.scalars().all()

        cia_stats: dict[str, dict[str, int | Decimal]] = {}
        for job in jobs:
            cia = job.cia
            if cia not in cia_stats:
                cia_stats[cia] = {
                    "cotacoes": 0,
                    "propostas": 0,
                    "premio_total": Decimal("0"),
                }
            cia_stats[cia]["cotacoes"] = int(cia_stats[cia]["cotacoes"]) + 1
            cot = cot_map.get(job.cotacao_id)
            if cot is not None and cot.id in ids_com_prop:
                cia_stats[cia]["propostas"] = int(cia_stats[cia]["propostas"]) + 1
                cia_stats[cia]["premio_total"] = Decimal(
                    str(cia_stats[cia]["premio_total"])
                ) + (job.premio_total or Decimal("0"))

        ranking_cias = sorted(
            [
                DashboardCiaOut(
                    cia=cia,
                    cotacoes=int(v["cotacoes"]),
                    propostas=int(v["propostas"]),
                    premio_total=Decimal(str(v["premio_total"])),
                )
                for cia, v in cia_stats.items()
            ],
            key=lambda x: x.premio_total,
            reverse=True,
        )

    return DashboardOut(
        total_cotacoes=total_cotacoes,
        total_propostas=total_propostas,
        taxa_conversao=_taxa(total_propostas, total_cotacoes),
        ticket_medio=ticket_medio,
        por_ramo=por_ramo,
        ranking_cias=ranking_cias,
    )


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    periodo: int = Query(default=30, ge=1, le=365),
) -> DashboardOut:
    """Métricas do corretor (ou tenant-wide para admin)."""
    is_admin = usuario.papel == "admin"
    uid = None if is_admin else usuario.id
    inicio = _corte(periodo)
    return await _calcular_dashboard(db, inicio, uid, is_admin)
