"""Testes unitários do registry de adapters."""

import pytest

from app.adapters.fake.adapter import FakeSeguradora
from app.adapters.justos.adapter import JustosSeguradora
from app.adapters.registry import cias_para_ramo, get_adapter
from app.adapters.yelum.adapter import YelumSeguradora


def test_get_adapter_fake() -> None:
    assert isinstance(get_adapter("fake"), FakeSeguradora)


def test_get_adapter_justos() -> None:
    assert isinstance(get_adapter("justos"), JustosSeguradora)


def test_get_adapter_yelum() -> None:
    assert isinstance(get_adapter("yelum"), YelumSeguradora)


def test_get_adapter_desconhecido_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="Adapter desconhecido"):
        get_adapter("naoexiste")


def test_cias_para_ramo_sem_credenciais_retorna_apenas_fake() -> None:
    """Sem variáveis de ambiente configuradas apenas 'fake' deve ser retornado."""
    cias = cias_para_ramo("auto")
    assert cias == ["fake"] or "fake" in cias


def test_cias_para_ramo_auto_com_justos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com JUSTOS_PARTNER_NAME definido, 'justos' deve aparecer para ramo auto."""
    monkeypatch.setenv("JUSTOS_PARTNER_NAME", "corretor-teste")
    cias = cias_para_ramo("auto")
    assert "fake" in cias
    assert "justos" in cias


def test_cias_para_ramo_imovel_com_yelum(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com YELUM_CLIENT_ID definido, 'yelum' deve aparecer para ramo imovel."""
    monkeypatch.setenv("YELUM_CLIENT_ID", "client-id-teste")
    cias = cias_para_ramo("imovel")
    assert "fake" in cias
    assert "yelum" in cias


def test_cias_para_ramo_imovel_sem_yelum_nao_inclui_yelum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YELUM_CLIENT_ID", raising=False)
    cias = cias_para_ramo("imovel")
    assert "yelum" not in cias
