"""Mapeamento do veículo no payload v2 (J2 §4): placa, chassi, FIPE e ano."""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.justos.adapter import _payload_cotacao

_BASE: dict[str, Any] = {
    "cpf": "12345678901",
    "nome": "Maria Souza",
    "cep_pernoite": "01310100",
    "codigo_fipe": "023108-8",
    "ano_modelo": 2022,
    "finalidade": "pessoal",
}


def _payload(**extra: Any) -> dict[str, Any]:
    return _payload_cotacao({**_BASE, **extra})


def test_veiculo_sem_placa_segue_com_chassi() -> None:
    """A placa pode ir vazia; o chassi é o caminho indicado nesse caso."""
    payload = _payload(chassi="99999999999999999")
    assert payload["plate"] == ""
    assert payload["chassis"] == "99999999999999999"


def test_placa_e_chassi_convivem() -> None:
    payload = _payload(placa="FHL4853", chassi="99999999999999999")
    assert payload["plate"] == "FHL4853"
    assert payload["chassis"] == "99999999999999999"


def test_ano_do_modelo_vai_como_texto() -> None:
    assert _payload()["vehicle_model_year"] == "2022"


def test_chave_legada_do_codigo_fipe_e_aceita() -> None:
    dados = {k: v for k, v in _BASE.items() if k != "codigo_fipe"}
    assert (
        _payload_cotacao({**dados, "fipe_codigo": "004321-0"})["vehicle_fipe_code"]
        == "004321-0"
    )


@pytest.mark.parametrize("ausente", ["codigo_fipe", "ano_modelo"])
def test_identificacao_do_veiculo_e_obrigatoria(ausente: str) -> None:
    dados = {k: v for k, v in _BASE.items() if k != ausente}
    with pytest.raises(ValueError, match=ausente):
        _payload_cotacao(dados)


def test_bonus_ausente_vai_como_zero_textual() -> None:
    assert _payload()["previous_bonus"] == "0"
    assert _payload(bonus_anterior=7)["previous_bonus"] == "7"


@pytest.mark.parametrize(
    ("campo", "chave"),
    [
        ("zero_km", "is_zero_km"),
        ("condutor_menor_24", "under_24"),
        ("ja_segurado", "is_insured"),
        ("leilao", "is_auction"),
    ],
)
def test_marcadores_do_veiculo_sao_booleanos(campo: str, chave: str) -> None:
    assert _payload()[chave] is False
    assert _payload(**{campo: True})[chave] is True
