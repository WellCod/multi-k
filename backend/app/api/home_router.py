"""Rotas da home — fila de trabalho do corretor e KPIs do admin."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
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
    """KPIs da carteira — visível apenas para admins."""
    hoje = date.today()

    # Busca propostas (cap de segurança — 50k registros)
    res_props = await db.execute(
        select(Proposta, Cotacao)
        .join(Cotacao, Proposta.cotacao_id == Cotacao.id)
        .limit(50_000)
    )
    todas_propostas = res_props.all()

    # Busca todos os corretores para montar o mapa nome → stats
    res_users = await db.execute(select(Usuario))
    usuarios_map: dict[uuid.UUID, str] = {
        u.id: u.nome for u in res_users.scalars().all()
    }

    # Propostas vigentes (inicio_vigencia + 365 > hoje)
    vigentes = [(p, c) for p, c in todas_propostas if _proposta_vigente(p, hoje)]

    segurados_vigentes = len(
        {c.cliente_id for _, c in vigentes if c.cliente_id is not None}
    )
    apolices_vigentes = len(vigentes)
    premio_liquido = sum((c.premio_total or Decimal("0")) for _, c in vigentes)

    comissao_produzida = sum(
        p.comissao_parcela * p.n_parcelas for p, _ in todas_propostas
    )

    # Cotações em andamento (aguardando/processando)
    res_cot = await db.execute(
        select(Cotacao).where(Cotacao.status.in_(["aguardando", "processando"]))
    )
    cotacoes_em_andamento = len(res_cot.scalars().all())

    # KPIs por ramo — somente propostas vigentes
    ramo_stats: dict[str, dict[str, Decimal | int]] = {}
    for _prop, cotacao in vigentes:
        r = cotacao.ramo
        if r not in ramo_stats:
            ramo_stats[r] = {"count": 0, "premio_total": Decimal("0")}
        ramo_stats[r]["count"] = int(ramo_stats[r]["count"]) + 1
        ramo_stats[r]["premio_total"] = Decimal(str(ramo_stats[r]["premio_total"])) + (
            cotacao.premio_total or Decimal("0")
        )
    por_ramo = [
        KpiRamo(
            ramo=r,
            count=int(v["count"]),
            premio_total=Decimal(str(v["premio_total"])),
        )
        for r, v in ramo_stats.items()
    ]

    # KPIs por corretor — todas as propostas
    corretor_stats: dict[uuid.UUID, dict[str, int | Decimal]] = {}
    for prop, cotacao in todas_propostas:
        uid = prop.usuario_id
        if uid not in corretor_stats:
            corretor_stats[uid] = {
                "propostas": 0,
                "premio_total": Decimal("0"),
            }
        corretor_stats[uid]["propostas"] = int(corretor_stats[uid]["propostas"]) + 1
        corretor_stats[uid]["premio_total"] = Decimal(
            str(corretor_stats[uid]["premio_total"])
        ) + (cotacao.premio_total or Decimal("0"))

    # Cotações por corretor (cap de segurança)
    res_cots_all = await db.execute(select(Cotacao).limit(50_000))
    for cot in res_cots_all.scalars().all():
        uid = cot.usuario_id
        if uid not in corretor_stats:
            corretor_stats[uid] = {
                "propostas": 0,
                "premio_total": Decimal("0"),
            }
        # campo cotacoes acumulado separadamente
        if "cotacoes" not in corretor_stats[uid]:
            corretor_stats[uid]["cotacoes"] = 0
        corretor_stats[uid]["cotacoes"] = (
            int(corretor_stats[uid].get("cotacoes", 0)) + 1
        )

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
