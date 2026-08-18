"""
Adapter fake — valida os 3 estados de retorno e conformidade com a interface.
Latência zerada para os testes não esperarem 8–15s.
"""

import pytest

from app.adapters.base import PortaSeguradora, RiscoCanonico
from app.adapters.fake import FakeSeguradora

_RISCO_AUTO = RiscoCanonico(
    ramo="auto",
    dados={"cep_pernoite": "13010000"},
)
_RISCO_ERRO = RiscoCanonico(
    ramo="auto",
    dados={"cep_pernoite": "00000099"},  # termina em 99 → erro
)
_RISCO_RESTRICAO = RiscoCanonico(
    ramo="auto",
    dados={"cep_pernoite": "00000088"},  # termina em 88 → restrição
)


@pytest.fixture
def fake() -> FakeSeguradora:
    return FakeSeguradora(latencia_min=0, latencia_max=0)


def test_fake_implementa_protocolo(fake: FakeSeguradora) -> None:
    assert isinstance(fake, PortaSeguradora)


def test_capacidades(fake: FakeSeguradora) -> None:
    cap = fake.capacidades()
    assert "auto" in cap.ramos
    assert "residencia" in cap.ramos
    assert len(cap.coberturas) > 0


async def test_cotar_sucesso(fake: FakeSeguradora) -> None:
    resultado = await fake.cotar(_RISCO_AUTO)
    assert resultado.sucesso is True
    assert resultado.cotacao_id is not None
    assert resultado.premio_total is not None
    assert len(resultado.restricoes) == 0
    assert resultado.necessita_vistoria is False


async def test_cotar_erro(fake: FakeSeguradora) -> None:
    resultado = await fake.cotar(_RISCO_ERRO)
    assert resultado.sucesso is False
    assert resultado.cotacao_id is None
    assert resultado.premio_total is None


async def test_cotar_restricao(fake: FakeSeguradora) -> None:
    resultado = await fake.cotar(_RISCO_RESTRICAO)
    assert resultado.sucesso is True
    assert len(resultado.restricoes) > 0
    assert resultado.necessita_vistoria is True


async def test_recotar(fake: FakeSeguradora) -> None:
    resultado = await fake.recotar("cotacao-001", _RISCO_AUTO)
    assert resultado.sucesso is True


async def test_transmitir(fake: FakeSeguradora) -> None:
    from app.adapters.base import PropostaCanonica

    proposta = PropostaCanonica(
        cotacao_id="cotacao-001",
        risco=_RISCO_AUTO,
        dados_negocio={},
    )
    resultado = await fake.transmitir(proposta)
    assert resultado.sucesso is True
    assert resultado.protocolo is not None
    assert resultado.protocolo.startswith("FAKE-")


async def test_movimentos(fake: FakeSeguradora) -> None:
    from datetime import date

    movimentos = await fake.movimentos(date.today())
    assert movimentos == []
