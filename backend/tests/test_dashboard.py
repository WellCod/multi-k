"""Testes do endpoint GET /dashboard."""

import uuid
from datetime import date

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
    app.dependency_overrides[_adapter_dep] = lambda: FakeSeguradora(0, 0)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)
        yield c
    app.dependency_overrides.clear()


async def _login(
    client: AsyncClient,
    db: AsyncSession,
    email: str,
    papel: Papel = Papel.CORRETOR,
) -> None:
    await criar_usuario(db, email, papel)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


async def _processar_jobs(cotacao_id: uuid.UUID, engine: AsyncEngine) -> None:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as db:
        result = await db.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        job_data = [(j.id, j.cotacao_id) for j in result.scalars().all()]
    for job_id, cot_id in job_data:
        await processar_job(job_id, cot_id, factory)


_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {
        "cep_pernoite": "13010001",
        "codigo_fipe": "001004-9",
        "finalidade": "pessoal",
    },
}

_TRANSMITIR_BODY = {
    "plano_pagamento": "AVISTA",
    "n_parcelas": 1,
    "comissao_pct": "0.1500",
    "inicio_vigencia": str(date.today()),
}


async def test_dashboard_sem_auth_retorna_401(client: AsyncClient) -> None:
    r = await client.get("/dashboard")
    assert r.status_code == 401


async def test_dashboard_corretor_retorna_estrutura(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, "dash_corretor@test.com")
    r = await client.get("/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {
        "total_cotacoes",
        "total_propostas",
        "taxa_conversao",
        "ticket_medio",
        "por_ramo",
        "ranking_cias",
    }
    assert isinstance(body["por_ramo"], list)
    assert isinstance(body["ranking_cias"], list)


async def test_dashboard_corretor_sem_cotacoes_taxa_zero(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, "dash_zero@test.com")
    r = await client.get("/dashboard?periodo=1")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cotacoes"] >= 0
    assert body["por_ramo"] == []
    assert body["ranking_cias"] == []


async def test_dashboard_admin_ve_ranking_cias(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "dash_admin@test.com", Papel.ADMIN)

    r_cot = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r_cot.status_code == 202
    cotacao_id = uuid.UUID(r_cot.json()["id"])
    await _processar_jobs(cotacao_id, engine)

    r = await client.get("/dashboard?periodo=365")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["ranking_cias"], list)
    assert len(body["ranking_cias"]) >= 1
    cia_item = body["ranking_cias"][0]
    assert "cia" in cia_item
    assert "cotacoes" in cia_item


async def test_dashboard_corretor_com_cotacao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "dash_cot@test.com")
    r_cot = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r_cot.status_code == 202
    cotacao_id = uuid.UUID(r_cot.json()["id"])
    await _processar_jobs(cotacao_id, engine)

    r = await client.get("/dashboard?periodo=30")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cotacoes"] >= 1
    assert len(body["por_ramo"]) >= 1
    assert body["por_ramo"][0]["ramo"] == "auto"


async def test_dashboard_com_proposta_calcula_taxa(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "dash_taxa@test.com")
    r_cot = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r_cot.status_code == 202
    cotacao_id = uuid.UUID(r_cot.json()["id"])
    await _processar_jobs(cotacao_id, engine)

    await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)

    r = await client.get("/dashboard?periodo=30")
    assert r.status_code == 200
    body = r.json()
    assert body["total_propostas"] >= 1
    assert body["taxa_conversao"] != "0.0000"
    assert body["ticket_medio"] != "0.00"


async def test_dashboard_periodo_invalido_retorna_422(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _login(client, db, "dash_per_inv@test.com")
    r = await client.get("/dashboard?periodo=0")
    assert r.status_code == 422
