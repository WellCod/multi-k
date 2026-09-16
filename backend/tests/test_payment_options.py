"""Condições da seguradora preservadas sem inferência financeira."""

import pytest

from app.adapters.base import CondicaoTransmissaoError
from app.adapters.justos.payment import confirmed_option, payment_options


def test_explicit_values_preserved_and_extra_fields_removed() -> None:
    options = payment_options(
        {
            "annual": {
                "installments": [
                    {
                        "months": 2,
                        "amount": "2565.00",
                        "total_amount": "5130.00",
                        "secret": "must-not-leak",
                    }
                ]
            }
        }
    )
    assert options[0].model_dump() == {
        "periodicidade": "annual",
        "parcelas": 2,
        "valor_parcela": "2565.00",
        "valor_total": "5130.00",
    }


def test_missing_amount_not_derived_from_total() -> None:
    option = payment_options(
        {"annual": {"installments": [{"months": 10, "total_amount": "5400"}]}}
    )[0]
    assert option.valor_total == "5400.00"
    assert option.valor_parcela is None


def test_missing_options_not_invented_from_info_or_total() -> None:
    assert payment_options({"annual": {"total": "5400"}, "info": "10x sem juros"}) == []


@pytest.mark.parametrize("raw", [True, -1, "NaN", "Infinity", {}, None])
def test_invalid_money_is_unknown(raw: object) -> None:
    option = payment_options(
        {"monthly": {"installments": [{"months": 1, "amount": raw}]}}
    )[0]
    assert option.valor_parcela is None


@pytest.mark.parametrize("months", [True, "2", 0, 13, None])
def test_invalid_installment_count_rejected(months: object) -> None:
    assert payment_options({"annual": {"installments": [{"months": months}]}}) == []


def test_valor_nao_numerico_e_desconhecido() -> None:
    option = payment_options(
        {"monthly": {"installments": [{"months": 1, "amount": "à vista"}]}}
    )[0]
    assert option.valor_parcela is None


def test_linha_que_nao_e_objeto_e_ignorada() -> None:
    assert payment_options({"annual": {"installments": ["2x sem juros", None]}}) == []


def test_condicao_malformada_pede_recalculo() -> None:
    payload = {"condicoes_pagamento": [{"periodicidade": "trimestral"}]}
    with pytest.raises(CondicaoTransmissaoError, match="Condição indisponível"):
        confirmed_option(payload, 0)
