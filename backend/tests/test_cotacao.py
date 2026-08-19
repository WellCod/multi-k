"""Testes do endpoint de cotação."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.adapters.fake.adapter import FakeSeguradora
from app.api.cotacao_router import get_adapter
from app.domain.auth import Papel
from app.main import app
from tests.conftest import criar_usuario

_RISCO_AUTO = {
    "ramo": "auto",
    "dados": {"cep_pernoite": "13010001"},
}
_RISCO_AUTO_ERRO = {
    "ramo": "auto",
    "dados": {"cep_pernoite": "13010099"},
}
_RISCO_AUTO_RESTRICAO = {
    "ramo": "auto",
    "dados": {"cep_pernoite": "13010088"},
}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def zero_latency():
    """Remove latência do adapter durante testes."""
    app.dependency_overrides[get_adapter] = lambda: FakeSeguradora(
        latencia_min=0, latencia_max=0
    )
    yield
    app.dependency_overrides.pop(get_adapter, None)


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> AsyncClient:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200
    return client


async def test_cotacao_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_cot@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 200
    body = r.json()
    assert body["sucesso"] is True
    assert body["cotacao_id"] is not None
    assert body["premio_total"] is not None
    assert body["restricoes"] == []
    assert body["necessita_vistoria"] is False


async def test_cotacao_restricao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_res@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_RESTRICAO)
    assert r.status_code == 200
    body = r.json()
    assert body["sucesso"] is True
    assert body["necessita_vistoria"] is True
    assert len(body["restricoes"]) > 0


async def test_cotacao_erro(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "corretor_err@test.com")
    r = await client.post("/cotacoes", json=_RISCO_AUTO_ERRO)
    assert r.status_code == 200
    body = r.json()
    assert body["sucesso"] is False
    assert body["cotacao_id"] is None
    assert body["premio_total"] is None


async def test_cotacao_sem_auth(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.post("/cotacoes", json=_RISCO_AUTO)
    assert r.status_code == 401


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
