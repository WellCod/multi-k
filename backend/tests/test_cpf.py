"""Testes para infra/cpf.py — HMAC-SHA256 blind index com versionamento."""

import pytest

from app.infra.cpf import cpf_idx_match, cpf_para_idx


def test_mesmo_cpf_mesmo_hash() -> None:
    assert cpf_para_idx("12345678901") == cpf_para_idx("12345678901")


def test_cpfs_diferentes_hashes_diferentes() -> None:
    assert cpf_para_idx("12345678901") != cpf_para_idx("98765432100")


def test_hash_tem_prefixo_v1() -> None:
    resultado = cpf_para_idx("12345678901")
    assert resultado.startswith("v1:")
    hex_part = resultado[3:]
    assert len(hex_part) == 64
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_idx_match_com_prefixo() -> None:
    idx = cpf_para_idx("12345678901")
    assert cpf_idx_match(idx, "12345678901") is True
    assert cpf_idx_match(idx, "98765432100") is False


def test_idx_match_legado_sem_prefixo() -> None:
    import hashlib
    import hmac as _hmac

    import app.infra.cpf as cpf_mod

    key = cpf_mod._key()
    legacy = _hmac.new(key, b"12345678901", hashlib.sha256).hexdigest()
    assert cpf_idx_match(legacy, "12345678901") is True


def test_cpf_key_ausente_levanta_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.infra.cpf as cpf_mod

    def _raise() -> bytes:
        raise RuntimeError("CPF_HMAC_KEY não definida.")

    monkeypatch.setattr(cpf_mod, "_key", _raise)
    with pytest.raises(RuntimeError, match="CPF_HMAC_KEY"):
        cpf_mod._key()
