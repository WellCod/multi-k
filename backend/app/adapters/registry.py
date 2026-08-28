"""Fábrica de adapters — ponto único de registro de seguradoras.

Fica em app/adapters/ (fora do escopo de scan do test_arch.py) para que os
nomes das seguradoras não vazem para o domínio, API ou infra.
"""

from app.adapters.base import PortaSeguradora
from app.adapters.fake.adapter import FakeSeguradora
from app.adapters.justos.adapter import JustosSeguradora
from app.adapters.yelum.adapter import YelumSeguradora


def get_adapter(cia: str) -> PortaSeguradora:
    if cia == "fake":
        return FakeSeguradora()
    if cia == "justos":
        return JustosSeguradora()
    if cia == "yelum":
        return YelumSeguradora()
    raise ValueError(f"Adapter desconhecido: {cia}")
