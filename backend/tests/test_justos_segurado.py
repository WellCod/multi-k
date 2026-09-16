"""Segurado PF/PJ, CEPs distintos, nome social declarado e enums fechados."""

from typing import Any

import pytest

from app.adapters.justos.adapter import _payload_cotacao

_BASE: dict[str, Any] = {
    "nome": "Maria Souza Andrade",
    "sexo": "F",
    "data_nascimento": "1988-02-03",
    "cep_pernoite": "01310100",
    "codigo_fipe": "023108-8",
    "ano_modelo": "2022",
    "finalidade": "pessoal",
}


def _payload(**extra: Any) -> dict[str, Any]:
    return _payload_cotacao({**_BASE, "cpf": "12345678901", **extra})


def test_pj_envia_cnpj_sem_dados_de_pessoa_fisica() -> None:
    insured = _payload(cpf="40317530000182")["insured"]
    assert insured["cpf_cnpj"] == "40317530000182"
    assert "gender" not in insured
    assert "birth_date" not in insured


def test_pf_mantem_genero_e_nascimento() -> None:
    insured = _payload()["insured"]
    assert insured["gender"] == "F"
    assert insured["birth_date"] == "1988-02-03"


def test_pontuacao_do_documento_e_descartada() -> None:
    assert _payload(cpf="123.456.789-01")["insured"]["cpf_cnpj"] == "12345678901"


@pytest.mark.parametrize("documento", ["1234567890", "123456789012", ""])
def test_documento_com_tamanho_invalido_e_recusado(documento: str) -> None:
    with pytest.raises(ValueError):
        _payload(cpf=documento)


def test_nome_social_nao_e_deduzido_do_nome_legal() -> None:
    assert "social_name" not in _payload()["insured"]


def test_nome_social_declarado_e_enviado() -> None:
    assert _payload(nome_social="Mari")["insured"]["social_name"] == "Mari"


def test_cep_do_segurado_nao_se_confunde_com_o_pernoite() -> None:
    payload = _payload(cep_segurado="04567000")
    assert payload["insured"]["cep"] == "04567000"
    assert payload["vehicle_overnight_cep"] == "01310100"


def test_cotacao_antiga_sem_cep_do_segurado_preserva_o_dado() -> None:
    payload = _payload()
    assert payload["insured"]["cep"] == "01310100"
    assert payload["vehicle_overnight_cep"] == "01310100"


def test_leilao_chega_a_seguradora() -> None:
    assert _payload(leilao=True)["is_auction"] is True


def test_ausencia_de_leilao_e_falso() -> None:
    assert _payload()["is_auction"] is False


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [("pessoal", "personal"), ("comercial", "commercial"), ("app", "app_driver")],
)
def test_finalidade_mapeia_para_o_enum(codigo: str, esperado: str) -> None:
    assert _payload(finalidade=codigo)["vehicle_use"] == esperado


def test_finalidade_desconhecida_nao_vira_particular() -> None:
    with pytest.raises(ValueError, match="finalidade fora do enum"):
        _payload(finalidade="frota")


_CONDUTOR: dict[str, Any] = {
    "condutor_cpf": "98765432100",
    "condutor_nome": "João Souza",
    "condutor_sexo": "M",
    "condutor_nascimento": "1990-03-12",
}


def test_segurado_condutor_omite_o_bloco_main_driver() -> None:
    assert "main_driver" not in _payload()


def test_parentesco_traduz_para_o_enum() -> None:
    payload = _payload(**_CONDUTOR, condutor_parentesco="conjuge")
    assert payload["main_driver"]["relationship"] == "spouse"


def test_parentesco_desconhecido_nao_passa_cru() -> None:
    with pytest.raises(ValueError, match="condutor_parentesco fora do enum"):
        _payload(**_CONDUTOR, condutor_parentesco="primo")


def test_nome_social_do_condutor_tambem_e_declarado() -> None:
    assert "social_name" not in _payload(**_CONDUTOR)["main_driver"]
    payload = _payload(**_CONDUTOR, condutor_nome_social="Jo")
    assert payload["main_driver"]["social_name"] == "Jo"


@pytest.mark.parametrize(
    "ausente", ["condutor_nome", "condutor_sexo", "condutor_nascimento"]
)
def test_condutor_informado_nao_aceita_campo_vazio(ausente: str) -> None:
    """J2 §4: opcionais só enquanto o bloco não existe."""
    with pytest.raises(ValueError, match=ausente):
        _payload(**{**_CONDUTOR, ausente: ""})


def test_cpf_do_condutor_fora_do_formato_e_recusado() -> None:
    with pytest.raises(ValueError, match="condutor_cpf"):
        _payload(**{**_CONDUTOR, "condutor_cpf": "9876543210"})
