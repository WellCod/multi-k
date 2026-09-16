"""coverage_amount zerado é 100% da FIPE, não cobertura de R$ 0,00."""

from app.api.comparativo_router import (
    ItemComparativoOut,
    _comparison_coverages,
    _gerar_pdf,
    _observacoes,
)
from app.infra.models import Cotacao, CotacaoJob


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


def _item(info: str | None) -> ItemComparativoOut:
    return ItemComparativoOut(
        cia="justos",
        revisao_base="r",
        cotacao_id_cia="Q-1",
        premio_total=None,
        annual_total=None,
        restricoes=[],
        mensagens=[],
        necessita_vistoria=False,
        status="sucesso",
        info=info,
    )


def test_observacao_da_seguradora_entra_no_pdf() -> None:
    assert _observacoes([_item("Desconto de 5% no anual.")]) == [
        "<b>JUSTOS</b>: Desconto de 5% no anual."
    ]


def test_sem_observacao_nao_gera_secao() -> None:
    assert _observacoes([_item(None)]) == []


def test_texto_do_provedor_nao_vira_markup_do_pdf() -> None:
    """O texto é dado da seguradora, não instrução de formatação."""
    linha = _observacoes([_item("<b>uso & abuso</b>")])[0]
    assert "&lt;b&gt;uso &amp; abuso&lt;/b&gt;" in linha


def test_pdf_com_observacao_e_gerado() -> None:
    pdf = _gerar_pdf(Cotacao(ramo="auto"), [_item("Observação sintética.")])
    assert pdf.startswith(b"%PDF")
