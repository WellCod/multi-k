"""Rotas da home — fila de trabalho do corretor e KPIs do admin."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser
from app.infra.db import get_db
from app.infra.models import Cotacao, Proposta, Usuario

router = APIRouter(prefix="/home", tags=["home"])

_VIGENCIA_DIAS = 365
_JANELA_RENOVACAO_DIAS = 60


# ---------------------------------------------------------------------------
# Schemas — corretor
# ---------------------------------------------------------------------------


class ItemRenovacao(BaseModel):
    proposta_id: uuid.UUID
    cotacao_id: uuid.UUID
    cliente_id: uuid.UUID | None
    protocolo: str
    ramo: str
    inicio_vigencia: date
    fim_vigencia: date
    dias_para_vencer: int
    janela: str  # "D30" | "D45" | "D60"
    premio_total: Decimal | None


class ItemPropostaParada(BaseModel):
    cotacao_id: uuid.UUID
    cliente_id: uuid.UUID | None
    ramo: str
    status: str
    premio_total: Decimal | None
    criado_em: datetime


class ItemCotacaoAbandonada(BaseModel):
    cotacao_id: uuid.UUID
    cliente_id: uuid.UUID | None
    ramo: str
    status: str
    criado_em: datetime


class ItemParcelaVencendo(BaseModel):
    proposta_id: uuid.UUID
    protocolo: str
    numero_parcela: int
    vencimento: date
    valor: Decimal
    comissao: Decimal


class HomeCorretorOut(BaseModel):
    renovacoes: list[ItemRenovacao]
    propostas_paradas: list[ItemPropostaParada]
    cotacoes_abandonadas: list[ItemCotacaoAbandonada]
    parcelas_vencendo: list[ItemParcelaVencendo]


# ---------------------------------------------------------------------------
# Schemas — admin
# ---------------------------------------------------------------------------


class KpiRamo(BaseModel):
    ramo: str
    count: int
    premio_total: Decimal


class KpiCorretor(BaseModel):
    nome: str
    cotacoes: int
    propostas: int
    premio_total: Decimal


class HomeAdminOut(BaseModel):
    segurados_vigentes: int
    apolices_vigentes: int
    cotacoes_em_andamento: int
    premio_liquido: Decimal
    comissao_produzida: Decimal
    comissao_recebida: Decimal  # sempre 0 até FASE 7
    por_ramo: list[KpiRamo]
    por_corretor: list[KpiCorretor]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _janela(dias: int) -> str:
    if dias <= 30:
        return "D30"
    if dias <= 45:
        return "D45"
    return "D60"


def _fim_vigencia(inicio: date) -> date:
    return inicio + timedelta(days=_VIGENCIA_DIAS)


def _proposta_vigente(p: Proposta, hoje: date) -> bool:
    """Retorna True se a proposta ainda está dentro do período de vigência."""
    if p.inicio_vigencia is None:
        return False
    return _fim_vigencia(p.inicio_vigencia) > hoje


# ---------------------------------------------------------------------------
# GET /home/corretor
# ---------------------------------------------------------------------------


@router.get("/corretor", response_model=HomeCorretorOut)
async def home_corretor(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HomeCorretorOut:
    """Fila de trabalho do corretor logado."""
    hoje = date.today()
    agora = datetime.now(UTC)
    corte = agora - timedelta(days=2)

    # --- Renovações: propostas vencendo em até 60 dias (limite 20) ---
    res_props = await db.execute(
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.usuario_id == usuario.id)
        .where(Proposta.inicio_vigencia.is_not(None))
        .order_by(Proposta.inicio_vigencia)
    )
    renovacoes: list[ItemRenovacao] = []
    for proposta, cotacao in res_props.all():
        if proposta.inicio_vigencia is None:
            continue
        fim = _fim_vigencia(proposta.inicio_vigencia)
        dias = (fim - hoje).days
        if 0 <= dias <= _JANELA_RENOVACAO_DIAS:
            renovacoes.append(
                ItemRenovacao(
                    proposta_id=proposta.id,
                    cotacao_id=proposta.cotacao_id,
                    cliente_id=cotacao.cliente_id,
                    protocolo=proposta.protocolo,
                    ramo=cotacao.ramo,
                    inicio_vigencia=proposta.inicio_vigencia,
                    fim_vigencia=fim,
                    dias_para_vencer=dias,
                    janela=_janela(dias),
                    premio_total=cotacao.premio_total,
                )
            )
        if len(renovacoes) >= 20:
            break

    # --- IDs de cotações que já têm proposta (do usuário) ---
    res_com_prop = await db.execute(
        select(Proposta.cotacao_id).where(Proposta.usuario_id == usuario.id)
    )
    ids_com_proposta: set[uuid.UUID] = {r for (r,) in res_com_prop.all()}

    # --- Propostas paradas: sucesso/restricao sem proposta há 2+ dias ---
    res_paradas = await db.execute(
        select(Cotacao)
        .where(Cotacao.usuario_id == usuario.id)
        .where(Cotacao.status.in_(["sucesso", "restricao"]))
        .where(Cotacao.criado_em < corte)
        .order_by(Cotacao.criado_em.desc())
        .limit(20)
    )
    propostas_paradas: list[ItemPropostaParada] = []
    for cot in res_paradas.scalars().all():
        if cot.id not in ids_com_proposta:
            propostas_paradas.append(
                ItemPropostaParada(
                    cotacao_id=cot.id,
                    cliente_id=cot.cliente_id,
                    ramo=cot.ramo,
                    status=cot.status,
                    premio_total=cot.premio_total,
                    criado_em=cot.criado_em,
                )
            )

    # --- Cotações abandonadas: aguardando/processando há 2+ dias ---
    res_aband = await db.execute(
        select(Cotacao)
        .where(Cotacao.usuario_id == usuario.id)
        .where(Cotacao.status.in_(["aguardando", "processando"]))
        .where(Cotacao.criado_em < corte)
        .order_by(Cotacao.criado_em.desc())
        .limit(10)
    )
    cotacoes_abandonadas: list[ItemCotacaoAbandonada] = [
        ItemCotacaoAbandonada(
            cotacao_id=c.id,
            cliente_id=c.cliente_id,
            ramo=c.ramo,
            status=c.status,
            criado_em=c.criado_em,
        )
        for c in res_aband.scalars().all()
    ]

    # --- Parcelas vencendo nos próximos 30 dias ---
    limite_parc = hoje + timedelta(days=30)
    res_all_props = await db.execute(
        select(Proposta)
        .where(Proposta.usuario_id == usuario.id)
        .where(Proposta.inicio_vigencia.is_not(None))
    )
    parcelas_vencendo: list[ItemParcelaVencendo] = []
    for prop in res_all_props.scalars().all():
        if prop.inicio_vigencia is None:
            continue
        for i in range(prop.n_parcelas):
            venc = prop.inicio_vigencia + timedelta(days=30 * i)
            if hoje <= venc <= limite_parc:
                parcelas_vencendo.append(
                    ItemParcelaVencendo(
                        proposta_id=prop.id,
                        protocolo=prop.protocolo,
                        numero_parcela=i + 1,
                        vencimento=venc,
                        valor=prop.valor_parcela,
                        comissao=prop.comissao_parcela,
                    )
                )
        if len(parcelas_vencendo) >= 20:
            break

    return HomeCorretorOut(
        renovacoes=renovacoes,
        propostas_paradas=propostas_paradas,
        cotacoes_abandonadas=cotacoes_abandonadas,
        parcelas_vencendo=parcelas_vencendo,
    )


# ---------------------------------------------------------------------------
# GET /home/admin
# ---------------------------------------------------------------------------


@router.get("/admin", response_model=HomeAdminOut)
async def home_admin(
    usuario: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HomeAdminOut:
    """KPIs da carteira — visível apenas para admins. Aggregate queries, sem N+1."""
    hoje = date.today()
    # propostas com inicio_vigencia + 365 > hoje ↔ inicio_vigencia > hoje - 365
    corte_vigencia = hoje - timedelta(days=_VIGENCIA_DIAS)

    # --- Segurados e apólices vigentes + prêmio líquido ---
    res_vigentes = await db.execute(
        select(
            func.count(Proposta.id).label("apolices"),
            func.count(func.distinct(Cotacao.cliente_id)).label("segurados"),
            func.coalesce(func.sum(Cotacao.premio_total), Decimal("0")).label("premio"),
        )
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.inicio_vigencia.is_not(None))
        .where(Proposta.inicio_vigencia > corte_vigencia)
    )
    row_vig = res_vigentes.one()
    apolices_vigentes = int(row_vig.apolices)
    segurados_vigentes = int(row_vig.segurados)
    premio_liquido = Decimal(str(row_vig.premio or "0"))

    # --- Comissão produzida ---
    res_comissao = await db.execute(
        select(
            func.coalesce(
                func.sum(Proposta.comissao_parcela * Proposta.n_parcelas), Decimal("0")
            ).label("total")
        )
    )
    comissao_produzida = Decimal(str(res_comissao.scalar_one() or "0"))

    # --- Cotações em andamento ---
    res_andamento = await db.execute(
        select(func.count(Cotacao.id)).where(
            Cotacao.status.in_(["aguardando", "processando"])
        )
    )
    cotacoes_em_andamento = int(res_andamento.scalar_one())

    # --- KPIs por ramo (propostas vigentes) ---
    res_ramo = await db.execute(
        select(
            Cotacao.ramo,
            func.count(Proposta.id).label("count"),
            func.coalesce(func.sum(Cotacao.premio_total), Decimal("0")).label("premio"),
        )
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .where(Proposta.inicio_vigencia.is_not(None))
        .where(Proposta.inicio_vigencia > corte_vigencia)
        .group_by(Cotacao.ramo)
    )
    por_ramo = [
        KpiRamo(
            ramo=r.ramo,
            count=int(r.count),
            premio_total=Decimal(str(r.premio or "0")),
        )
        for r in res_ramo.all()
    ]

    # --- KPIs por corretor: propostas + prêmio ---
    res_corretor = await db.execute(
        select(
            Proposta.usuario_id,
            func.count(Proposta.id).label("propostas"),
            func.coalesce(func.sum(Cotacao.premio_total), Decimal("0")).label("premio"),
        )
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .group_by(Proposta.usuario_id)
    )
    corretor_stats: dict[uuid.UUID, dict[str, int | Decimal]] = {
        r.usuario_id: {
            "propostas": int(r.propostas),
            "premio_total": Decimal(str(r.premio or "0")),
            "cotacoes": 0,
        }
        for r in res_corretor.all()
    }

    # Cotações por corretor
    res_cot_corretor = await db.execute(
        select(Cotacao.usuario_id, func.count(Cotacao.id).label("cotacoes"))
        .group_by(Cotacao.usuario_id)
    )
    for r in res_cot_corretor.all():
        if r.usuario_id not in corretor_stats:
            corretor_stats[r.usuario_id] = {
                "propostas": 0,
                "premio_total": Decimal("0"),
                "cotacoes": 0,
            }
        corretor_stats[r.usuario_id]["cotacoes"] = int(r.cotacoes)

    # Nomes dos corretores
    res_users = await db.execute(select(Usuario.id, Usuario.nome))
    usuarios_map: dict[uuid.UUID, str] = {r.id: r.nome for r in res_users.all()}

    por_corretor = [
        KpiCorretor(
            nome=usuarios_map.get(uid, str(uid)),
            cotacoes=int(v.get("cotacoes", 0)),
            propostas=int(v["propostas"]),
            premio_total=Decimal(str(v["premio_total"])),
        )
        for uid, v in corretor_stats.items()
    ]

    return HomeAdminOut(
        segurados_vigentes=segurados_vigentes,
        apolices_vigentes=apolices_vigentes,
        cotacoes_em_andamento=cotacoes_em_andamento,
        premio_liquido=premio_liquido,
        comissao_produzida=comissao_produzida,
        comissao_recebida=Decimal("0"),
        por_ramo=por_ramo,
        por_corretor=por_corretor,
    )
