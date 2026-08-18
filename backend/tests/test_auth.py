"""Testes de autenticação: login, logout e rate limit."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.auth import Papel
from app.main import app
from tests.conftest import criar_usuario


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_login_sucesso(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await criar_usuario(db, "joao@test.com", Papel.CORRETOR)
    await db.commit()

    r = await client.post(
        "/auth/login", json={"email": "joao@test.com", "senha": "Senha@123"}
    )
    assert r.status_code == 200
    assert r.json()["papel"] == "corretor"
    assert "sid" in r.cookies


async def test_login_senha_errada(db: AsyncSession, client: AsyncClient) -> None:
    await criar_usuario(db, "maria@test.com", Papel.CORRETOR)
    await db.commit()

    r = await client.post(
        "/auth/login",
        json={"email": "maria@test.com", "senha": "senha_errada"},
    )
    assert r.status_code == 401


async def test_login_usuario_inexistente(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/login",
        json={"email": "naoexiste@test.com", "senha": "qualquer"},
    )
    assert r.status_code == 401


async def test_rate_limit_login(db: AsyncSession, client: AsyncClient) -> None:
    await criar_usuario(db, "limite@test.com", Papel.CORRETOR)
    await db.commit()

    for _ in range(5):
        await client.post(
            "/auth/login",
            json={"email": "limite@test.com", "senha": "errada"},
        )

    r = await client.post(
        "/auth/login",
        json={"email": "limite@test.com", "senha": "errada"},
    )
    assert r.status_code == 429


async def test_logout(db: AsyncSession, client: AsyncClient) -> None:
    await criar_usuario(db, "sair@test.com", Papel.CORRETOR)
    await db.commit()

    login_r = await client.post(
        "/auth/login", json={"email": "sair@test.com", "senha": "Senha@123"}
    )
    assert login_r.status_code == 200

    logout_r = await client.post("/auth/logout")
    assert logout_r.status_code == 200
    assert logout_r.cookies.get("sid") != login_r.cookies.get("sid")


async def test_rota_protegida_sem_cookie(client: AsyncClient) -> None:
    r = await client.get("/auth/me")
    assert r.status_code in (401, 404)
