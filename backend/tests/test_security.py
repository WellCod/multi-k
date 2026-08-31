"""Testes de segurança: CSRF middleware, validadores M4 e rate-limit FIPE."""

from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proposta_router import TransmitirInput
from app.domain.auth import Papel
from app.main import app
from tests.conftest import CsrfAuth, criar_usuario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        c._auth = CsrfAuth(c.cookies)  # type: ignore[assignment]
        yield c


@pytest_asyncio.fixture
async def plain_client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente sem CsrfAuth — para testar que a proteção CSRF está ativa."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _login_plain(
    client: AsyncClient,
    db: AsyncSession,
    email: str,
) -> None:
    """Faz login via plain_client (rota /auth/login é isenta de CSRF)."""
    await criar_usuario(db, email, Papel.CORRETOR)
    await db.commit()
    r = await client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Testes CSRF
# ---------------------------------------------------------------------------


async def test_csrf_post_sem_token_retorna_403(
    db: AsyncSession, plain_client: AsyncClient
) -> None:
    """POST autenticado sem X-CSRF-Token deve retornar 403."""
    await _login_plain(plain_client, db, "csrf_notoken@test.com")
    # sid cookie presente; sem o header CSRF
    r = await plain_client.post(
        "/cotacoes",
        json={
            "ramo": "auto",
            "dados": {
                "codigo_fipe": "001004-9",
                "finalidade": "pessoal",
                "cep_pernoite": "13010001",
            },
        },
    )
    assert r.status_code == 403


async def test_csrf_post_token_errado_retorna_403(
    db: AsyncSession, plain_client: AsyncClient
) -> None:
    """POST autenticado com X-CSRF-Token errado deve retornar 403."""
    await _login_plain(plain_client, db, "csrf_wrongtoken@test.com")
    r = await plain_client.post(
        "/cotacoes",
        json={"ramo": "auto", "dados": {}},
        headers={"X-CSRF-Token": "token-invalido"},
    )
    assert r.status_code == 403


async def test_csrf_login_isento(plain_client: AsyncClient) -> None:
    """/auth/login é isento de CSRF — não deve retornar 403."""
    r = await plain_client.post(
        "/auth/login",
        json={"email": "naoexiste@test.com", "senha": "qualquer"},
    )
    assert r.status_code != 403


async def test_csrf_get_isento(db: AsyncSession, client: AsyncClient) -> None:
    """GET (método seguro) não exige CSRF — deve retornar 200 ou 401, não 403."""
    r = await client.get("/cotacoes")
    assert r.status_code != 403


# ---------------------------------------------------------------------------
# Testes M4 — validador dados_negocio
# ---------------------------------------------------------------------------


def test_m4_dados_negocio_mais_de_50_chaves_levanta_validation_error() -> None:
    """TransmitirInput com >50 chaves em dados_negocio deve levantar ValidationError."""
    dados_grandes = {str(i): i for i in range(51)}
    with pytest.raises(ValidationError, match="50 chaves"):
        TransmitirInput(
            plano_pagamento="mensal",
            n_parcelas=1,
            comissao_pct=Decimal("0.05"),
            dados_negocio=dados_grandes,
        )


def test_m4_dados_negocio_acima_de_10kb_levanta_validation_error() -> None:
    """TransmitirInput com valor >10 KB em dados_negocio levanta ValidationError."""
    dados_grandes = {"chave": "x" * 10_001}
    with pytest.raises(ValidationError, match="10 KB"):
        TransmitirInput(
            plano_pagamento="mensal",
            n_parcelas=1,
            comissao_pct=Decimal("0.05"),
            dados_negocio=dados_grandes,
        )


# ---------------------------------------------------------------------------
# Teste rate-limit FIPE
# ---------------------------------------------------------------------------


async def test_fipe_rate_limit_retorna_429(plain_client: AsyncClient) -> None:
    """Quando rate_limit.allow retorna False, GET /fipe/marcas deve retornar 429."""
    with patch(
        "app.api.fipe_router.rate_limit.allow",
        new=AsyncMock(return_value=False),
    ):
        r = await plain_client.get("/fipe/marcas")
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# Testes rate_limit.allow — lógica da janela deslizante
# ---------------------------------------------------------------------------


async def test_rate_limit_permite_dentro_do_limite() -> None:
    """Requisições dentro do limite devem retornar True."""
    from app.infra import rate_limit as rl

    key = "test_allow_dentro"
    rl._counters.pop(key, None)
    for _ in range(5):
        assert await rl.allow(key, max_requests=5, window_seconds=60.0) is True


async def test_rate_limit_bloqueia_apos_limite() -> None:
    """A requisição N+1 deve retornar False quando o limite é N."""
    from app.infra import rate_limit as rl

    key = "test_allow_bloqueia"
    rl._counters.pop(key, None)
    for _ in range(3):
        await rl.allow(key, max_requests=3, window_seconds=60.0)
    assert await rl.allow(key, max_requests=3, window_seconds=60.0) is False


async def test_rate_limit_janela_expirada_permite_novamente() -> None:
    """Entradas fora da janela são descartadas e a chave volta a ser permitida."""
    import time

    from app.infra import rate_limit as rl

    key = "test_allow_expirada"
    rl._counters[key] = [time.monotonic() - 120.0]  # timestamp já expirado
    assert await rl.allow(key, max_requests=1, window_seconds=60.0) is True


# ---------------------------------------------------------------------------
# Testes encryption.EncryptedJSON — roundtrip AES-256-GCM
# ---------------------------------------------------------------------------


def test_encrypted_json_roundtrip() -> None:
    """Encrypt→decrypt deve devolver o mesmo objeto."""
    import os

    os.environ.setdefault("PAYLOAD_ENCRYPTION_KEY", "0" * 64)
    from app.infra.encryption import EncryptedJSON

    col = EncryptedJSON()
    original = {"cpf": "12345678901", "valor": 1500.50, "lista": [1, 2, 3]}
    ciphertext = col.process_bind_param(original, None)
    assert ciphertext is not None
    assert ciphertext != str(original)  # efectivamente cifrado
    recovered = col.process_result_value(ciphertext, None)
    assert recovered == original


def test_encrypted_json_none_passa_transparente() -> None:
    """None deve passar sem cifrar e sem erro."""
    from app.infra.encryption import EncryptedJSON

    col = EncryptedJSON()
    assert col.process_bind_param(None, None) is None
    assert col.process_result_value(None, None) is None


def test_encrypted_json_chave_invalida_levanta_erro() -> None:
    """Chave com tamanho errado deve levantar ValueError."""
    import os
    from unittest.mock import patch

    from app.infra.encryption import EncryptedJSON

    col = EncryptedJSON()
    with (
        patch.dict(os.environ, {"PAYLOAD_ENCRYPTION_KEY": "aabbcc"}),
        pytest.raises((ValueError, RuntimeError)),
    ):
        col.process_bind_param({"x": 1}, None)


def test_encrypted_json_chave_ausente_levanta_runtime_error() -> None:
    """Chave completamente ausente deve levantar RuntimeError."""
    import os
    from unittest.mock import patch

    from app.infra.encryption import EncryptedJSON

    col = EncryptedJSON()
    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(RuntimeError, match="PAYLOAD_ENCRYPTION_KEY"),
    ):
        col.process_bind_param({"x": 1}, None)
