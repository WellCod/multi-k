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


# ---------------------------------------------------------------------------
# Testes com dados reais — cobre loops de agregação
# ---------------------------------------------------------------------------


async def test_producao_admin_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Produção com dados reais deve retornar linhas por corretor."""
    await _criar_proposta(client, db, engine, "cor_prod_dados@test.com")
    await _login(client, db, "adm_prod_dados@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/producao")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    item = body[0]
    assert "corretor_nome" in item
    assert "cotacoes" in item
    assert "taxa_conversao" in item
    assert "premio_total" in item


async def test_mix_corretor_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Mix com dados reais deve retornar lista com pct calculado."""
    await _criar_proposta(client, db, engine, "cor_mix_dados@test.com")
    r = await client.get("/relatorios/mix")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert "pct" in body[0]
    assert "count" in body[0]


async def test_csv_export_producao_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """CSV de produção com dados deve incluir header e ao menos uma linha de dados."""
    await _criar_proposta(client, db, engine, "cor_csv_prod@test.com")
    await _login(client, db, "adm_csv_prod@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/csv", params={"tipo": "producao"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert "corretor_id" in lines[0]
    assert len(lines) >= 2  # header + ao menos 1 linha de dados


async def test_csv_export_funil_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """CSV de funil com dados deve incluir linhas de por_ramo."""
    await _criar_proposta(client, db, engine, "cor_csv_funil@test.com")
    await _login(client, db, "adm_csv_funil@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/csv", params={"tipo": "funil"})
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert "ramo" in lines[0]
    assert len(lines) >= 2


async def test_xlsx_export_producao_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """XLSX de produção com dados deve retornar bytes de workbook válido."""
    await _criar_proposta(client, db, engine, "cor_xlsx_prod@test.com")
    await _login(client, db, "adm_xlsx_prod@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/xlsx", params={"tipo": "producao"})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    assert len(r.content) > 100  # bytes reais, não vazio


async def test_xlsx_export_funil_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """XLSX de funil com dados deve retornar workbook válido."""
    await _criar_proposta(client, db, engine, "cor_xlsx_funil@test.com")
    await _login(client, db, "adm_xlsx_funil@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/xlsx", params={"tipo": "funil"})
    assert r.status_code == 200
    assert len(r.content) > 100


async def test_xlsx_export_mix_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """XLSX de mix com dados deve retornar workbook válido."""
    await _criar_proposta(client, db, engine, "cor_xlsx_mix@test.com")
    await _login(client, db, "adm_xlsx_mix@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/xlsx", params={"tipo": "mix"})
    assert r.status_code == 200
    assert len(r.content) > 100


async def test_csv_export_mix_com_dados(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """CSV de mix com dados deve incluir header e linhas de ramo."""
    await _criar_proposta(client, db, engine, "cor_csv_mix@test.com")
    await _login(client, db, "adm_csv_mix@test.com", Papel.ADMIN)
    r = await client.get("/relatorios/export/csv", params={"tipo": "mix"})
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert "ramo" in lines[0]
    assert len(lines) >= 2


async def test_funil_com_date_from(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Funil com date_from explícito deve respeitar o parâmetro."""
    from datetime import date, timedelta

    await _login(client, db, "cor_funil_dfrom@test.com")
    date_from = (date.today() - timedelta(days=7)).isoformat()
    r = await client.get("/relatorios/funil", params={"date_from": date_from})
    assert r.status_code == 200
    body = r.json()
    assert "total_cotacoes" in body


async def test_funil_com_date_to(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Funil com date_to explícito deve respeitar o parâmetro."""
    from datetime import date

    await _login(client, db, "cor_funil_dto@test.com")
    date_to = date.today().isoformat()
    r = await client.get("/relatorios/funil", params={"date_to": date_to})
    assert r.status_code == 200
    body = r.json()
    assert "taxa_conversao_geral" in body


async def test_mix_com_date_from_e_date_to(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Mix com date_from e date_to deve funcionar com intervalo explícito."""
    from datetime import date, timedelta

    await _login(client, db, "cor_mix_drange@test.com")
    date_from = (date.today() - timedelta(days=30)).isoformat()
    date_to = date.today().isoformat()
    r = await client.get(
        "/relatorios/mix",
        params={"date_from": date_from, "date_to": date_to},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)
