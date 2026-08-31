"""Testes do endpoint de cotação."""

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.auth import Papel
from app.infra.models import CotacaoJob
from app.infra.worker import processar_job
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_DADOS_AUTO_BASE = {"codigo_fipe": "001004-9", "finalidade": "pessoal"}
_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010001"},
}
_RISCO_AUTO_ERRO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010099"},
}
_RISCO_AUTO_RESTRICAO = {
    "ramo": "auto",
    "dados": {**_DADOS_AUTO_BASE, "cep_pernoite": "13010088"},
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> AsyncClient:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return client


async def _processar_jobs_da_cotacao(
    cotacao_id: uuid.UUID,
    engine: AsyncEngine,
) -> None:
    """Processa synchronously os jobs pendentes para uma cotação nos testes."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as db:
        result = await db.execute(
            select(CotacaoJob).where(CotacaoJob.cotacao_id == cotacao_id)
        )
        jobs = result.scalars().all()
        job_data = [(j.id, j.cotacao_id) for j in jobs]

    for job_id, cot_id in job_data:
        await processar_job(job_id, cot_id, factory)


async def test_cotacao_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_cot@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 202
    body = r.json()
    cotacao_id = uuid.UUID(body["id"])
    assert body["status"] == "aguardando"

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "sucesso"
    assert body2["premio_total"] is not None
    assert body2["restricoes"] == []
    assert body2["necessita_vistoria"] is False


async def test_cotacao_restricao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_res@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_RESTRICAO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    body = r2.json()
    assert body["status"] == "restricao"
    assert body["necessita_vistoria"] is True
    assert len(body["restricoes"]) > 0


async def test_cotacao_erro(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_err@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_ERRO)
    assert r.status_code == 202
    cotacao_id = uuid.UUID(r.json()["id"])

    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    body = r2.json()
    assert body["status"] == "erro"
    assert body["premio_total"] is None


async def test_cotacao_sem_auth(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 401


async def test_recotar(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_rec@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    cotacao_id = uuid.UUID(r.json()["id"])
    await _processar_jobs_da_cotacao(cotacao_id, engine)

    r2 = await client.post(f"/cotacoes/{cotacao_id}/recotar")
    assert r2.status_code == 202
    nova_id = uuid.UUID(r2.json()["id"])
    assert nova_id != cotacao_id

    await _processar_jobs_da_cotacao(nova_id, engine)

    r3 = await client.get(f"/cotacoes/{nova_id}")
    body = r3.json()
    assert body["status"] == "sucesso"
    assert body["versao_anterior_id"] == str(cotacao_id)


async def test_listar_cotacoes(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_list@test.com")
    await client.post("/cotacoes", json=_RISCO_AUTO)
    r = await client.get("/cotacoes")
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_dominios_retorna_lista(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_dom@test.com")
    r = await client.get("/dominios")
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    assert all("tipo" in i and "codigo" in i and "descricao" in i for i in items)


async def test_dominios_filtro_tipo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_domf@test.com")
    r = await client.get("/dominios", params={"tipo": "estado_civil"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    assert all(i["tipo"] == "estado_civil" for i in items)


async def test_dominios_sem_auth(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/dominios")
    assert r.status_code == 401


async def test_cotacao_preserva_cliente_id(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Cotação criada com cliente_id expõe esse vínculo no GET."""
    await _login(client, db, "corretor_clid@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Teste Vínculo", "cpf": "66666666666"}
    )
    assert r_cli.status_code == 201
    cliente_id = r_cli.json()["id"]

    r = await client.post(
        "/cotacoes",
        json={**_RISCO_AUTO, "cliente_id": cliente_id},
    )
    assert r.status_code == 202
    cotacao_id = r.json()["id"]

    r2 = await client.get(f"/cotacoes/{cotacao_id}")
    assert r2.json()["cliente_id"] == cliente_id


async def test_nova_cotacao_preserva_cliente_e_versao_anterior(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """POST /cotacoes com versao_anterior_id e cliente_id preserva ambos.

    Simula o fluxo do frontend após ?recotar=: o novo objeto tem vínculo ao
    cliente e à cotação original.
    """
    await _login(client, db, "corretor_recotar_cli@test.com")
    r_cli = await client.post(
        "/clientes", json={"nome": "Recotar Cliente", "cpf": "77777777777"}
    )
    cliente_id = r_cli.json()["id"]

    r_orig = await client.post(
        "/cotacoes", json={**_RISCO_AUTO, "cliente_id": cliente_id}
    )
    orig_id = r_orig.json()["id"]

    r_nova = await client.post(
        "/cotacoes",
        json={**_RISCO_AUTO, "cliente_id": cliente_id, "versao_anterior_id": orig_id},
    )
    assert r_nova.status_code == 202
    nova_id = r_nova.json()["id"]

    r3 = await client.get(f"/cotacoes/{nova_id}")
    body = r3.json()
    assert body["cliente_id"] == cliente_id
    assert body["versao_anterior_id"] == orig_id
