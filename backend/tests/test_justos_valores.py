"""Dinheiro em Decimal e sem zeros inventados (regra interna e J3 §6)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.adapters.justos.adapter import _selecionar_coberturas, _total
from app.adapters.justos.payment import to_decimal


def _peril(*precos: object, mandatory: bool = True) -> dict[str, Any]:
    return {
        "mandatory": mandatory,
        "peril_options": [
            {"slug": f"opcao-{i}", "price": preco} for i, preco in enumerate(precos)
        ],
    }


@pytest.mark.parametrize("bruto", [None, "", "grátis", "NaN", "-10", True, {}, []])
def test_valor_invalido_nao_vira_zero(bruto: object) -> None:
    assert to_decimal(bruto) is None


def test_valor_explicito_vira_decimal_com_duas_casas() -> None:
    assert to_decimal("250.5") == Decimal("250.50")
    assert to_decimal(0) == Decimal("0.00")


def test_total_ausente_nao_vira_premio_zero() -> None:
    assert _total({}, "monthly") is None
    assert _total({"monthly": {}}, "monthly") is None
    assert _total({"monthly": "250.00"}, "monthly") is None


def test_total_informado_e_preservado() -> None:
    assert _total({"monthly": {"total": "250.5"}}, "monthly") == Decimal("250.50")


def test_opcao_sem_preco_nao_e_a_mais_barata() -> None:
    """Preço ausente é desconhecido, não zero — senão a escolha seria falsa."""
    selecionadas = _selecionar_coberturas({"casco": _peril(None, "80.00", "120.00")})
    assert selecionadas["casco"] == "opcao-1"


def test_cobertura_obrigatoria_sem_preco_algum_interrompe() -> None:
    with pytest.raises(ValueError, match="não informou preço"):
        _selecionar_coberturas({"casco": _peril(None, "sob consulta")})


def test_comparacao_usa_decimal_e_nao_ordem_alfabetica() -> None:
    selecionadas = _selecionar_coberturas({"casco": _peril("9.00", "100.00")})
    assert selecionadas["casco"] == "opcao-0"
