"""A capacidade de preparação não impõe condições de uma CIA às demais."""

from decimal import Decimal

from app.adapters.base import (
    PreparacaoTransmissao,
    PreparadorTransmissao,
    SelecaoTransmissao,
)
from app.adapters.justos.adapter import JustosSeguradora


def test_preparation_is_optional() -> None:
    class LegacyCarrier:
        pass

    assert not isinstance(LegacyCarrier(), PreparadorTransmissao)
    assert isinstance(JustosSeguradora(), PreparadorTransmissao)


def test_another_carrier_can_prepare_different_terms() -> None:
    class AnotherCarrier:
        def preparar_transmissao(
            self, payload: dict[str, object], selecao: SelecaoTransmissao
        ) -> PreparacaoTransmissao:
            return PreparacaoTransmissao(
                dados_negocio={"forma_local": "boleto"},
                plano_pagamento="SEMESTRAL_BOLETO",
                valor_parcela=Decimal("120.50"),
                condicao_pagamento={"periodo": "semestral"},
                comissao_pct=Decimal("0.12"),
            )

    carrier = AnotherCarrier()
    assert isinstance(carrier, PreparadorTransmissao)
    result = carrier.preparar_transmissao(
        {}, SelecaoTransmissao(None, 1, None, {}, Decimal("0.12"))
    )
    assert result.plano_pagamento == "SEMESTRAL_BOLETO"
    assert result.valor_parcela == Decimal("120.50")
    assert result.comissao_pct == Decimal("0.12")
    assert "policy_type" not in result.dados_negocio
    assert "installments" not in result.dados_negocio
