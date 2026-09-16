"""Seleção de coberturas na cotação (J2 §4–6): mandatory, slug e quirk staging."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.adapters.base import CondicaoTransmissaoError, SelecaoTransmissao
from app.adapters.justos.adapter import _PERILS_CORE, _selecionar_coberturas
from app.adapters.justos.payment import prepare_transmission


def _peril(*slugs_e_precos: tuple[str, str], mandatory: bool = False) -> dict[str, Any]:
    return {
        "mandatory": mandatory,
        "peril_options": [
            {"slug": slug, "price": preco} for slug, preco in slugs_e_precos
        ],
    }


_CORE = "roubo-e-furto"
_EXTRA = "backup-car"


def test_core_e_um_subconjunto_das_coberturas_declaradas() -> None:
    assert _CORE in _PERILS_CORE
    assert _EXTRA not in _PERILS_CORE


def test_obrigatoria_recebe_a_opcao_mais_barata() -> None:
    selecao = _selecionar_coberturas(
        {_CORE: _peril(("cara", "120.00"), ("barata", "80.00"), mandatory=True)}
    )
    assert selecao[_CORE] == "barata"


def test_opcional_fica_sem_escolha_quando_existe_obrigatoria() -> None:
    """Com mandatory na resposta, add-on opcional não entra sozinho no prêmio."""
    selecao = _selecionar_coberturas(
        {
            _CORE: _peril(("basica", "80.00"), mandatory=True),
            _EXTRA: _peril(("extra", "30.00")),
        }
    )
    assert selecao == {_CORE: "basica", _EXTRA: None}


def test_core_nao_obrigatoria_nao_e_escolhida_quando_ha_obrigatoria() -> None:
    outra_core = "incendio"
    selecao = _selecionar_coberturas(
        {
            _CORE: _peril(("basica", "80.00"), mandatory=True),
            outra_core: _peril(("tambem-core", "40.00")),
        }
    )
    assert selecao[outra_core] is None


def test_quirk_do_staging_seleciona_apenas_o_nucleo() -> None:
    """Staging devolve mandatory=False para tudo; o núcleo não pode sumir."""
    selecao = _selecionar_coberturas(
        {
            _CORE: _peril(("basica", "80.00")),
            _EXTRA: _peril(("extra", "30.00")),
        }
    )
    assert selecao == {_CORE: "basica", _EXTRA: None}


def test_cobertura_sem_opcoes_e_omitida() -> None:
    selecao = _selecionar_coberturas(
        {_CORE: _peril(("basica", "80.00"), mandatory=True), "vazia": _peril()}
    )
    assert "vazia" not in selecao


def test_slug_escolhido_pertence_a_propria_cobertura() -> None:
    selecao = _selecionar_coberturas(
        {
            _CORE: _peril(("roubo-a", "80.00"), mandatory=True),
            "incendio": _peril(("incendio-a", "20.00"), mandatory=True),
        }
    )
    assert selecao[_CORE] == "roubo-a"
    assert selecao["incendio"] == "incendio-a"


def test_transmissao_recusa_selecao_diferente_da_aplicada() -> None:
    """O caminho de transmissão não aceita seleção que não passou pela revisão."""
    payload = {
        "coverages_selected": {_CORE: "basica"},
        "comissao_pct_cotada": "0.15",
        "condicoes_pagamento": [
            {
                "periodicidade": "monthly",
                "parcelas": 1,
                "valor_parcela": "80.00",
                "valor_total": "80.00",
            }
        ],
    }
    selecao = SelecaoTransmissao(
        opcao_pagamento=0,
        parcelas=1,
        inicio_vigencia=None,
        dados_negocio={"coverages_selected": {_CORE: "outra"}},
        comissao_pct=Decimal("0.15"),
    )
    with pytest.raises(CondicaoTransmissaoError, match="Aplique a revisão"):
        prepare_transmission(payload, selecao)
