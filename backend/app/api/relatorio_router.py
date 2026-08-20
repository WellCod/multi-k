"""Rotas de relatórios — produção, funil, mix e exports CSV/XLSX."""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser
from app.infra.db import get_db
from app.infra.models import Cotacao, Proposta, Usuario

router = APIRouter(prefix="/relatorios", tags=["relatorios"])


# ---------------------------------------------------------------------------
# Schemas de saída
# ---------------------------------------------------------------------------


class ProducaoOut(BaseModel):
    corretor_id: uuid.UUID
    corretor_nome: str
    cotacoes: int
    propostas: int
    taxa_conversao: Decimal  # propostas / cotacoes
    premio_total: Decimal
    comissao_prevista: Decimal


class FunilRamoOut(BaseModel):
    ramo: str
    cotacoes: int
    com_proposta: int
    taxa_conversao: Decimal
    premio_medio: Decimal


class FunilOut(BaseModel):
    total_cotacoes: int
    total_com_proposta: int
    taxa_conversao_geral: Decimal
    por_ramo: list[FunilRamoOut]


class MixOut(BaseModel):
    ramo: str
    count: int
    pct: Decimal
    premio_total: Decimal


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _corte(periodo: int) -> datetime:
    """Retorna o datetime de início do período consultado."""
    return datetime.now(UTC) - timedelta(days=periodo)


def _pct(num: int, den: int) -> Decimal:
    if den == 0:
        return Decimal("0.00")
    return (Decimal(num) / Decimal(den) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _taxa(num: int, den: int) -> Decimal:
    if den == 0:
        return Decimal("0.0000")
    return (Decimal(num) / Decimal(den)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


async def _dados_producao(
    db: AsyncSession,
    periodo: int,
    usuario_id: uuid.UUID | None = None,
) -> list[ProducaoOut]:
    """Monta relatório de produção por corretor no período."""
    corte = _corte(periodo)

    # Cotações no período
    q_cot = select(Cotacao).where(Cotacao.criado_em >= corte)
    if usuario_id is not None:
        q_cot = q_cot.where(Cotacao.usuario_id == usuario_id)
    res_cot = await db.execute(q_cot)
    cotacoes = res_cot.scalars().all()

    # Propostas no período
    q_prop = select(Proposta).where(Proposta.transmitida_em >= corte)
    if usuario_id is not None:
        q_prop = q_prop.where(Proposta.usuario_id == usuario_id)
    res_prop = await db.execute(q_prop)
    propostas = res_prop.scalars().all()

    # Mapa de cotações para buscar prêmio
    cot_map: dict[uuid.UUID, Cotacao] = {c.id: c for c in cotacoes}

    # Mapa de usuários
    res_u = await db.execute(select(Usuario))
    usuarios_map: dict[uuid.UUID, str] = {u.id: u.nome for u in res_u.scalars().all()}

    # Agrupa por corretor
    por_corretor: dict[uuid.UUID, dict[str, int | Decimal]] = {}

    for cot in cotacoes:
        uid = cot.usuario_id
        if uid not in por_corretor:
            por_corretor[uid] = {
                "cotacoes": 0,
                "propostas": 0,
                "premio_total": Decimal("0"),
                "comissao_prevista": Decimal("0"),
            }
        por_corretor[uid]["cotacoes"] = int(por_corretor[uid]["cotacoes"]) + 1

    for prop in propostas:
        uid = prop.usuario_id
        if uid not in por_corretor:
            por_corretor[uid] = {
                "cotacoes": 0,
                "propostas": 0,
                "premio_total": Decimal("0"),
                "comissao_prevista": Decimal("0"),
            }
        por_corretor[uid]["propostas"] = int(por_corretor[uid]["propostas"]) + 1
        cot_opt = cot_map.get(prop.cotacao_id)
        premio = (cot_opt.premio_total if cot_opt else None) or Decimal("0")
        por_corretor[uid]["premio_total"] = (
            Decimal(str(por_corretor[uid]["premio_total"])) + premio
        )
        comissao = (prop.comissao_parcela * prop.n_parcelas).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        por_corretor[uid]["comissao_prevista"] = (
            Decimal(str(por_corretor[uid]["comissao_prevista"])) + comissao
        )

    saida: list[ProducaoOut] = []
    for uid, v in por_corretor.items():
        cots = int(v["cotacoes"])
        props = int(v["propostas"])
        saida.append(
            ProducaoOut(
                corretor_id=uid,
                corretor_nome=usuarios_map.get(uid, str(uid)),
                cotacoes=cots,
                propostas=props,
                taxa_conversao=_taxa(props, cots),
                premio_total=Decimal(str(v["premio_total"])),
                comissao_prevista=Decimal(str(v["comissao_prevista"])),
            )
        )
    return saida


async def _dados_funil(
    db: AsyncSession,
    periodo: int,
    usuario_id: uuid.UUID | None = None,
) -> FunilOut:
    """Calcula funil de conversão por ramo no período."""
    corte = _corte(periodo)

    q_cot = select(Cotacao).where(Cotacao.criado_em >= corte)
    if usuario_id is not None:
        q_cot = q_cot.where(Cotacao.usuario_id == usuario_id)
    res_cot = await db.execute(q_cot)
    cotacoes = res_cot.scalars().all()

    q_prop = select(Proposta).where(Proposta.transmitida_em >= corte)
    if usuario_id is not None:
        q_prop = q_prop.where(Proposta.usuario_id == usuario_id)
    res_prop = await db.execute(q_prop)
    propostas = res_prop.scalars().all()

    # cotacao_id das propostas no período
    ids_com_prop: set[uuid.UUID] = {p.cotacao_id for p in propostas}

    # Agrupa por ramo
    ramo_cots: dict[str, list[Cotacao]] = {}
    for c in cotacoes:
        ramo_cots.setdefault(c.ramo, []).append(c)

    por_ramo: list[FunilRamoOut] = []
    for ramo, cots in ramo_cots.items():
        com_prop = sum(1 for c in cots if c.id in ids_com_prop)
        premios = [c.premio_total for c in cots if c.premio_total is not None]
        premio_medio = (
            sum(premios, Decimal("0")) / len(premios) if premios else Decimal("0")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        por_ramo.append(
            FunilRamoOut(
                ramo=ramo,
                cotacoes=len(cots),
                com_proposta=com_prop,
                taxa_conversao=_taxa(com_prop, len(cots)),
                premio_medio=premio_medio,
            )
        )

    total_cots = len(cotacoes)
    total_prop = len(ids_com_prop)
    return FunilOut(
        total_cotacoes=total_cots,
        total_com_proposta=total_prop,
        taxa_conversao_geral=_taxa(total_prop, total_cots),
        por_ramo=por_ramo,
    )


async def _dados_mix(
    db: AsyncSession,
    periodo: int,
    usuario_id: uuid.UUID | None = None,
) -> list[MixOut]:
    """Distribuição por ramo no período, ordenada por volume."""
    corte = _corte(periodo)

    q_prop = (
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.transmitida_em >= corte)
    )
    if usuario_id is not None:
        q_prop = q_prop.where(Proposta.usuario_id == usuario_id)
    res = await db.execute(q_prop)

    ramo_stats: dict[str, dict[str, int | Decimal]] = {}
    for _prop, cotacao in res.all():
        r = cotacao.ramo
        if r not in ramo_stats:
            ramo_stats[r] = {"count": 0, "premio_total": Decimal("0")}
        ramo_stats[r]["count"] = int(ramo_stats[r]["count"]) + 1
        ramo_stats[r]["premio_total"] = Decimal(str(ramo_stats[r]["premio_total"])) + (
            cotacao.premio_total or Decimal("0")
        )

    total = sum(int(v["count"]) for v in ramo_stats.values())
    saida = sorted(
        [
            MixOut(
                ramo=r,
                count=int(v["count"]),
                pct=_pct(int(v["count"]), total),
                premio_total=Decimal(str(v["premio_total"])),
            )
            for r, v in ramo_stats.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )
    return saida


# ---------------------------------------------------------------------------
# Endpoints de leitura
# ---------------------------------------------------------------------------


@router.get("/producao", response_model=list[ProducaoOut])
async def relatorio_producao(
    usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    periodo: int = Query(default=30, ge=7, le=365),
) -> list[ProducaoOut]:
    """Produção por corretor — admin apenas."""
    return await _dados_producao(db, periodo)


@router.get("/funil", response_model=FunilOut)
async def relatorio_funil(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    periodo: int = Query(default=30, ge=7, le=365),
) -> FunilOut:
    """Funil de conversão. Corretor vê apenas seus dados; admin vê tudo."""
    uid = None if usuario.papel == "admin" else usuario.id
    return await _dados_funil(db, periodo, uid)


@router.get("/mix", response_model=list[MixOut])
async def relatorio_mix(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    periodo: int = Query(default=30, ge=7, le=365),
) -> list[MixOut]:
    """Mix por ramo. Corretor vê apenas seus dados; admin vê tudo."""
    uid = None if usuario.papel == "admin" else usuario.id
    return await _dados_mix(db, periodo, uid)


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------


@router.get("/export/csv")
async def export_csv(
    usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    tipo: str = Query(pattern="^(producao|funil|mix)$"),
    periodo: int = Query(default=30, ge=7, le=365),
) -> StreamingResponse:
    """Exporta relatório em CSV. Admin apenas."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    if tipo == "producao":
        dados = await _dados_producao(db, periodo)
        writer.writerow(
            [
                "corretor_id",
                "corretor_nome",
                "cotacoes",
                "propostas",
                "taxa_conversao",
                "premio_total",
                "comissao_prevista",
            ]
        )
        for d in dados:
            writer.writerow(
                [
                    str(d.corretor_id),
                    d.corretor_nome,
                    d.cotacoes,
                    d.propostas,
                    str(d.taxa_conversao),
                    str(d.premio_total),
                    str(d.comissao_prevista),
                ]
            )

    elif tipo == "funil":
        funil = await _dados_funil(db, periodo)
        writer.writerow(
            [
                "ramo",
                "cotacoes",
                "com_proposta",
                "taxa_conversao",
                "premio_medio",
            ]
        )
        for r in funil.por_ramo:
            writer.writerow(
                [
                    r.ramo,
                    r.cotacoes,
                    r.com_proposta,
                    str(r.taxa_conversao),
                    str(r.premio_medio),
                ]
            )

    else:  # mix
        mix = await _dados_mix(db, periodo)
        writer.writerow(["ramo", "count", "pct", "premio_total"])
        for m in mix:
            writer.writerow([m.ramo, m.count, str(m.pct), str(m.premio_total)])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={tipo}_{periodo}d.csv"},
    )


# ---------------------------------------------------------------------------
# Export XLSX
# ---------------------------------------------------------------------------


@router.get("/export/xlsx")
async def export_xlsx(
    usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    tipo: str = Query(pattern="^(producao|funil|mix)$"),
    periodo: int = Query(default=30, ge=7, le=365),
) -> StreamingResponse:
    """Exporta relatório em XLSX (openpyxl). Admin apenas."""
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError as err:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=501,
            detail="openpyxl não instalado. Execute: pip install openpyxl",
        ) from err

    wb = openpyxl.Workbook()
    ws = wb.active

    if tipo == "producao":
        ws.title = "Producao"
        dados = await _dados_producao(db, periodo)
        ws.append(
            [
                "Corretor ID",
                "Corretor Nome",
                "Cotações",
                "Propostas",
                "Taxa Conversão",
                "Prêmio Total",
                "Comissão Prevista",
            ]
        )
        for d in dados:
            ws.append(
                [
                    str(d.corretor_id),
                    d.corretor_nome,
                    d.cotacoes,
                    d.propostas,
                    float(d.taxa_conversao),
                    float(d.premio_total),
                    float(d.comissao_prevista),
                ]
            )

    elif tipo == "funil":
        ws.title = "Funil"
        funil = await _dados_funil(db, periodo)
        ws.append(
            [
                "Ramo",
                "Cotações",
                "Com Proposta",
                "Taxa Conversão",
                "Prêmio Médio",
            ]
        )
        for r in funil.por_ramo:
            ws.append(
                [
                    r.ramo,
                    r.cotacoes,
                    r.com_proposta,
                    float(r.taxa_conversao),
                    float(r.premio_medio),
                ]
            )

    else:  # mix
        ws.title = "Mix"
        mix = await _dados_mix(db, periodo)
        ws.append(["Ramo", "Qtd", "Pct (%)", "Prêmio Total"])
        for m in mix:
            ws.append([m.ramo, m.count, float(m.pct), float(m.premio_total)])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (f"attachment; filename={tipo}_{periodo}d.xlsx")
        },
    )
