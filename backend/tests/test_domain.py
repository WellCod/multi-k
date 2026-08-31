"""Testes unitários dos modelos de domínio: eventos, risco e cpf_gen."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.domain import eventos, risco
from app.infra.cpf_gen import _digito, gerar_cpf

# ---------------------------------------------------------------------------
# domain/eventos.py
# ---------------------------------------------------------------------------


def test_cotacao_criada_defaults_preenchidos() -> None:
    ev = eventos.CotacaoCriada(
        cotacao_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        cia="fake",
        risco_json={"ramo": "auto"},
    )
    assert ev.cia == "fake"
    assert ev.id is not None
    assert ev.ocorrido_em is not None


def test_proposta_transmitida_com_protocolo() -> None:
    ev = eventos.PropostaTransmitida(
        cotacao_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        protocolo="PROTO-123",
    )
    assert ev.protocolo == "PROTO-123"


def test_proposta_transmitida_protocolo_nulo() -> None:
    ev = eventos.PropostaTransmitida(
        cotacao_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        protocolo=None,
    )
    assert ev.protocolo is None


def test_apolice_emitida_instancia() -> None:
    ev = eventos.ApoliceEmitida(
        cotacao_id=uuid.uuid4(),
        numero_apolice="APL-001",
        cia="fake",
    )
    assert ev.numero_apolice == "APL-001"
    assert ev.cia == "fake"


def test_endosso_registrado_instancia() -> None:
    ev = eventos.EndossoRegistrado(
        apolice_id=uuid.uuid4(),
        tipo="inclusao",
        descricao="Inclusão de condutor",
    )
    assert ev.tipo == "inclusao"


def test_parcela_gerada_instancia() -> None:
    ev = eventos.ParcelaGerada(
        apolice_id=uuid.uuid4(),
        numero=2,
        vencimento=date.today(),
        valor=Decimal("500.00"),
    )
    assert ev.numero == 2
    assert ev.valor == Decimal("500.00")


def test_comissao_registrada_valor_recebido_opcional() -> None:
    sem = eventos.ComissaoRegistrada(
        apolice_id=uuid.uuid4(), valor_previsto=Decimal("150.00")
    )
    assert sem.valor_recebido is None
    com = eventos.ComissaoRegistrada(
        apolice_id=uuid.uuid4(),
        valor_previsto=Decimal("150.00"),
        valor_recebido=Decimal("120.00"),
    )
    assert com.valor_recebido == Decimal("120.00")


def test_sinistro_aberto_instancia() -> None:
    ev = eventos.SinistroAberto(
        apolice_id=uuid.uuid4(),
        numero_sinistro="SIN-001",
        data_ocorrencia=date.today(),
    )
    assert ev.numero_sinistro == "SIN-001"


# ---------------------------------------------------------------------------
# domain/risco.py
# ---------------------------------------------------------------------------


def test_combustivel_enum_valores() -> None:
    assert risco.Combustivel.GASOLINA == "gasolina"
    assert risco.Combustivel.ELETRICO == "eletrico"
    assert risco.Combustivel.FLEX == "flex"


def test_tipo_imovel_enum_valores() -> None:
    assert risco.TipoImovel.APARTAMENTO == "apartamento"
    assert risco.TipoImovel.CASA == "casa"


def _proponente() -> risco.Proponente:
    return risco.Proponente(
        cpf="12345678901",
        nome="João Silva",
        nascimento=date(1990, 1, 1),
        sexo="M",
        estado_civil="solteiro",
        profissao="engenheiro",
        email="joao@test.com",
        telefone="11999990000",
    )


def _vigencia() -> risco.Vigencia:
    hoje = date.today()
    return risco.Vigencia(inicio=hoje, fim=hoje + timedelta(days=365))


def test_proponente_valido() -> None:
    p = _proponente()
    assert p.cpf == "12345678901"
    assert p.sexo == "M"


def test_vigencia_valida() -> None:
    v = _vigencia()
    assert v.fim > v.inicio


def test_risco_auto_defaults() -> None:
    ra = risco.RiscoAuto(
        proponente=_proponente(),
        vigencia=_vigencia(),
        fipe_codigo="001004-9",
        ano_modelo=2020,
        combustivel=risco.Combustivel.GASOLINA,
        cep_pernoite="13010001",
        km_mes=1000,
        condutor_principal_idade=35,
        coberturas=["compreensiva"],
    )
    assert ra.blindado is False
    assert ra.alienado is False
    assert ra.garagem is True
    assert ra.bonus == 0


def test_risco_residencia_defaults() -> None:
    rr = risco.RiscoResidencia(
        proponente=_proponente(),
        vigencia=_vigencia(),
        tipo=risco.TipoImovel.APARTAMENTO,
        cep="13010001",
        valor_imovel=Decimal("500000.00"),
        coberturas=["incendio"],
    )
    assert rr.alarme is False
    assert rr.valor_conteudo == Decimal("0")


# ---------------------------------------------------------------------------
# infra/cpf_gen.py
# ---------------------------------------------------------------------------


def test_gerar_cpf_formato() -> None:
    cpf = gerar_cpf()
    assert len(cpf) == 11
    assert cpf.isdigit()


def test_gerar_cpf_digitos_verificadores_corretos() -> None:
    cpf = gerar_cpf()
    digits = [int(d) for d in cpf]
    assert _digito(digits[:9], 10) == digits[9]
    assert _digito(digits[:10], 11) == digits[10]


def test_digito_resto_menor_que_2_retorna_zero() -> None:
    base = [0] * 9
    assert _digito(base, 10) == 0
