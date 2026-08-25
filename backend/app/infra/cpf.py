"""HMAC-SHA256 blind index para CPF.

O CPF nunca é persistido em claro. Busca sempre por índice cego.
Troque CPF_HMAC_KEY periodicamente; índices antigos ficam inválidos — planeje a rotação.
"""

import hashlib
import hmac as _hmac
import logging

from app.infra.secrets import get_optional_secret

_log = logging.getLogger(__name__)

_DEV_KEY = "dev-only-hmac-key-change-in-prod"  # noqa: S105


def _key() -> bytes:
    key = get_optional_secret("CPF_HMAC_KEY", "")
    if not key:
        debug = get_optional_secret("DEBUG", "false").lower() in ("true", "1", "yes")
        if not debug:
            raise RuntimeError(
                "CPF_HMAC_KEY obrigatório em produção. "
                'Gere: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        _log.warning("cpf_hmac_key_not_set: chave dev-only em uso; defina CPF_HMAC_KEY")
        key = _DEV_KEY
    return key.encode()


def cpf_para_idx(cpf_digits: str) -> str:
    """Retorna HMAC-SHA256 hex dos 11 dígitos do CPF."""
    return _hmac.new(_key(), cpf_digits.encode(), hashlib.sha256).hexdigest()
