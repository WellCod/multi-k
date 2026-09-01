"""Testes dos endpoints de auditoria — admin-only."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.auth import Papel
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


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


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


async def test_auditoria_sem_auth_retorna_401(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    r = await client.get("/auditoria")
    assert r.status_code == 401


async def test_auditoria_corretor_retorna_403(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "aud_cor_403@test.com")
    r = await client.get("/auditoria")
    assert r.status_code == 403


async def test_auditoria_admin_lista_estrutura(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Admin deve receber lista paginada com campos esperados."""
    await _login(client, db, "aud_adm_lista@test.com", Papel.ADMIN)
    # Gera ao menos um evento de auditoria
    await client.post("/cotacoes", json=_RISCO_AUTO)
    r = await client.get("/auditoria")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


async def test_auditoria_admin_filtro_tipo(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Filtro por tipo deve retornar apenas registros com aquele tipo."""
    await _login(client, db, "aud_adm_tipo@test.com", Papel.ADMIN)
    r = await client.get("/auditoria", params={"tipo": "login"})
    assert r.status_code == 200
    body = r.json()
    assert all(item["tipo"] == "login" for item in body["items"])


async def test_auditoria_admin_filtro_usuario_id(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Filtro por usuario_id deve aceitar UUID válido."""
    import uuid

    await _login(client, db, "aud_adm_uid@test.com", Papel.ADMIN)
    uid = str(uuid.uuid4())
    r = await client.get("/auditoria", params={"usuario_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == [] or all(
        str(item["usuario_id"]) == uid for item in body["items"]
    )


async def test_auditoria_admin_paginacao(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Paginação deve respeitar page_size."""
    await _login(client, db, "aud_adm_pag@test.com", Papel.ADMIN)
    r = await client.get("/auditoria", params={"page": 1, "page_size": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert len(body["items"]) <= 3


async def test_auditoria_usuarios_sem_auth(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    r = await client.get("/auditoria/usuarios")
    assert r.status_code == 401


async def test_auditoria_usuarios_corretor_403(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    await _login(client, db, "aud_usr_cor@test.com")
    r = await client.get("/auditoria/usuarios")
    assert r.status_code == 403


async def test_auditoria_usuarios_admin_retorna_lista(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Admin deve receber lista de usuários que aparecem no log."""
    await _login(client, db, "aud_usr_adm@test.com", Papel.ADMIN)
    r = await client.get("/auditoria/usuarios")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    for item in body:
        assert "id" in item
        assert "nome" in item


async def test_auditoria_admin_com_dados_nome_mapeado(
    db: AsyncSession, client: AsyncClient, engine: AsyncEngine
) -> None:
    """Registros de auditoria com usuario_id devem ter usuario_nome preenchido."""
    await _login(client, db, "aud_nome_adm@test.com", Papel.ADMIN)
    # Login gera auditoria com usuario_id → usuario_nome deve ser resolvido
    r = await client.get("/auditoria", params={"tipo": "login", "page_size": 10})
    assert r.status_code == 200
    body = r.json()
    logins_com_usuario = [i for i in body["items"] if i.get("usuario_id") is not None]
    if logins_com_usuario:
        assert logins_com_usuario[0]["usuario_nome"] is not None
