"""HMAC-SHA256 blind index para CPF.

O CPF nunca é persistido em claro. Busca sempre por índice cego.
Troque CPF_HMAC_KEY periodicamente; índices antigos ficam inválidos — planeje a rotação.
"""

import hashlib
import hmac as _hmac

from app.infra.secrets import get_optional_secret


def _key() -> bytes:
    return get_optional_secret(
        "CPF_HMAC_KEY", "dev-only-hmac-key-change-in-prod"
    ).encode()


def cpf_para_idx(cpf_digits: str) -> str:
    """Retorna HMAC-SHA256 hex dos 11 dígitos do CPF."""
    return _hmac.new(_key(), cpf_digits.encode(), hashlib.sha256).hexdigest()
