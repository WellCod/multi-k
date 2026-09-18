"""Ambiente e chave da Justos: errar precisa doer na hora, não em produção.

Antes, JUSTOS_ENV com qualquer valor fora de "production" caía em staging sem
avisar — e o badge STAGING da interface sumia, porque testava igualdade com
"staging". A combinação pior possível: cotando em teste com a tela afirmando
produção.
"""

from __future__ import annotations

import pathlib

import pytest

from app.adapters.justos import client
from app.infra.secrets import EnvSecretProvider, set_provider
from tests.conftest import CHAVE_EC_TESTE as _CHAVE


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_PARTNER_NAME", "parceiro_teste")
    monkeypatch.setenv("JUSTOS_BROKER_ID", "1")
    monkeypatch.setenv("JUSTOS_CPF_CNPJ", "00000000000")
    monkeypatch.delenv("JUSTOS_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("JUSTOS_PRIVATE_KEY", raising=False)
    set_provider(EnvSecretProvider())


def test_ambiente_padrao_e_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JUSTOS_ENV", raising=False)
    assert client.ambiente() == "staging"


@pytest.mark.parametrize("valor", ["staging", "production", " production "])
def test_ambientes_validos(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    monkeypatch.setenv("JUSTOS_ENV", valor)
    assert client.ambiente() == valor.strip()


@pytest.mark.parametrize("valor", ["prod", "producao", "Production", "homolog"])
def test_ambiente_invalido_nao_cai_para_staging(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    """Typo tem de falhar aqui; antes virava staging silencioso."""
    monkeypatch.setenv("JUSTOS_ENV", valor)
    with pytest.raises(RuntimeError, match="JUSTOS_ENV inválido"):
        client.ambiente()


def test_url_segue_o_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_ENV", "production")
    assert client._base_url() == "https://api.justos.com.br"
    monkeypatch.setenv("JUSTOS_ENV", "staging")
    assert client._base_url() == "https://api.staging.justos.com.br"


def test_producao_recusa_chave_em_arquivo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """O par de produção é outro: caminho herdado do dev assinaria errado."""
    arquivo = tmp_path / "dev.pem"
    arquivo.write_text(_CHAVE)
    monkeypatch.setenv("JUSTOS_ENV", "production")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY_PATH", str(arquivo))

    with pytest.raises(RuntimeError, match="não vale em produção"):
        client._gerar_jwt()


def test_staging_aceita_chave_em_arquivo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    arquivo = tmp_path / "dev.pem"
    arquivo.write_text(_CHAVE)
    monkeypatch.setenv("JUSTOS_ENV", "staging")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY_PATH", str(arquivo))

    assert client._gerar_jwt()


def test_producao_assina_com_a_chave_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUSTOS_ENV", "production")
    monkeypatch.setenv("JUSTOS_PRIVATE_KEY", _CHAVE.replace("\n", "\n"))

    assert client._gerar_jwt()
