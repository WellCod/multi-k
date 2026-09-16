"""A comissão cotada é a única que a transmissão pode registrar."""

from decimal import Decimal

import pytest

from app.adapters.base import CondicaoTransmissaoError, SelecaoTransmissao
from app.adapters.justos.adapter import _comissao_cotada, _payload_cotacao
from app.adapters.justos.payment import prepare_transmission

_RISCO = {
    "cpf": "12345678901",
    "nome": "Fulano de Tal",
    "codigo_fipe": "023108-8",
    "ano_modelo": "2020",
    "cep_pernoite": "01310100",
    "finalidade": "pessoal",
}

_COBERTURAS = {"colisao-e-desastres-naturais": "franquia-reduzida"}


def _payload(comissao: object) -> dict[str, object]:
    return {
        "coverages_selected": _COBERTURAS,
        "comissao_pct_cotada": comissao,
        "condicoes_pagamento": [
            {
                "periodicidade": "monthly",
                "parcelas": 1,
                "valor_parcela": "250.00",
                "valor_total": "250.00",
            }
        ],
    }


def _selecao(comissao: str) -> SelecaoTransmissao:
    return SelecaoTransmissao(
        opcao_pagamento=0,
        parcelas=1,
        inicio_vigencia=None,
        dados_negocio={"coverages_selected": _COBERTURAS},
        comissao_pct=Decimal(comissao),
    )


def test_ausencia_usa_default_do_corretor() -> None:
    assert _comissao_cotada({}) == 15
    assert _comissao_cotada({"comissao_pct": ""}) == 15


def test_fracao_canonica_vira_percentual_inteiro() -> None:
    assert _comissao_cotada({"comissao_pct": "0.20"}) == 20
    assert (
        _payload_cotacao({**_RISCO, "comissao_pct": Decimal("0.25")})[
            "broker_commission_percentage"
        ]
        == 25
    )


@pytest.mark.parametrize("bruto", ["0.05", "0.30", "0", "1"])
def test_fora_da_faixa_da_seguradora_e_recusado(bruto: str) -> None:
    with pytest.raises(ValueError, match="faixa aceita pela Justos"):
        _comissao_cotada({"comissao_pct": bruto})


def test_percentual_quebrado_nao_e_arredondado() -> None:
    with pytest.raises(ValueError, match="percentual inteiro"):
        _comissao_cotada({"comissao_pct": "0.155"})


def test_valor_ilegivel_nao_vira_default() -> None:
    with pytest.raises(ValueError, match="inválida"):
        _comissao_cotada({"comissao_pct": "quinze"})


def test_transmissao_registra_a_comissao_cotada() -> None:
    preparado = prepare_transmission(_payload("0.15"), _selecao("0.1500"))
    assert preparado.comissao_pct == Decimal("0.15")


def test_comissao_editada_exige_recotacao() -> None:
    with pytest.raises(CondicaoTransmissaoError, match="difere da cotada"):
        prepare_transmission(_payload("0.15"), _selecao("0.20"))


def test_cotacao_legada_sem_comissao_confirmada_bloqueia() -> None:
    payload = _payload("0.15")
    del payload["comissao_pct_cotada"]
    with pytest.raises(CondicaoTransmissaoError, match="Recotize"):
        prepare_transmission(payload, _selecao("0.15"))


def test_comissao_cotada_ilegivel_bloqueia_a_transmissao() -> None:
    with pytest.raises(CondicaoTransmissaoError, match="ilegível"):
        prepare_transmission(_payload("quinze por cento"), _selecao("0.15"))
