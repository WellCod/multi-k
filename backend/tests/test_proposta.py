"""Testes de transmissão de proposta e endpoints relacionados."""

import uuid
from datetime import date

import pytest
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
from tests.conftest import criar_usuario

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


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    # Substitui o adapter por FakeSeguradora sem latência nos testes
    app.dependency_overrides[_adapter_dep] = lambda: FakeSeguradora(0, 0)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> AsyncClient:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return client


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


async def _criar_cotacao_processada(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine, email: str
) -> uuid.UUID:
    await _login(client, db, email)
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])
    await _processar_jobs(cotacao_id, engine)
    return cotacao_id


async def test_transmitir_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_tx@test.com"
    )

    r = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["protocolo"].startswith("FAKE-")
    assert body["cotacao_id"] == str(cotacao_id)
    assert body["n_parcelas"] == 1
    assert float(body["valor_parcela"]) > 0
    assert float(body["comissao_parcela"]) > 0


async def test_transmitir_cotacao_aguardando_falha(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_txaw@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    cotacao_id = r.json()["id"]
    # Cotação ainda "aguardando" — não pode transmitir
    r2 = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r2.status_code == 422


async def test_transmitir_cotacao_outro_usuario(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_owner@test.com"
    )
    # Loga como outro corretor
    await criar_usuario(db, "corretor_intruso@test.com", Papel.CORRETOR)
    await db.commit()
    r = await client.post(
        "/auth/login",
        json={"email": "corretor_intruso@test.com", "senha": "Senha@123"},
    )
    assert r.status_code == 200
    r2 = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY)
    assert r2.status_code == 404


async def test_obter_proposta(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_gp@test.com"
    )
    r_tx = await client.post(
        f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR_BODY
    )
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.get(f"/propostas/{proposta_id}")
    assert r.status_code == 200
    assert r.json()["protocolo"] == r_tx.json()["protocolo"]


async def test_parcelas(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_parc@test.com"
    )
    body_3x = {**_TRANSMITIR_BODY, "n_parcelas": 3, "plano_pagamento": "3X"}
    r_tx = await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=body_3x)
    assert r_tx.status_code == 201
    proposta_id = r_tx.json()["id"]

    r = await client.get(f"/propostas/{proposta_id}/parcelas")
    assert r.status_code == 200
    parcelas = r.json()
    assert len(parcelas) == 3
    assert parcelas[0]["numero"] == 1
    assert parcelas[1]["numero"] == 2
    assert parcelas[2]["numero"] == 3
    # Primeira parcela no dia de inicio_vigencia
    assert parcelas[0]["vencimento"] == str(date.today())


async def test_comparativo_json(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_comp@test.com"
    )
    r = await client.get(f"/cotacoes/{cotacao_id}/comparativo")
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) >= 1
    assert "premio_total" in itens[0]
    assert "cia" in itens[0]


async def test_comparativo_pdf(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    cotacao_id = await _criar_cotacao_processada(
        client, db, engine, "corretor_pdf@test.com"
    )
    r = await client.get(f"/cotacoes/{cotacao_id}/comparativo/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 100


async def test_renovacoes_vazio(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_ren@test.com")
    r = await client.get("/renovacoes")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize("sem_auth", [True])
async def test_transmitir_sem_auth(
    client: AsyncClient, engine: AsyncEngine, sem_auth: bool
) -> None:
    r = await client.post(f"/cotacoes/{uuid.uuid4()}/transmitir", json=_TRANSMITIR_BODY)
    assert r.status_code == 401
