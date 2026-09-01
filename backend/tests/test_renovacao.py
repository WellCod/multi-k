"""Testes para api/renovacao_router.py."""

import uuid as _uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.auth import Papel
from app.infra.models import Cotacao, Proposta
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> "str":
    u = await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return str(u.id)


async def _criar_proposta_vencendo(
    db: AsyncSession, usuario_id: str, dias_para_vencer: int
) -> None:
    """Cria cotação + proposta que vencerá em `dias_para_vencer` dias."""
    uid = _uuid.UUID(usuario_id)
    cotacao = Cotacao(
        id=_uuid.uuid4(),
        usuario_id=uid,
        ramo="auto",
        status="sucesso",
        dados_risco={},
        premio_total=Decimal("1200.00"),
    )
    db.add(cotacao)
    await db.flush()

    inicio = date.today() + timedelta(days=dias_para_vencer) - timedelta(days=365)
    proposta = Proposta(
        id=_uuid.uuid4(),
        cotacao_id=cotacao.id,
        usuario_id=uid,
        protocolo=f"P-{dias_para_vencer:03d}",
        plano_pagamento="mensal",
        n_parcelas=12,
        valor_parcela=Decimal("100.00"),
        comissao_parcela=Decimal("10.00"),
        comissao_pct=Decimal("0.1000"),
        inicio_vigencia=inicio,
    )
    db.add(proposta)
    await db.commit()


async def test_sem_auth_retorna_401(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/renovacoes")
    assert r.status_code == 401


async def test_lista_vazia_sem_propostas(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "ren_vazia@test.com")
    r = await client.get("/renovacoes")
    assert r.status_code == 200
    assert r.json() == []


async def test_retorna_proposta_dentro_do_prazo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    usuario_id = await _login(client, db, "ren_prazo@test.com")
    await _criar_proposta_vencendo(db, usuario_id, dias_para_vencer=20)

    r = await client.get("/renovacoes?dias=30")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert items[0]["janela"] == "D30"


async def test_nao_retorna_proposta_fora_do_prazo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    usuario_id = await _login(client, db, "ren_fora@test.com")
    await _criar_proposta_vencendo(db, usuario_id, dias_para_vencer=90)

    r = await client.get("/renovacoes?dias=60")
    assert r.status_code == 200
    assert r.json() == []


async def test_janela_d45(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    usuario_id = await _login(client, db, "ren_d45@test.com")
    await _criar_proposta_vencendo(db, usuario_id, dias_para_vencer=40)

    r = await client.get("/renovacoes?dias=60")
    assert r.status_code == 200
    items = r.json()
    assert any(i["janela"] == "D45" for i in items)
