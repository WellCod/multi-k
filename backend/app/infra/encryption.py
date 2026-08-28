"""AES-256-GCM transparent encryption for SQLAlchemy columns."""

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.infra.secrets import get_optional_secret


def _key() -> bytes:
    raw = get_optional_secret("PAYLOAD_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "PAYLOAD_ENCRYPTION_KEY não definida. "
            'Gere: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    key_bytes = bytes.fromhex(raw)
    if len(key_bytes) != 32:
        raise ValueError("PAYLOAD_ENCRYPTION_KEY deve ser hex de 32 bytes (64 chars)")
    return key_bytes


class EncryptedJSON(TypeDecorator[Any]):
    """Armazena dict/list como AES-256-GCM ciphertext em coluna TEXT.

    Formato no banco: base64(nonce[12] + ciphertext+tag)
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        plaintext = json.dumps(value, ensure_ascii=False).encode()
        nonce = os.urandom(12)
        ciphertext = AESGCM(_key()).encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode()

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        raw = base64.b64decode(value.encode())
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(_key()).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)
