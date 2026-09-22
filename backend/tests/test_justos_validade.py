"""Validade da cotação: 30 dias corridos, fim do dia no fuso da seguradora.

Regra confirmada pela Justos em 21/09/2026. Recusamos localmente para não
queimar a tentativa de transmissão e para dar uma mensagem melhor que o erro
genérico deles.
"""

from datetime import UTC, datetime

import pytest

from app.adapters.justos.adapter import _cotacao_vencida

FUSO = "-03:00"


def _em(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def test_cotacao_de_hoje_vale() -> None:
    assert (
        _cotacao_vencida(
            _em(f"2026-09-01T10:00:00{FUSO}"), _em(f"2026-09-01T23:00:00{FUSO}")
        )
        is None
    )


def test_ultimo_instante_do_trigesimo_dia_ainda_vale() -> None:
    """O corte é o fim do dia, não 30x24h."""
    criada = _em(f"2026-09-01T10:00:00{FUSO}")
    assert _cotacao_vencida(criada, _em(f"2026-10-01T23:59:59{FUSO}")) is None


def test_dia_seguinte_ao_limite_e_recusado() -> None:
    criada = _em(f"2026-09-01T10:00:00{FUSO}")
    msg = _cotacao_vencida(criada, _em(f"2026-10-02T00:00:01{FUSO}"))
    assert msg is not None
    assert "01/10/2026" in msg


def test_criada_tarde_em_brasilia_nao_vence_cedo_demais() -> None:
    """23h30 em Brasília é o dia seguinte em UTC.

    Contar o prazo sobre a data UTC encurtaria a validade em um dia inteiro
    para toda cotação feita no fim da noite.
    """
    criada = _em("2026-09-01T23:30:00-03:00")
    assert criada.astimezone(UTC).date().isoformat() == "2026-09-02"
    # Vale até o fim de 01/10 no horário de Brasília, não até 02/10.
    assert _cotacao_vencida(criada, _em(f"2026-10-01T22:00:00{FUSO}")) is None
    assert _cotacao_vencida(criada, _em(f"2026-10-02T00:30:00{FUSO}")) is not None


def test_aceita_string_iso() -> None:
    assert (
        _cotacao_vencida(
            f"2026-09-01T10:00:00{FUSO}", _em(f"2026-12-01T10:00:00{FUSO}")
        )
        is not None
    )


def test_sem_data_nao_bloqueia() -> None:
    """Ausência de data não é motivo para recusar uma transmissão legítima."""
    assert _cotacao_vencida(None) is None


@pytest.mark.parametrize("lixo", ["ontem", "", "2026-13-45"])
def test_data_ilegivel_nao_bloqueia(lixo: str) -> None:
    assert _cotacao_vencida(lixo) is None


def test_datetime_ingenuo_e_tratado_como_utc() -> None:
    criada = datetime(2026, 9, 1, 13, 0, 0)
    assert _cotacao_vencida(criada, _em(f"2026-12-01T10:00:00{FUSO}")) is not None
