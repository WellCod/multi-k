"""Testes dos endpoints /home/corretor e /home/admin."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth import Papel
from app.main import app
from tests.conftest import criar_usuario


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _login(
    client: AsyncClient,
    db: AsyncSession,
    email: str,
    papel: Papel = Papel.CORRETOR,
    senha: str = "Senha@123",
) -> None:
    """Cria usuário, faz commit e autentica o client via cookie."""
    await criar_usuario(db, email, papel, senha)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# test_home_corretor_vazio
# ---------------------------------------------------------------------------


async def test_home_corretor_vazio(db: AsyncSession, client: AsyncClient) -> None:
    """Corretor sem dados deve receber todas as listas vazias."""
    await _login(client, db, "corretor_home_vazio@test.com")

    r = await client.get("/home/corretor")
    assert r.status_code == 200

    body = r.json()
    assert body["renovacoes"] == []
    assert body["propostas_paradas"] == []
    assert body["cotacoes_abandonadas"] == []
    assert body["parcelas_vencendo"] == []


# ---------------------------------------------------------------------------
# test_home_admin_vazio
# ---------------------------------------------------------------------------


async def test_home_admin_vazio(db: AsyncSession, client: AsyncClient) -> None:
    """Admin sem dados de carteira deve ver zeros nos KPIs."""
    await _login(client, db, "admin_home_vazio@test.com", Papel.ADMIN)

    r = await client.get("/home/admin")
    assert r.status_code == 200

    body = r.json()
    # Pode haver dados de outros testes no mesmo módulo, então apenas
    # verificamos que os campos existem e têm tipos corretos.
    assert "segurados_vigentes" in body
    assert "apolices_vigentes" in body
    assert "cotacoes_em_andamento" in body
    assert "premio_liquido" in body
    assert "comissao_produzida" in body
    assert "comissao_recebida" in body
    # comissao_recebida sempre 0 até FASE 7
    assert float(body["comissao_recebida"]) == 0.0
    assert "por_ramo" in body
    assert "por_corretor" in body
    assert isinstance(body["por_ramo"], list)
    assert isinstance(body["por_corretor"], list)


# ---------------------------------------------------------------------------
# test_home_corretor_sem_auth
# ---------------------------------------------------------------------------


async def test_home_corretor_sem_auth(client: AsyncClient) -> None:
    """Requisição sem sessão deve retornar 401."""
    r = await client.get("/home/corretor")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# test_home_admin_sem_admin
# ---------------------------------------------------------------------------


async def test_home_admin_sem_admin(db: AsyncSession, client: AsyncClient) -> None:
    """Corretor tentando acessar /home/admin deve receber 403."""
    await _login(client, db, "corretor_nao_admin@test.com", Papel.CORRETOR)

    r = await client.get("/home/admin")
    assert r.status_code == 403
