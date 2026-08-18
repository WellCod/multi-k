"""
Garante que PII nunca chega ao sink de log.
O processador allowlist_processor remove campos não autorizados antes
do render — este teste valida isso diretamente, sem depender de postgres.
"""

from typing import Any

from app.infra.logging_config import ALLOWED_FIELDS, allowlist_processor

_FORBIDDEN = {"cpf", "password", "client_secret", "access_token", "senha"}


def _processar(event_dict: dict[str, Any]) -> dict[str, Any]:
    return allowlist_processor(None, "info", event_dict)


def test_campos_permitidos_passam() -> None:
    entrada = {
        "event": "cotacao.criada",
        "level": "info",
        "usuario_id": "abc-123",
        "cotacao_id": "xyz",
    }
    saida = _processar(entrada)
    assert saida == entrada


def test_pii_removido() -> None:
    entrada = {
        "event": "teste",
        "cpf": "12345678901",
        "password": "s3cr3t",
        "client_secret": "tok",
        "access_token": "bearer-xxx",
        "senha": "abc",
    }
    saida = _processar(entrada)
    for campo in _FORBIDDEN:
        assert campo not in saida, f"{campo!r} não deve aparecer no log"
    assert "event" in saida


def test_campo_desconhecido_removido() -> None:
    entrada = {"event": "ok", "campo_qualquer": "valor", "level": "info"}
    saida = _processar(entrada)
    assert "campo_qualquer" not in saida


def test_todos_campos_permitidos_em_allowed_fields() -> None:
    campos_esperados = {
        "event",
        "level",
        "timestamp",
        "request_id",
        "usuario_id",
        "cotacao_id",
    }
    assert campos_esperados.issubset(ALLOWED_FIELDS)


def test_pii_nao_esta_em_allowed_fields() -> None:
    for campo in _FORBIDDEN:
        assert campo not in ALLOWED_FIELDS, (
            f"{campo!r} não deveria estar em ALLOWED_FIELDS"
        )
