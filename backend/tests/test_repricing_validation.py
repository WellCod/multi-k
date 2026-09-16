"""Recálculo não pode fabricar valores nem encaminhar outra CIA à Justos."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.comparativo_router import (
    RepricingInput,
    _confirmed_price,
    _validate_selection,
    repricing,
)
from app.infra.models import CotacaoJob


def coverage_job() -> CotacaoJob:
    return CotacaoJob(
        cia="justos",
        status="concluido",
        status_resultado="sucesso",
        payload_resposta={
            "quote_id": "synthetic",
            "comissao_pct_cotada": "0.15",
            "coverages_available": {
                "required": {
                    "mandatory": True,
                    "peril_options": [{"slug": "required-option"}],
                },
                "optional": {
                    "mandatory": False,
                    "peril_options": [{"slug": "optional-option"}],
                },
            },
        },
    )


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"required": None},
        {"required": "invented"},
        {"required": "optional-option"},
        {"required": "required-option", "unknown": None},
    ],
)
def test_invalid_coverage_selection(selection: dict[str, str | None]) -> None:
    with pytest.raises(HTTPException) as error:
        _validate_selection(coverage_job(), selection)
    assert error.value.status_code == 422


@pytest.mark.parametrize("optional", [None, "optional-option"])
def test_valid_coverage_selection(optional: str | None) -> None:
    _validate_selection(
        coverage_job(), {"required": "required-option", "optional": optional}
    )


def test_missing_catalog_requires_refresh() -> None:
    with pytest.raises(HTTPException) as error:
        _validate_selection(CotacaoJob(payload_resposta={}), {})
    assert error.value.status_code == 409


async def test_invalid_selection_never_calls_provider() -> None:
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: coverage_job())
    with (
        patch("app.api.comparativo_router._get_cotacao_ou_404", new_callable=AsyncMock),
        patch(
            "app.api.comparativo_router.justos_client.calcular_preco",
            new_callable=AsyncMock,
        ) as provider,
    ):
        with pytest.raises(HTTPException):
            await repricing(
                uuid4(),
                RepricingInput(cia="justos", coverages_selected={}),
                SimpleNamespace(id=uuid4()),
                db,
            )
        provider.assert_not_awaited()


@pytest.mark.parametrize(
    "value", [None, {}, True, [], "NaN", "Infinity", "-1", "invalid"]
)
def test_invalid_price_is_not_zero(value: object) -> None:
    with pytest.raises(HTTPException) as error:
        _confirmed_price({"monthly": {"total": value}}, "monthly")
    assert error.value.status_code == 502


@pytest.mark.parametrize("section", [None, [], "invalid", {}])
def test_missing_section_is_not_zero(section: object) -> None:
    with pytest.raises(HTTPException):
        _confirmed_price({"annual": section}, "annual")


@pytest.mark.parametrize("value", ["0", "100.25", "999.99"])
def test_confirmed_price_preserved(value: str) -> None:
    assert _confirmed_price({"monthly": {"total": value}}, "monthly") == Decimal(value)


async def test_other_insurer_never_calls_justos() -> None:
    db = AsyncMock()
    with (
        patch("app.api.comparativo_router._get_cotacao_ou_404", new_callable=AsyncMock),
        patch(
            "app.api.comparativo_router.justos_client.calcular_preco",
            new_callable=AsyncMock,
        ) as provider,
    ):
        with pytest.raises(HTTPException) as error:
            await repricing(
                uuid4(),
                RepricingInput(cia="fake", coverages_selected={}),
                SimpleNamespace(id=uuid4()),
                db,
            )
        assert error.value.status_code == 422
        provider.assert_not_awaited()
        db.execute.assert_not_awaited()
