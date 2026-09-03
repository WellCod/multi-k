"""Testes de cobertura extras — dashboard e auth_router direto."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.auth import TENANT_ID
from app.infra.auth_service import hash_senha
from app.infra.models import Cotacao, CotacaoJob, Proposta, Usuario

# ---------------------------------------------------------------------------
# dashboard_router._calcular_dashboard — direto (lines 65-137, 155)
# ---------------------------------------------------------------------------


async def test_calcular_dashboard_corretor_vazio(engine: AsyncEngine) -> None:
    """_calcular_dashboard com usuario_id isolado e sem dados retorna zeros."""
    from app.api.dashboard_router import _calcular_dashboard

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    uid = uuid.uuid4()
    inicio = datetime.now(UTC) - timedelta(days=30)
    async with factory() as session:
        await session.execute(
            text(f"SELECT set_config('app.usuario_id', '{uid}', true)")
        )
        await session.execute(text("SELECT set_config('app.papel', 'corretor', true)"))
        result = await _calcular_dashboard(session, inicio, uid, is_admin=False)

    assert result.total_cotacoes == 0
    assert result.total_propostas == 0
    assert result.taxa_conversao == Decimal("0.0000")
    assert result.ticket_medio == Decimal("0.00")
    assert result.por_ramo == []
    assert result.ranking_cias == []


async def test_calcular_dashboard_admin_vazio(engine: AsyncEngine) -> None:
    """_calcular_dashboard admin sem dados retorna ranking_cias vazio."""
    from app.api.dashboard_router import _calcular_dashboard

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    inicio = datetime.now(UTC) - timedelta(days=30)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await _calcular_dashboard(session, inicio, None, is_admin=True)

    assert isinstance(result.ranking_cias, list)


async def test_calcular_dashboard_com_cotacao_e_proposta(engine: AsyncEngine) -> None:
    """_calcular_dashboard com dados cobre por_ramo, ticket_medio e taxa."""
    from app.api.dashboard_router import _calcular_dashboard

    uid = uuid.uuid4()
    cot_id = uuid.uuid4()
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
            email=f"dash3_{uid.hex[:8]}@test.com",
            nome="Dash Direto",
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
            premio_total=Decimal("2000.00"),
        )
        session.add(cot)
        await session.flush()
        session.add(
            Proposta(
                cotacao_id=cot_id,
                protocolo=f"DDP{uid.hex[:8]}",
                comissao_pct=Decimal("0.1500"),
                plano_pagamento="AVISTA",
                n_parcelas=1,
                valor_parcela=Decimal("2000.00"),
                comissao_parcela=Decimal("300.00"),
                usuario_id=uid,
                tenant_id=TENANT_ID,
            )
        )
        await session.commit()

    async with factory() as session:
        await session.execute(
            text(f"SELECT set_config('app.usuario_id', '{uid}', true)")
        )
        await session.execute(text("SELECT set_config('app.papel', 'corretor', true)"))
        inicio = datetime.now(UTC) - timedelta(days=30)
        result = await _calcular_dashboard(session, inicio, uid, is_admin=False)

    assert result.total_cotacoes >= 1
    assert result.total_propostas >= 1
    assert result.taxa_conversao != Decimal("0.0000")
    assert result.ticket_medio == Decimal("2000.00")
    assert len(result.por_ramo) >= 1
    assert result.por_ramo[0].ramo == "auto"


async def test_calcular_dashboard_admin_com_jobs(engine: AsyncEngine) -> None:
    """_calcular_dashboard admin cobre ranking_cias quando há CotacaoJobs."""
    from app.api.dashboard_router import _calcular_dashboard

    uid = uuid.uuid4()
    cot_id = uuid.uuid4()
    job_id = uuid.uuid4()
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        u = Usuario(
            id=uid,
            email=f"dashadm_{uid.hex[:8]}@test.com",
            nome="Dash Admin",
            senha_hash=hash_senha("Test@123"),
            papel="admin",
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
            premio_total=Decimal("1800.00"),
        )
        session.add(cot)
        await session.flush()
        _now = datetime.now(UTC)
        session.add(
            CotacaoJob(
                id=job_id,
                cotacao_id=cot_id,
                cia="fake",
                status="concluido",
                premio_total=Decimal("1800.00"),
                payload_resposta={},
                processado_em=_now,  # garante latencia_media_s (linhas 147-148)
            )
        )
        # Proposta com transmitida_em explícito — garante ids_com_prop (linhas 151-152)
        session.add(
            Proposta(
                cotacao_id=cot_id,
                protocolo=f"ADM{uid.hex[:8]}",
                comissao_pct=Decimal("0.1500"),
                plano_pagamento="AVISTA",
                n_parcelas=1,
                valor_parcela=Decimal("1800.00"),
                comissao_parcela=Decimal("270.00"),
                usuario_id=uid,
                tenant_id=TENANT_ID,
                transmitida_em=_now,
            )
        )
        await session.commit()

    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        inicio = datetime.now(UTC) - timedelta(days=30)
        result = await _calcular_dashboard(session, inicio, None, is_admin=True)

    assert isinstance(result.ranking_cias, list)
    assert len(result.ranking_cias) >= 1
    cia = result.ranking_cias[0]
    assert cia.cia == "fake"
    assert cia.propostas >= 1
    assert cia.latencia_media_s is not None  # cobre linhas 147-148


# ---------------------------------------------------------------------------
# auth_router.me e auth_router.refresh — chamada direta (lines 151, 181-206)
# ---------------------------------------------------------------------------


async def test_me_direto_retorna_dados_usuario(engine: AsyncEngine) -> None:
    """me() chamado diretamente cobre linha 151 (MeOutput)."""
    from app.api.auth_router import me

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.nome = "Corretor Teste"
    mock_user.papel = "corretor"
    mock_user.email = "direto@test.com"

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        result = await me(usuario=mock_user, db=session)

    assert result.email == "direto@test.com"
    assert result.papel == "corretor"


async def test_refresh_sessao_valida_direto(engine: AsyncEngine) -> None:
    """refresh() direto com sessão existente cobre linhas 186-206."""
    from app.api.auth_router import refresh
    from app.infra.auth_service import criar_sessao

    uid = uuid.uuid4()
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        u = Usuario(
            id=uid,
            email=f"ref_dir_{uid.hex[:8]}@test.com",
            nome="Ref Direto",
            senha_hash=hash_senha("Test@123"),
            papel="corretor",
            tenant_id=TENANT_ID,
        )
        session.add(u)
        await session.flush()
        sessao_id = await criar_sessao(session, uid, ip=None)
        await session.commit()

    mock_request = MagicMock()
    mock_request.cookies.get.return_value = str(sessao_id)
    mock_response = MagicMock()

    async with factory() as session:
        result = await refresh(request=mock_request, response=mock_response, db=session)
        await session.commit()

    assert result == {}
    assert mock_response.set_cookie.called


async def test_refresh_sessao_inexistente_direto(engine: AsyncEngine) -> None:
    """refresh() direto com sessão inválida cobre linhas 181-185 (HTTPException 401)."""
    import pytest
    from fastapi import HTTPException

    from app.api.auth_router import refresh

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_request = MagicMock()
    valid_uuid = str(uuid.uuid4())  # UUID válido mas sessão inexistente
    mock_request.cookies.get.return_value = valid_uuid
    mock_response = MagicMock()

    async with factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await refresh(request=mock_request, response=mock_response, db=session)

    assert exc_info.value.status_code == 401
    assert "expirada" in exc_info.value.detail


async def test_refresh_uuid_invalido_direto(engine: AsyncEngine) -> None:
    """refresh() direto com UUID inválido cobre linhas 174-175 (ValueError)."""
    import pytest
    from fastapi import HTTPException

    from app.api.auth_router import refresh

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_request = MagicMock()
    mock_request.cookies.get.return_value = "nao-e-uuid"
    mock_response = MagicMock()

    async with factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await refresh(request=mock_request, response=mock_response, db=session)

    assert exc_info.value.status_code == 401


async def test_refresh_sem_sid_direto(engine: AsyncEngine) -> None:
    """refresh() direto sem cookie cobre linhas 167-170."""
    import pytest
    from fastapi import HTTPException

    from app.api.auth_router import refresh

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_request = MagicMock()
    mock_request.cookies.get.return_value = None  # sem cookie
    mock_response = MagicMock()

    async with factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await refresh(request=mock_request, response=mock_response, db=session)

    assert exc_info.value.status_code == 401
    assert "autenticado" in exc_info.value.detail.lower()
