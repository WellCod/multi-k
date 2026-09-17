"""Normaliza somente condições explícitas do pricing; não calcula parcelas."""

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel

from app.adapters.base import (
    CondicaoTransmissaoError,
    PreparacaoTransmissao,
    SelecaoTransmissao,
)
from app.adapters.money import to_decimal


class PaymentOption(BaseModel):
    periodicidade: Literal["monthly", "annual"]
    parcelas: int
    valor_parcela: str | None
    valor_total: str | None


def _money(raw: object) -> str | None:
    amount = to_decimal(raw)
    return None if amount is None else str(amount)


def payment_options(pricing: dict[str, object]) -> list[PaymentOption]:
    options: list[PaymentOption] = []
    periods: tuple[Literal["monthly", "annual"], ...] = ("monthly", "annual")
    for period in periods:
        section = pricing.get(period)
        rows = section.get("installments") if isinstance(section, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            months = row.get("months")
            if type(months) is not int or not 1 <= months <= 12:
                continue
            options.append(
                PaymentOption(
                    periodicidade=period,
                    parcelas=months,
                    valor_parcela=_money(row.get("amount")),
                    valor_total=_money(row.get("total_amount")),
                )
            )
    return options


def confirmed_option(payload: dict[str, object], index: int | None) -> PaymentOption:
    rows = payload.get("condicoes_pagamento")
    if not isinstance(rows, list) or index is None or not 0 <= index < len(rows):
        raise CondicaoTransmissaoError(
            "Selecione uma condição confirmada pela seguradora. "
            "Recalcule se não houver opções.",
        )
    try:
        option = PaymentOption.model_validate(rows[index])
    except ValueError as exc:
        raise CondicaoTransmissaoError(
            "Condição indisponível. Recalcule a cotação."
        ) from exc
    if (
        not 1 <= option.parcelas <= 12
        or (option.periodicidade == "monthly" and option.parcelas != 1)
        or _money(option.valor_parcela) is None
        or _money(option.valor_total) is None
    ):
        raise CondicaoTransmissaoError(
            "Valores não informados pela seguradora. "
            "Recalcule e revise antes de transmitir.",
        )
    return option


def quoted_commission(payload: dict[str, object]) -> Decimal:
    """Comissão que a seguradora usou para precificar, em fração."""
    raw = payload.get("comissao_pct_cotada")
    if raw is None or isinstance(raw, (bool, dict, list)):
        raise CondicaoTransmissaoError(
            "Cotação sem comissão confirmada pela seguradora. "
            "Recotize antes de transmitir.",
        )
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise CondicaoTransmissaoError(
            "Comissão da cotação ilegível. Recotize antes de transmitir."
        ) from exc


def prepare_transmission(
    payload: dict[str, object], selection: SelecaoTransmissao
) -> PreparacaoTransmissao:
    business = dict(selection.dados_negocio)
    if business.get("coverages_selected") != payload.get("coverages_selected"):
        raise CondicaoTransmissaoError(
            "Aplique a revisão de coberturas antes de transmitir."
        )
    quoted = quoted_commission(payload)
    if selection.comissao_pct != quoted:
        raise CondicaoTransmissaoError(
            f"A comissão difere da cotada na seguradora ({quoted * 100:.0f}%). "
            "Recotize com o novo percentual antes de transmitir.",
        )
    option = confirmed_option(payload, selection.opcao_pagamento)
    if selection.parcelas != option.parcelas:
        raise CondicaoTransmissaoError(
            "O parcelamento diverge da condição selecionada."
        )
    business["policy_type"] = option.periodicidade
    business["installments"] = (
        option.parcelas if option.periodicidade == "annual" else None
    )
    business["scheduling_date"] = (
        selection.inicio_vigencia.isoformat() if selection.inicio_vigencia else None
    )
    return PreparacaoTransmissao(
        dados_negocio=business,
        plano_pagamento=(
            "MENSAL"
            if option.periodicidade == "monthly"
            else f"ANUAL_{option.parcelas}X"
        ),
        valor_parcela=Decimal(str(option.valor_parcela)),
        condicao_pagamento=option.model_dump(),
        comissao_pct=quoted,
    )
