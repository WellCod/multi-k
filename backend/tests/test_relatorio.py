"""Testes dos endpoints de relatório — produção, funil, mix e exports."""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapters.fake.adapter import FakeSeguradora
from app.api.proposta_router import _adapter_dep
from app.domain.auth import Papel
from app.infra.models import CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {
        "cep_pernoite": "13010001",
        "codigo_fipe": "001004-9",
        "finalidade": "pessoal",
    },
}
_TRANSMITIR = {
    "plano_pagamento": "AVISTA",
    "n_parcelas": 1,
    "comissao_pct": "0.1500",
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    app.dependency_overrides[_adapter_dep] = lambda: FakeSeguradora(0, 0)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
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
        from sqlalchemy import select

        result = await db.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        jobs = [(j.id, j.cotacao_id) for j in result.scalars().all()]
    for job_id, cot_id in jobs:
        await processar_job(job_id, cot_id, factory)


async def _criar_proposta(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine, email: str
) -> None:
    await _login(client, db, email)
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    cotacao_id = uuid.UUID(r.json()["id"])
    await _processar_jobs(cotacao_id, engine)
    await client.post(f"/cotacoes/{cotacao_id}/transmitir", json=_TRANSMITIR)


# ---------------------------------------------------------------------------
# Funil e mix — acessíveis ao corretor
# ---------------------------------------------------------------------------


async def test_funil_corretor_retorna_estrutura(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_rel_funil@test.com")
    r = await client.get("/relatorios/funil")
    assert r.status_code == 200
    body = r.json()
    assert "total_cotacoes" in body
    assert "taxa_conversao_geral" in body
    assert isinstance(body["por_ramo"], list)


async def test_mix_corretor_retorna_lista(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_rel_mix@test.com")
    r = await client.get("/relatorios/mix")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_funil_sem_auth_retorna_401(client: AsyncClient) -> None:
    r = await client.get("/relatorios/funil")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Produção — admin apenas
# ---------------------------------------------------------------------------


async def test_producao_corretor_retorna_403(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_rel_prod403@test.com", Papel.CORRETOR)
    r = await client.get("/relatorios/producao")
    assert r.status_code == 403


async def test_producao_admin_retorna_lista(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "adm_rel_prod@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/producao")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Export CSV / XLSX — admin apenas
# ---------------------------------------------------------------------------


async def test_export_csv_admin(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "adm_rel_csv@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/csv", params={"tipo": "funil"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


async def test_export_xlsx_admin(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "adm_rel_xlsx@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/xlsx", params={"tipo": "producao"})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]


async def test_export_csv_corretor_retorna_403(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "cor_rel_csv403@test.com", Papel.CORRETOR)
    r = await client.get("/relatorios/export/csv", params={"tipo": "mix"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Funil reflete dados reais após proposta
# ---------------------------------------------------------------------------


async def test_funil_conta_proposta(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_proposta(client, db, engine, "cor_rel_funil2@test.com")
    r = await client.get("/relatorios/funil")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cotacoes"] >= 1
    assert body["total_com_proposta"] >= 1
