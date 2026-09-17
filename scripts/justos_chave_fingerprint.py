"""Imprime a impressão digital da chave Justos configurada.

Serve para conferir com a seguradora *qual* chave está cadastrada de cada
lado, sem trocar arquivo: a impressão digital identifica o par sem revelar
a chave privada. Útil antes de subir para produção, onde o par precisa ser
distinto do usado em staging.

Uso:
    cd backend && python ../scripts/justos_chave_fingerprint.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from app.adapters.justos import client  # noqa: E402
from app.infra.secrets import EnvSecretProvider, get_optional_secret, set_provider  # noqa: E402


def _pem_privado() -> str:
    caminho = get_optional_secret("JUSTOS_PRIVATE_KEY_PATH")
    if caminho:
        return pathlib.Path(caminho).read_text()
    inline = get_optional_secret("JUSTOS_PRIVATE_KEY", "")
    if not inline:
        raise SystemExit(
            "Nenhuma chave configurada: defina JUSTOS_PRIVATE_KEY_PATH (dev) "
            "ou JUSTOS_PRIVATE_KEY (produção)."
        )
    return inline.replace("\n", "\n")


def main() -> None:
    set_provider(EnvSecretProvider())
    try:
        ambiente = client.ambiente()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    privada = serialization.load_pem_private_key(_pem_privado().encode(), password=None)
    publica = privada.public_key()
    spki = publica.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(spki).hexdigest()
    impressao = ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))

    origem = (
        "arquivo (JUSTOS_PRIVATE_KEY_PATH)"
        if get_optional_secret("JUSTOS_PRIVATE_KEY_PATH")
        else "segredo inline (JUSTOS_PRIVATE_KEY)"
    )
    print(f"ambiente        : {ambiente}")
    print(f"origem da chave : {origem}")
    print(f"curva           : {privada.curve.name}")
    print(f"SHA-256 (SPKI)  : {impressao}")
    print()
    print("Chave pública correspondente:")
    print(
        publica.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
    )


if __name__ == "__main__":
    main()
