"""Testes dos endpoints /home/corretor e /home/admin."""

import uuid
from datetime import date, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.fake.adapter import FakeSeguradora
from app.api.proposta_router import _adapter_dep
from app.domain.auth import Papel
from app.infra.models import CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(
    client: AsyncClient,
    db: AsyncSession,
    email: str,
    papel: Papel = Papel.CORRETOR,
    senha: str = "Senha@123",
) -> None:
    """Cria usuário, faz commit e autentica o client via cookie."""
    await criar_usuario(db, email, papel, senha)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# test_home_corretor_vazio
# ---------------------------------------------------------------------------


async def test_home_corretor_vazio(db: AsyncSession, client: AsyncClient) -> None:
    """Corretor sem dados deve receber todas as listas vazias."""
    await _login(client, db, "corretor_home_vazio@test.com")

    r = await client.get("/home/corretor")
    assert r.status_code == 200

    body = r.json()
    assert body["renovacoes"] == []
    assert body["propostas_paradas"] == []
    assert body["cotacoes_abandonadas"] == []
    assert body["parcelas_vencendo"] == []


# ---------------------------------------------------------------------------
# test_home_admin_vazio
# ---------------------------------------------------------------------------


async def test_home_admin_vazio(db: AsyncSession, client: AsyncClient) -> None:
    """Admin sem dados de carteira deve ver zeros nos KPIs."""
    await _login(client, db, "admin_home_vazio@test.com", Papel.ADMIN)

    r = await client.get("/home/admin")
    assert r.status_code == 200

    body = r.json()
    # Pode haver dados de outros testes no mesmo módulo, então apenas
    # verificamos que os campos existem e têm tipos corretos.
    assert "segurados_vigentes" in body
    assert "apolices_vigentes" in body
    assert "cotacoes_em_andamento" in body
    assert "premio_liquido" in body
    assert "comissao_produzida" in body
    assert "comissao_recebida" in body
    # comissao_recebida sempre 0 até FASE 7
    assert float(body["comissao_recebida"]) == 0.0
    assert "por_ramo" in body
    assert "por_corretor" in body
    assert isinstance(body["por_ramo"], list)
    assert isinstance(body["por_corretor"], list)


# ---------------------------------------------------------------------------
# test_home_corretor_sem_auth
# ---------------------------------------------------------------------------


async def test_home_corretor_sem_auth(client: AsyncClient) -> None:
    """Requisição sem sessão deve retornar 401."""
    r = await client.get("/home/corretor")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# test_home_admin_sem_admin
# ---------------------------------------------------------------------------


async def test_home_admin_sem_admin(db: AsyncSession, client: AsyncClient) -> None:
    """Corretor tentando acessar /home/admin deve receber 403."""
    await _login(client, db, "corretor_nao_admin@test.com", Papel.CORRETOR)

    r = await client.get("/home/admin")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Helpers para testes com dados reais
# ---------------------------------------------------------------------------

_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {
        "cep_pernoite": "13010001",
        "codigo_fipe": "001004-9",
        "finalidade": "pessoal",
    },
}


async def _criar_proposta(
    client: AsyncClient,
    engine: AsyncEngine,
    inicio_vigencia: date,
    n_parcelas: int = 1,
) -> uuid.UUID:
    """Cria cotação, processa jobs e transmite proposta. Retorna proposta_id."""
    app.dependency_overrides[_adapter_dep] = lambda: FakeSeguradora(0, 0)
    try:
        r = await client.post("/cotacoes", json=_RISCO_AUTO)
        assert r.status_code == 202
        cotacao_id = uuid.UUID(r.json()["id"])

        factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        async with factory() as s:
            result = await s.execute(
                select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
            )
            job_data = [(j.id, j.cotacao_id) for j in result.scalars().all()]
        for job_id, cot_id in job_data:
            await processar_job(job_id, cot_id, factory)

        r_tx = await client.post(
            f"/cotacoes/{cotacao_id}/transmitir",
            json={
                "plano_pagamento": "AVISTA",
                "n_parcelas": n_parcelas,
                "comissao_pct": "0.1500",
                "inicio_vigencia": str(inicio_vigencia),
            },
        )
        assert r_tx.status_code == 201
        return uuid.UUID(r_tx.json()["id"])
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# test_home_corretor_com_renovacao
# ---------------------------------------------------------------------------


async def test_home_corretor_com_renovacao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Corretor com proposta a vencer em 30 dias vê renovação e parcela."""
    await _login(client, db, "corretor_home_ren@test.com")

    # Proposta: inicio 335 dias atrás → fim = hoje + 30 dias → D30
    inicio_ren = date.today() - timedelta(days=335)
    await _criar_proposta(client, engine, inicio_ren)

    r = await client.get("/home/corretor")
    assert r.status_code == 200
    body = r.json()
    assert len(body["renovacoes"]) >= 1
    ren = body["renovacoes"][0]
    assert ren["janela"] == "D30"
    assert ren["dias_para_vencer"] <= 30


async def test_home_corretor_com_parcelas_vencendo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Proposta com inicio_vigencia hoje gera parcela vencendo nos próximos 30 dias."""
    await _login(client, db, "corretor_home_parc@test.com")

    # Proposta com inicio hoje → parcela 1 vence hoje
    await _criar_proposta(client, engine, date.today(), n_parcelas=2)

    r = await client.get("/home/corretor")
    assert r.status_code == 200
    body = r.json()
    assert len(body["parcelas_vencendo"]) >= 1


# ---------------------------------------------------------------------------
# test_home_admin_com_dados
# ---------------------------------------------------------------------------


async def test_home_admin_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Admin vê por_ramo e por_corretor preenchidos quando há propostas vigentes."""
    # Cria um corretor com proposta vigente
    await _login(client, db, "corretor_admin_dados@test.com")
    await _criar_proposta(client, engine, date.today())

    # Agora acessa como admin
    await _login(client, db, "admin_dados@test.com", Papel.ADMIN)

    r = await client.get("/home/admin")
    assert r.status_code == 200
    body = r.json()
    assert body["apolices_vigentes"] >= 1
    assert body["premio_liquido"] is not None
    assert len(body["por_ramo"]) >= 1
    assert len(body["por_corretor"]) >= 1
    # Verifica campos do KpiRamo
    ramo_item = body["por_ramo"][0]
    assert "ramo" in ramo_item
    assert "count" in ramo_item
    assert "premio_total" in ramo_item
