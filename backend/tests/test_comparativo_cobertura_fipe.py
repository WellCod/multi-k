"""coverage_amount zerado é 100% da FIPE, não cobertura de R$ 0,00."""

from app.api.comparativo_router import _comparison_coverages
from app.infra.models import CotacaoJob


def _job(coverage_amount: object) -> CotacaoJob:
    return CotacaoJob(
        cia="justos",
        status="concluido",
        status_resultado="sucesso",
        payload_resposta={
            "coverages_selected": {"casco": "integral"},
            "coverages_available": {
                "casco": {
                    "name": "Casco",
                    "mandatory": True,
                    "peril_options": [
                        {"slug": "integral", "coverage_amount": coverage_amount}
                    ],
                }
            },
        },
    )


def test_zero_vira_percentual_sem_inventar_valor() -> None:
    linha = _comparison_coverages(_job(0))[0]
    assert linha["limite"] is None
    assert linha["limite_descricao"] == "100% da tabela FIPE"


def test_valor_monetario_permanece_valor() -> None:
    linha = _comparison_coverages(_job("45000"))[0]
    assert linha["limite"] == "45000.00"
    assert linha["limite_descricao"] is None


def test_ausencia_nao_vira_percentual() -> None:
    linha = _comparison_coverages(_job(None))[0]
    assert linha["limite"] is None
    assert linha["limite_descricao"] is None
