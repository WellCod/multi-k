"""Catálogo de seguradora anterior para renovação (J2 §4.2)."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.adapters.justos import client as justos_client
from app.adapters.justos.adapter import JustosSeguradora, _payload_cotacao
from app.domain.auth import Papel
from app.infra.secrets import EnvSecretProvider, set_provider
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

_BASE = "https://api.staging.justos.com.br"
_AUTH_URL = f"{_BASE}/brokers/auth/api-token"
_INSURER_URL = f"{_BASE}/brokers/insurer"

_TEST_EC_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgYqQQSZA0evZwbYt+\n"
    "9jewzOhw0/IQm01U6mKufI1vo2OhRANCAAQt5Sb19Sv1EeFXd0/9nS9f2saBhQE0\n"
    "kqQklcBPMV06ju1TZVaKL+6T9piYvnKWMgGkxYdalAOOnuA98qtllZXI\n"
    "-----END PRIVATE KEY-----\n"
)

_CATALOGO = [
    {"code": 5355, "name": "Azul Seguros"},
    {"code": 6467, "name": "Alfa Seguradora"},
]

_RISCO: dict[str, Any] = {
    "cpf": "12345678901",
    "nome": "Maria Souza",
    "cep_pernoite": "01310100",
    "codigo_fipe": "023108-8",
    "ano_modelo": "2022",
    "finalidade": "pessoal",
}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_PARTNER_NAME", "test_partner")
    monkeypatch.setenv("JUSTOS_BROKER_ID", "1")
    monkeypatch.setenv("JUSTOS_CPF_CNPJ", "00000000000")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY", _TEST_EC_KEY)
    monkeypatch.setenv("JUSTOS_ENV", "staging")
    set_provider(EnvSecretProvider())
    justos_client._invalida_cache()
    justos_client._invalida_catalogo()


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


def _mock(router: respx.MockRouter, payload: Any) -> Any:
    router.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
    return router.get(_INSURER_URL).mock(return_value=Response(200, json=payload))


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


async def test_catalogo_vem_ordenado_por_nome() -> None:
    with respx.mock as r:
        _mock(r, _CATALOGO)
        catalogo = await JustosSeguradora().seguradoras_anteriores()

    assert [s.nome for s in catalogo] == ["Alfa Seguradora", "Azul Seguros"]
    assert catalogo[0].codigo == 6467


@pytest.mark.parametrize(
    "entrada",
    [
        {"code": 1, "name": "   "},
        {"code": "6467", "name": "Alfa"},
        {"code": True, "name": "Alfa"},
        {"name": "Sem código"},
        "texto solto",
    ],
)
async def test_entrada_sem_codigo_utilizavel_e_descartada(entrada: Any) -> None:
    with respx.mock as r:
        _mock(r, [entrada])
        assert await JustosSeguradora().seguradoras_anteriores() == []


async def test_catalogo_e_cacheado_entre_cotacoes() -> None:
    """O catálogo muda raramente: não custa uma ida à rede por cotação."""
    with respx.mock as r:
        rota = _mock(r, _CATALOGO)
        await JustosSeguradora().seguradoras_anteriores()
        await JustosSeguradora().seguradoras_anteriores()

    assert rota.call_count == 1


# ---------------------------------------------------------------------------
# Payload da cotação
# ---------------------------------------------------------------------------


def test_codigo_da_seguradora_anterior_so_vai_em_renovacao() -> None:
    payload = _payload_cotacao(
        {**_RISCO, "tipo_negocio": "renovacao", "insurer_code": 6467}
    )
    assert payload["insurer_code"] == 6467


def test_codigo_em_negocio_novo_e_recusado() -> None:
    with pytest.raises(ValueError, match="só se aplica a renovação"):
        _payload_cotacao({**_RISCO, "insurer_code": 6467})


def test_codigo_vazio_nao_entra_no_payload() -> None:
    assert "insurer_code" not in _payload_cotacao({**_RISCO, "insurer_code": ""})


# ---------------------------------------------------------------------------
# Rota
# ---------------------------------------------------------------------------


async def test_rota_devolve_o_catalogo(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine
) -> None:
    await _login(client, db, "catalogo_ok@test.com")
    with respx.mock as r:
        _mock(r, _CATALOGO)
        resp = await client.get("/dominios/seguradoras-anteriores?cia=justos")

    assert resp.status_code == 200
    assert resp.json()[0] == {"codigo": 6467, "nome": "Alfa Seguradora"}


async def test_rota_recusa_cia_sem_catalogo(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine
) -> None:
    await _login(client, db, "catalogo_fake@test.com")
    resp = await client.get("/dominios/seguradoras-anteriores?cia=fake")
    assert resp.status_code == 422
    assert "catálogo" in resp.json()["detail"]


async def test_rota_recusa_cia_desconhecida(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine
) -> None:
    await _login(client, db, "catalogo_inexistente@test.com")
    resp = await client.get("/dominios/seguradoras-anteriores?cia=naoexiste")
    assert resp.status_code == 422


async def test_rota_nao_expoe_resposta_bruta_da_seguradora(
    client: AsyncClient, db: AsyncSession, engine: AsyncEngine
) -> None:
    await _login(client, db, "catalogo_erro@test.com")
    with respx.mock as r:
        r.post(_AUTH_URL).mock(return_value=Response(200, json={"token": "t"}))
        r.get(_INSURER_URL).mock(
            return_value=Response(500, json={"trace": "private-internal-detail"})
        )
        resp = await client.get("/dominios/seguradoras-anteriores?cia=justos")

    assert resp.status_code == 502
    assert "private-internal-detail" not in resp.text
