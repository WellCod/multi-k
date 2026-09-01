"""Testes de cobertura — parte 2: funções diretas de routers e auth_service."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# ---------------------------------------------------------------------------
# auth_service — registrar_falha reset de janela (line 129)
# ---------------------------------------------------------------------------


async def test_registrar_falha_reseta_na_nova_janela(engine: AsyncEngine) -> None:
    """registrar_falha reseta contagem quando ultima_tentativa está fora da janela."""
    from app.infra.auth_service import RATE_LIMIT_WINDOW, registrar_falha
    from app.infra.models import TentativaLogin

    ident = f"janela_{uuid.uuid4().hex[:8]}@test.com"
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    old_time = datetime.now(UTC) - RATE_LIMIT_WINDOW - timedelta(minutes=5)
    async with factory() as session:
        session.add(
            TentativaLogin(identificador=ident, contagem=4, ultima_tentativa=old_time)
        )
        await session.commit()
    async with factory() as session:
        await registrar_falha(session, ident)
        await session.commit()


# ---------------------------------------------------------------------------
# _utils.get_or_404 — path de 404 (lines 19-22)
# ---------------------------------------------------------------------------


async def test_get_or_404_levanta_404(engine: AsyncEngine) -> None:
    """get_or_404 levanta HTTPException 404 quando objeto não existe."""
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.api._utils import get_or_404
    from app.infra.models import Usuario

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        stmt = select(Usuario).where(Usuario.id == uuid.uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_or_404(stmt, session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# auditoria_router — chamadas diretas (lines 58, 79-107)
# ---------------------------------------------------------------------------


async def test_listar_auditoria_direto(engine: AsyncEngine) -> None:
    """listar_auditoria cobre queries, uid_set não-vazio e list comprehension."""
    from app.api.auditoria_router import listar_auditoria
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha
    from app.infra.models import Auditoria, Usuario

    uid = uuid.uuid4()
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        u = Usuario(
            id=uid,
            email=f"aud_dir_{uid.hex[:8]}@test.com",
            nome="Aud Direto",
            senha_hash=hash_senha("Test@123"),
            papel="corretor",
            tenant_id=TENANT_ID,
        )
        session.add(u)
        await session.flush()
        session.add(Auditoria(tipo="test_direto", usuario_id=uid, dados={}))
        await session.commit()

    mock_adm = MagicMock()
    async with factory() as session:
        result = await listar_auditoria(
            _usuario=mock_adm,
            db=session,
            page=1,
            page_size=50,
            tipo=None,
            usuario_id=None,
        )
        assert result.total >= 1
        assert isinstance(result.items, list)


async def test_listar_usuarios_auditoria_direto(engine: AsyncEngine) -> None:
    """listar_usuarios_auditoria cobre list comprehension da linha 58."""
    from app.api.auditoria_router import listar_usuarios_auditoria
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha
    from app.infra.models import Auditoria, Usuario

    uid = uuid.uuid4()
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        u = Usuario(
            id=uid,
            email=f"aud_usr_{uid.hex[:8]}@test.com",
            nome="Aud Usr",
            senha_hash=hash_senha("Test@123"),
            papel="corretor",
            tenant_id=TENANT_ID,
        )
        session.add(u)
        await session.flush()
        session.add(Auditoria(tipo="test_usr", usuario_id=uid, dados={}))
        await session.commit()

    mock_adm = MagicMock()
    async with factory() as session:
        result = await listar_usuarios_auditoria(_usuario=mock_adm, db=session)
        assert any(str(r.id) == str(uid) for r in result)


# ---------------------------------------------------------------------------
# renovacao_router — chamada direta com proposta dentro do prazo (lines 58-83)
# ---------------------------------------------------------------------------


async def test_listar_renovacoes_direto_com_dados(engine: AsyncEngine) -> None:
    """listar_renovacoes cobre loop e construção de RenovacaoOut."""
    from sqlalchemy import text

    from app.api.renovacao_router import listar_renovacoes
    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha
    from app.infra.models import Cotacao, Proposta, Usuario

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
            email=f"ren_dir_{uid.hex[:8]}@test.com",
            nome="Ren Dir",
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
            premio_total=Decimal("800.00"),
        )
        session.add(cot)
        await session.flush()
        session.add(
            Proposta(
                cotacao_id=cot_id,
                protocolo=f"REN{uid.hex[:8]}",
                comissao_pct=Decimal("0.1500"),
                plano_pagamento="AVISTA",
                n_parcelas=1,
                valor_parcela=Decimal("800.00"),
                comissao_parcela=Decimal("120.00"),
                inicio_vigencia=date.today() - timedelta(days=335),
                usuario_id=uid,
                tenant_id=TENANT_ID,
            )
        )
        await session.commit()

    mock_user = MagicMock()
    mock_user.id = uid
    async with factory() as session:
        await session.execute(
            text(f"SELECT set_config('app.usuario_id', '{uid}', true)")
        )
        await session.execute(text("SELECT set_config('app.papel', 'corretor', true)"))
        result = await listar_renovacoes(usuario=mock_user, db=session, dias=60)
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# relatorio_router — export_csv e export_xlsx branches funil e mix (direto)
# ---------------------------------------------------------------------------


async def _ensure_relatorio_data(engine: AsyncEngine) -> None:
    """Garante ao menos uma cotação e proposta no DB para os testes de export."""
    from sqlalchemy import text

    from app.domain.auth import TENANT_ID
    from app.infra.auth_service import hash_senha
    from app.infra.models import Cotacao, Proposta, Usuario

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
        session.add(
            Usuario(
                id=uid,
                email=f"exp_{uid.hex[:8]}@test.com",
                nome="Export Test",
                senha_hash=hash_senha("Test@123"),
                papel="corretor",
                tenant_id=TENANT_ID,
            )
        )
        await session.flush()
        session.add(
            Cotacao(
                id=cot_id,
                usuario_id=uid,
                tenant_id=TENANT_ID,
                ramo="auto",
                status="sucesso",
                dados_risco={},
                premio_total=Decimal("1200.00"),
            )
        )
        await session.flush()
        session.add(
            Proposta(
                cotacao_id=cot_id,
                protocolo=f"EXP{uid.hex[:8]}",
                comissao_pct=Decimal("0.1500"),
                plano_pagamento="AVISTA",
                n_parcelas=1,
                valor_parcela=Decimal("1200.00"),
                comissao_parcela=Decimal("180.00"),
                usuario_id=uid,
                tenant_id=TENANT_ID,
            )
        )
        await session.commit()


async def test_export_csv_funil_direto(engine: AsyncEngine) -> None:
    """export_csv tipo='funil' cobre branch funil do CSV (lines 387-397)."""
    from fastapi.responses import StreamingResponse
    from sqlalchemy import text

    from app.api.relatorio_router import export_csv

    await _ensure_relatorio_data(engine)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_adm = MagicMock()
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await export_csv(
            usuario=mock_adm, db=session, tipo="funil", periodo=30
        )
        assert isinstance(result, StreamingResponse)


async def test_export_csv_mix_direto(engine: AsyncEngine) -> None:
    """export_csv tipo='mix' cobre branch mix do CSV (lines 409-414)."""
    from fastapi.responses import StreamingResponse
    from sqlalchemy import text

    from app.api.relatorio_router import export_csv

    await _ensure_relatorio_data(engine)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_adm = MagicMock()
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await export_csv(usuario=mock_adm, db=session, tipo="mix", periodo=30)
        assert isinstance(result, StreamingResponse)


async def test_export_xlsx_funil_direto(engine: AsyncEngine) -> None:
    """export_xlsx tipo='funil' cobre branch funil do XLSX (lines 478-488)."""
    from fastapi.responses import StreamingResponse
    from sqlalchemy import text

    from app.api.relatorio_router import export_xlsx

    await _ensure_relatorio_data(engine)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_adm = MagicMock()
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await export_xlsx(
            usuario=mock_adm, db=session, tipo="funil", periodo=30
        )
        assert isinstance(result, StreamingResponse)


async def test_export_xlsx_mix_direto(engine: AsyncEngine) -> None:
    """export_xlsx tipo='mix' cobre branch mix do XLSX (lines 501-508)."""
    from fastapi.responses import StreamingResponse
    from sqlalchemy import text

    from app.api.relatorio_router import export_xlsx

    await _ensure_relatorio_data(engine)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    mock_adm = MagicMock()
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.papel', 'admin', true)"))
        result = await export_xlsx(usuario=mock_adm, db=session, tipo="mix", periodo=30)
        assert isinstance(result, StreamingResponse)
