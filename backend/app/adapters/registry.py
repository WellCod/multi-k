"""Fábrica de adapters — ponto único de registro de seguradoras.

Fica em app/adapters/ (fora do escopo de scan do test_arch.py) para que os
nomes das seguradoras não vazem para o domínio, API ou infra.
"""

from app.adapters.base import PortaSeguradora
from app.adapters.fake.adapter import FakeSeguradora
from app.adapters.justos.adapter import JustosSeguradora
from app.adapters.yelum.adapter import YelumSeguradora
from app.infra.secrets import get_optional_secret


def get_adapter(cia: str) -> PortaSeguradora:
    if cia == "fake":
        return FakeSeguradora()
    if cia == "justos":
        return JustosSeguradora()
    if cia == "yelum":
        return YelumSeguradora()
    raise ValueError(f"Adapter desconhecido: {cia}")


def _yelum_configurado() -> bool:
    return bool(get_optional_secret("YELUM_CLIENT_ID"))


def _justos_configurado() -> bool:
    return bool(get_optional_secret("JUSTOS_PARTNER_NAME"))


def cias_para_ramo(ramo: str) -> list[str]:
    cias: list[str] = []
    if ramo == "auto" and _justos_configurado():
        cias.append("justos")
    if ramo == "imovel" and _yelum_configurado():
        cias.append("yelum")
    if not cias:
        cias.append("fake")
    return cias


def catalogo_seguradoras() -> list[dict[str, object]]:
    """Presentation metadata stays at the integration boundary, not in React."""
    names = {"justos": "Justos", "yelum": "Yelum", "fake": "Simulação"}
    result: list[dict[str, object]] = []
    cias = dict.fromkeys(
        cia for ramo in ("auto", "moto", "imovel") for cia in cias_para_ramo(ramo)
    )
    for cia in cias:
        caps = get_adapter(cia).capacidades()
        modes: list[dict[str, object]] = []
        if cia == "justos":
            modes = [
                {
                    "id": "monthly",
                    "label": "Mensal",
                    "dados_negocio": {"policy_type": "monthly"},
                    "campo_parcelas": None,
                },
                {
                    "id": "annual",
                    "label": "Anual",
                    "dados_negocio": {"policy_type": "annual"},
                    "campo_parcelas": "installments",
                },
            ]
        result.append(
            {
                "id": cia,
                "nome": names.get(cia, cia),
                "logo_url": None,
                "ramos": [ramo for ramo in caps.ramos if cia in cias_para_ramo(ramo)],
                "coberturas": caps.coberturas,
                "franquias": caps.franquias,
                "parcelamentos": caps.parcelamentos,
                "planos": [
                    {
                        "codigo": p,
                        "descricao": "À vista" if p == "AVISTA" else p,
                        "parcelas": 1 if p == "AVISTA" else int(p.removesuffix("X")),
                    }
                    for p in caps.parcelamentos
                ],
                "modos_transmissao": modes,
            }
        )
    return result
