"""Testes de autenticação: login, logout e rate limit."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


@pytest_asyncio.fixture(autouse=True)
async def reset_tentativas(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tentativas_login"))


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


async def test_login_usuario_inexistente(
    engine: AsyncEngine, client: AsyncClient
) -> None:
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
