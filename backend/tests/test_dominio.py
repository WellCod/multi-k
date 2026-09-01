"""Testes para api/dominio_router.py."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

import app.api.dominio_router as dominio_router
from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


async def _login(client: AsyncClient, db: AsyncSession, email: str) -> None:
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


async def test_sem_auth_retorna_401(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/dominios")
    assert r.status_code == 401


async def test_lista_dominios_autenticado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_list@test.com")
    r = await client.get("/dominios")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert len(items) > 0
    assert "tipo" in items[0]
    assert "codigo" in items[0]
    assert "descricao" in items[0]


async def test_filtro_por_tipo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_tipo@test.com")
    r = await client.get("/dominios?tipo=profissao")
    assert r.status_code == 200
    items = r.json()
    assert all(i["tipo"] == "profissao" for i in items)


async def test_cache_retorna_mesmo_resultado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    dominio_router._dominio_cache.clear()
    await _login(client, db, "dom_cache@test.com")
    r1 = await client.get("/dominios?tipo=estado_civil")
    r2 = await client.get("/dominios?tipo=estado_civil")
    assert r1.status_code == 200
    assert r1.json() == r2.json()
    assert ("estado_civil", None) in dominio_router._dominio_cache
