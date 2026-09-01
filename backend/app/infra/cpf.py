"""HMAC-SHA256 blind index para CPF com versionamento de chave.

O CPF nunca é persistido em claro. Busca sempre por índice cego.
Formato armazenado: "v1:{hex64}" — a versão permite rotação futura de chave.
Ao trocar CPF_HMAC_KEY: recalcule os índices existentes em background e
remova os registros com prefixo antigo após migração completa.
"""

import hashlib
import hmac as _hmac

from app.infra.secrets import get_optional_secret

_CURRENT_VERSION = "v1"


def _key() -> bytes:
    key = get_optional_secret("CPF_HMAC_KEY", "")
    if not key:
        raise RuntimeError(
            "CPF_HMAC_KEY não definida. "
            'Gere: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return key.encode()


def cpf_para_idx(cpf_digits: str) -> str:
    """Retorna versioned HMAC-SHA256 hex: 'v1:{hex64}'."""
    digest = _hmac.new(_key(), cpf_digits.encode(), hashlib.sha256).hexdigest()
    return f"{_CURRENT_VERSION}:{digest}"


def cpf_idx_match(stored: str, cpf_digits: str) -> bool:
    """Compara índice armazenado (com ou sem prefixo de versão) com CPF em claro.

    Suporta índices legados sem prefixo durante migração.
    """
    computed = cpf_para_idx(cpf_digits)
    if _hmac.compare_digest(stored, computed):
        return True
    # fallback: índice legado sem prefixo (migração)
    digest_only = computed.split(":", 1)[1]
    return _hmac.compare_digest(stored, digest_only)
