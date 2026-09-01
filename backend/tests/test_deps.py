"""Testes para api/deps.py — autenticação, admin check, sessão inválida."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

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


async def test_sem_cookie_retorna_401(client: AsyncClient, engine: AsyncEngine) -> None:
    r = await client.get("/clientes")
    assert r.status_code == 401


async def test_cookie_sid_invalido_retorna_401(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    client.cookies.set("sid", "nao-e-uuid")
    r = await client.get("/clientes")
    assert r.status_code == 401


async def test_corretor_acessa_rota_restrita_a_admin_retorna_403(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await criar_usuario(db, "deps_cor@test.com", Papel.CORRETOR)
    await db.commit()
    await client.post(
        "/auth/login", json={"email": "deps_cor@test.com", "senha": "Senha@123"}
    )
    r = await client.get("/home/admin")
    assert r.status_code == 403


async def test_admin_acessa_rota_admin(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await criar_usuario(db, "deps_adm@test.com", Papel.ADMIN)
    await db.commit()
    await client.post(
        "/auth/login", json={"email": "deps_adm@test.com", "senha": "Senha@123"}
    )
    r = await client.get("/home/admin")
    assert r.status_code == 200


async def test_corretor_acessa_rota_normal(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await criar_usuario(db, "deps_cor2@test.com", Papel.CORRETOR)
    await db.commit()
    await client.post(
        "/auth/login", json={"email": "deps_cor2@test.com", "senha": "Senha@123"}
    )
    r = await client.get("/clientes")
    assert r.status_code == 200
