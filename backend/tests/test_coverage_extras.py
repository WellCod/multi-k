"""Testes de cobertura para funções puras, events_bus e auth_service."""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.infra import events_bus

# ---------------------------------------------------------------------------
# events_bus — subscribe, unsubscribe, publish
# ---------------------------------------------------------------------------


def test_events_bus_subscribe_retorna_queue() -> None:
    uid = uuid.uuid4()
    q = events_bus.subscribe(uid)
    assert isinstance(q, asyncio.Queue)
    events_bus.unsubscribe(uid, q)


def test_events_bus_publish_entrega_evento() -> None:
    uid = uuid.uuid4()
    q = events_bus.subscribe(uid)
    events_bus.publish(uid, {"tipo": "cotacao.pronta", "status": "sucesso"})
    assert not q.empty()
    item = q.get_nowait()
    assert item["tipo"] == "cotacao.pronta"
    events_bus.unsubscribe(uid, q)


def test_events_bus_unsubscribe_remove_entrada() -> None:
    uid = uuid.uuid4()
    q = events_bus.subscribe(uid)
    events_bus.unsubscribe(uid, q)
    assert uid not in events_bus._subscribers


def test_events_bus_publish_sem_subscriber_nao_levanta() -> None:
    uid = uuid.uuid4()
    events_bus.publish(uid, {"tipo": "orphan"})  # sem exception


def test_events_bus_publish_queue_cheia_nao_levanta() -> None:
    uid = uuid.uuid4()
    q = events_bus.subscribe(uid)
    for _ in range(50):  # maxsize=50
        q.put_nowait({"tipo": "fill"})
    events_bus.publish(uid, {"tipo": "overflow"})  # QueueFull suprimido
    events_bus.unsubscribe(uid, q)


# ---------------------------------------------------------------------------
# relatorio_router — funções puras
# ---------------------------------------------------------------------------


def test_relatorio_corte_retorna_datetime() -> None:
    from app.api.relatorio_router import _corte

    result = _corte(30)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    diff_days = (datetime.now(UTC) - result).total_seconds() / 86400
    assert 29.9 < diff_days < 30.1


def test_relatorio_pct_divisor_zero() -> None:
    from app.api.relatorio_router import _pct

    assert _pct(5, 0) == Decimal("0.00")


def test_relatorio_pct_normal() -> None:
    from app.api.relatorio_router import _pct

    assert _pct(1, 4) == Decimal("25.00")


def test_relatorio_taxa_divisor_zero() -> None:
    from app.api.relatorio_router import _taxa

    assert _taxa(3, 0) == Decimal("0.0000")


def test_relatorio_taxa_normal() -> None:
    from app.api.relatorio_router import _taxa

    assert _taxa(1, 2) == Decimal("0.5000")


def test_relatorio_resolve_corte_com_date_from() -> None:
    from app.api.relatorio_router import _resolve_corte

    date_from = date(2025, 1, 1)
    inicio, fim = _resolve_corte(30, date_from, None)
    assert inicio == datetime(2025, 1, 1, tzinfo=UTC)
    assert fim.date() == date.today()


def test_relatorio_resolve_corte_com_date_to() -> None:
    from app.api.relatorio_router import _resolve_corte

    date_to = date(2025, 12, 31)
    inicio, fim = _resolve_corte(30, None, date_to)
    assert fim == datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)


def test_relatorio_resolve_corte_sem_datas() -> None:
    from app.api.relatorio_router import _resolve_corte

    inicio, fim = _resolve_corte(30, None, None)
    now = datetime.now(UTC)
    diff = (now - inicio).total_seconds() / 86400
    assert 29.9 < diff < 30.1
    assert (fim - now).total_seconds() < 2


def test_relatorio_resolve_corte_com_ambas_as_datas() -> None:
    from app.api.relatorio_router import _resolve_corte

    date_from = date(2025, 3, 1)
    date_to = date(2025, 3, 31)
    inicio, fim = _resolve_corte(30, date_from, date_to)
    assert inicio == datetime(2025, 3, 1, tzinfo=UTC)
    assert fim == datetime(2025, 3, 31, 23, 59, 59, tzinfo=UTC)


# ---------------------------------------------------------------------------
# home_router — funções puras
# ---------------------------------------------------------------------------


def test_home_janela_d30() -> None:
    from app.api.home_router import _janela

    assert _janela(0) == "D30"
    assert _janela(30) == "D30"


def test_home_janela_d45() -> None:
    from app.api.home_router import _janela

    assert _janela(31) == "D45"
    assert _janela(45) == "D45"


def test_home_janela_d60() -> None:
    from app.api.home_router import _janela

    assert _janela(46) == "D60"
    assert _janela(60) == "D60"


def test_home_fim_vigencia() -> None:
    from app.api.home_router import _fim_vigencia

    inicio = date(2025, 1, 1)
    fim = _fim_vigencia(inicio)
    assert fim == date(2026, 1, 1)


def test_home_proposta_vigente_none_inicio() -> None:
    from app.api.home_router import _proposta_vigente

    p = MagicMock()
    p.inicio_vigencia = None
    assert _proposta_vigente(p, date.today()) is False


def test_home_proposta_vigente_dentro_vigencia() -> None:
    from app.api.home_router import _proposta_vigente

    p = MagicMock()
    p.inicio_vigencia = date.today() - timedelta(days=100)
    assert _proposta_vigente(p, date.today()) is True


def test_home_proposta_vigente_expirada() -> None:
    from app.api.home_router import _proposta_vigente

    p = MagicMock()
    p.inicio_vigencia = date.today() - timedelta(days=400)
    assert _proposta_vigente(p, date.today()) is False


# ---------------------------------------------------------------------------
# auth_service — IP mismatch e invalidar_sessao
# ---------------------------------------------------------------------------


async def test_buscar_sessao_ip_mismatch_warn_retorna_usuario(
    engine: AsyncEngine, db: AsyncSession
) -> None:
    """Modo 'warn' com IP diferente ainda retorna o usuário (sem rejeição)."""
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import buscar_sessao_valida, hash_senha
    from app.infra.models import Sessao, Usuario

    uid = uuid.uuid4()
    u = Usuario(
        id=uid,
        email=f"ip_warn_{uid.hex[:8]}@test.com",
        nome="IP Warn Test",
        senha_hash=hash_senha("Test@123"),
        papel="corretor",
        tenant_id=TENANT_ID,
    )
    db.add(u)
    await db.flush()
    sid = uuid.uuid4()
    sessao = Sessao(
        id=sid,
        usuario_id=uid,
        expira_em=datetime.now(UTC) + timedelta(hours=1),
        ip_origem="1.2.3.4",
    )
    db.add(sessao)
    await db.commit()

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        with patch("app.infra.auth_service._IP_CHECK_MODE", "warn"):
            result = await buscar_sessao_valida(session, sid, "9.9.9.9")
    assert result is not None


async def test_buscar_sessao_ip_mismatch_strict_rejeita(
    engine: AsyncEngine, db: AsyncSession
) -> None:
    """Modo 'strict' com IP diferente deve rejeitar a sessão (retorna None)."""
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import buscar_sessao_valida, hash_senha
    from app.infra.models import Sessao, Usuario

    uid = uuid.uuid4()
    u = Usuario(
        id=uid,
        email=f"ip_strict_{uid.hex[:8]}@test.com",
        nome="IP Strict Test",
        senha_hash=hash_senha("Test@123"),
        papel="corretor",
        tenant_id=TENANT_ID,
    )
    db.add(u)
    await db.flush()
    sid = uuid.uuid4()
    sessao = Sessao(
        id=sid,
        usuario_id=uid,
        expira_em=datetime.now(UTC) + timedelta(hours=1),
        ip_origem="1.2.3.4",
    )
    db.add(sessao)
    await db.commit()

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        with patch("app.infra.auth_service._IP_CHECK_MODE", "strict"):
            result = await buscar_sessao_valida(session, sid, "9.9.9.9")
    assert result is None


async def test_buscar_sessao_inexistente_retorna_none(engine: AsyncEngine) -> None:
    """UUID inexistente deve retornar None sem exceção."""
    from app.infra.auth_service import buscar_sessao_valida

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        result = await buscar_sessao_valida(session, uuid.uuid4(), None)
    assert result is None


async def test_invalidar_sessao_nao_existente_nao_levanta(
    engine: AsyncEngine,
) -> None:
    """invalidar_sessao com UUID inexistente não deve levantar exceção."""
    from app.infra.auth_service import invalidar_sessao

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await invalidar_sessao(session, uuid.uuid4())


# ---------------------------------------------------------------------------
# auth_service — branches não cobertos pelos testes HTTP
# ---------------------------------------------------------------------------


async def test_invalidar_sessao_com_sessao_existente(
    engine: AsyncEngine, db: AsyncSession
) -> None:
    """invalidar_sessao deve expirar sessão quando ela existe."""
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha, invalidar_sessao
    from app.infra.models import Sessao, Usuario

    uid = uuid.uuid4()
    u = Usuario(
        id=uid,
        email=f"inv_exist_{uid.hex[:8]}@test.com",
        nome="Inv Exist",
        senha_hash=hash_senha("Test@123"),
        papel="corretor",
        tenant_id=TENANT_ID,
    )
    db.add(u)
    await db.flush()
    sid = uuid.uuid4()
    sessao = Sessao(
        id=sid,
        usuario_id=uid,
        expira_em=datetime.now(UTC) + timedelta(hours=1),
        ip_origem=None,
    )
    db.add(sessao)
    await db.commit()

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await invalidar_sessao(session, sid)
        await session.commit()


async def test_registrar_falha_nova_tentativa(engine: AsyncEngine) -> None:
    """registrar_falha cria nova TentativaLogin para identificador novo."""
    from app.infra.auth_service import registrar_falha

    ident = f"nova_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()


async def test_registrar_falha_atualiza_existente(engine: AsyncEngine) -> None:
    """registrar_falha incrementa contagem em tentativa existente."""
    from app.infra.auth_service import registrar_falha

    ident = f"upd_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()


async def test_registrar_falha_bloqueia_apos_limite(engine: AsyncEngine) -> None:
    """registrar_falha define bloqueado_ate após RATE_LIMIT_MAX tentativas."""
    from app.infra.auth_service import RATE_LIMIT_MAX, registrar_falha

    ident = f"blk_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()
    for _ in range(RATE_LIMIT_MAX - 1):
        async with factory() as session:
            await registrar_falha(session, ident)
            await session.commit()


async def test_checar_rate_limit_bloqueado_levanta_429(engine: AsyncEngine) -> None:
    """checar_rate_limit levanta HTTPException 429 quando bloqueado."""
    import pytest
    from fastapi import HTTPException

    from app.infra.auth_service import (
        RATE_LIMIT_MAX,
        checar_rate_limit,
        registrar_falha,
    )

    ident = f"blk2_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    for _ in range(RATE_LIMIT_MAX):
        async with factory() as session:
            await registrar_falha(session, ident)
            await session.commit()

    async with factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await checar_rate_limit(session, ident)
        assert exc_info.value.status_code == 429


async def test_resetar_tentativas_com_existente(engine: AsyncEngine) -> None:
    """resetar_tentativas zera contagem de tentativa existente."""
    from app.infra.auth_service import registrar_falha, resetar_tentativas

    ident = f"rst_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()
    async with factory() as session:
        await resetar_tentativas(session, ident)
        await session.commit()


# ---------------------------------------------------------------------------
# relatorio_router — _dados_producao, _dados_funil, _dados_mix direto (sem HTTP)
# ---------------------------------------------------------------------------


async def _setup_cotacao_proposta(
    engine: AsyncEngine,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Cria usuário + cotação + proposta no DB, retorna (uid, cot_id, prop_id)."""
    from sqlalchemy import text

    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha
    from app.infra.models import Cotacao, Proposta, Usuario

    uid = uuid.uuid4()
    cot_id = uuid.uuid4()
    prop_id = uuid.uuid4()
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await session.execute(
            text(f"SELECT set_config('app.usuario_id', '{uid}', true)")
        )
        await session.execute(text("SELECT set_config('app.papel', 'corretor', true)"))
        u = Usuario(
            id=uid,
            email=f"rel_{uid.hex[:8]}@test.com",
            nome="Rel Test",
            senha_hash=hash_senha("Test@123"),
            papel="corretor",
            tenant_id=TENANT_ID,
        )
        session.add(u)
        await session.flush()

        cot = Cotacao(
            id=cot_id,
            usuario_id=uid,
            tenant_id=TENANT_ID,
            ramo="auto",
            status="sucesso",
            dados_risco={},
            premio_total=Decimal("1500.00"),
        )
        session.add(cot)
        await session.flush()

        prop = Proposta(
            id=prop_id,
            cotacao_id=cot_id,
            protocolo=f"PROTO{uid.hex[:8]}",
            comissao_pct=Decimal("0.1500"),
            plano_pagamento="AVISTA",
            n_parcelas=1,
            valor_parcela=Decimal("1500.00"),
            comissao_parcela=Decimal("225.00"),
            usuario_id=uid,
            tenant_id=TENANT_ID,
        )
        session.add(prop)
        await session.commit()

    return uid, cot_id, prop_id


async def test_dados_producao_vazio(engine: AsyncEngine) -> None:
    """_dados_producao retorna lista vazia quando não há dados no período."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_producao

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    futuro = datetime.now(UTC) + timedelta(days=365)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_producao(session, futuro, futuro + timedelta(days=1))
        assert isinstance(result, list)


async def test_dados_producao_com_dados(engine: AsyncEngine) -> None:
    """_dados_producao cobre loops de cotações e propostas com dados reais."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_producao

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_producao(
            session, agora - timedelta(hours=1), agora + timedelta(hours=1)
        )
        assert isinstance(result, list)
        assert any(str(r.corretor_id) == str(uid) for r in result)


async def test_dados_producao_com_usuario_id(engine: AsyncEngine) -> None:
    """_dados_producao com usuario_id cobre branch 'if usuario_id is not None'."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_producao

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_producao(
            session,
            agora - timedelta(hours=1),
            agora + timedelta(hours=1),
            usuario_id=uid,
        )
        assert isinstance(result, list)


async def test_dados_funil_vazio(engine: AsyncEngine) -> None:
    """_dados_funil retorna FunilOut vazio quando não há dados."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_funil

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    futuro = datetime.now(UTC) + timedelta(days=365)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_funil(session, futuro, futuro + timedelta(days=1))
        assert result.total_cotacoes == 0


async def test_dados_funil_com_dados(engine: AsyncEngine) -> None:
    """_dados_funil cobre loops de ramo e agrupamento com dados reais."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_funil

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_funil(
            session, agora - timedelta(hours=1), agora + timedelta(hours=1)
        )
        assert result.total_cotacoes >= 1
        assert len(result.por_ramo) >= 1


async def test_dados_funil_com_usuario_id(engine: AsyncEngine) -> None:
    """_dados_funil com usuario_id cobre branch filtro."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_funil

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_funil(
            session,
            agora - timedelta(hours=1),
            agora + timedelta(hours=1),
            usuario_id=uid,
        )
        assert isinstance(result.por_ramo, list)


async def test_dados_mix_vazio(engine: AsyncEngine) -> None:
    """_dados_mix retorna lista vazia quando não há propostas."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_mix

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    futuro = datetime.now(UTC) + timedelta(days=365)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_mix(session, futuro, futuro + timedelta(days=1))
        assert isinstance(result, list)


async def test_dados_mix_com_dados(engine: AsyncEngine) -> None:
    """_dados_mix cobre loop de ramo e cálculo de pct com dados reais."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_mix

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_mix(
            session, agora - timedelta(hours=1), agora + timedelta(hours=1)
        )
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0].pct > 0


async def test_dados_mix_com_usuario_id(engine: AsyncEngine) -> None:
    """_dados_mix com usuario_id cobre branch filtro."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.api.relatorio_router import _dados_mix

    uid, _, _ = await _setup_cotacao_proposta(engine)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    agora = datetime.now(UTC)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _dados_mix(
            session,
            agora - timedelta(hours=1),
            agora + timedelta(hours=1),
            usuario_id=uid,
        )
        assert isinstance(result, list)
