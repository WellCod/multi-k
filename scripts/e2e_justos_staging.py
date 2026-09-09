"""E2E completo contra a API Justos staging.

Fluxo: auth → quote → pricing → coverages → convert-formal-quote → checkout-link

Uso:
    python scripts/e2e_justos_staging.py

Preencha as constantes TEST_* abaixo com um veículo real antes de rodar.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time

import httpx
import jwt  # PyJWT[cryptography]

# ---------------------------------------------------------------------------
# Carrega .env do root do projeto
# ---------------------------------------------------------------------------
_ROOT = pathlib.Path(__file__).parent.parent
_ENV = _ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Dados de teste — substitua por veículo real para staging Justos
# ---------------------------------------------------------------------------
TEST_CPF = os.environ.get("TEST_CPF", "")  # passe via: set TEST_CPF=seucpf && python scripts/e2e_justos_staging.py
TEST_NOME = "João Teste Silva"
TEST_PLACA = "DVK0101"
TEST_FIPE = "024201-2"           # Peugeot 308 CC Roland Garros 1.6 Turbo 2014
TEST_ANO_MODELO = "2014"
TEST_CEP = "01310100"
TEST_EMAIL = "teste@klubi.com.br"
TEST_TELEFONE = "11999990000"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_BASE_STAGING = "https://api.staging.justos.com.br"


def _cfg(key: str) -> str:
    v = os.environ.get(key, "")
    if not v:
        raise RuntimeError(f"Variável de ambiente ausente: {key}")
    return v


def _gerar_jwt() -> str:
    key_path = os.environ.get("JUSTOS_PRIVATE_KEY_PATH", "")
    if key_path:
        pem = pathlib.Path(key_path).read_text()
    else:
        pem = _cfg("JUSTOS_PRIVATE_KEY").replace("\\n", "\n")

    now = int(time.time())
    return str(
        jwt.encode(
            {"iss": _cfg("JUSTOS_PARTNER_NAME"), "aud": "justos", "iat": now, "exp": now + 600},
            pem,
            algorithm="ES256",
        )
    )


def _ok(step: str, data: object) -> None:
    print(f"\n[OK] {step}")
    print(json.dumps(data, indent=2, default=str)[:800])


def _err(step: str, exc: Exception) -> None:
    print(f"\n[ERRO] {step}: {exc}")


async def run() -> None:
    if not TEST_CPF:
        raise RuntimeError(
            "Passe o CPF via env antes de rodar:\n"
            "  set TEST_CPF=seucpf && python scripts/e2e_justos_staging.py"
        )
    broker_id = int(_cfg("JUSTOS_BROKER_ID"))
    cpf_cnpj = _cfg("JUSTOS_CPF_CNPJ")

    async with httpx.AsyncClient(base_url=_BASE_STAGING, timeout=60.0) as c:
        # 1. Auth
        r = await c.post(
            "/brokers/auth/api-token",
            json={"token": _gerar_jwt(), "brokerId": broker_id, "cpf_cnpj": cpf_cnpj},
        )
        r.raise_for_status()
        token = r.json()["token"]
        _ok("Auth", {"token_prefix": token[:40] + "..."})

        headers = {"Authorization": f"Bearer {token}"}

        # 2. Quote
        quote_payload = {
            "plate": TEST_PLACA,
            "chassis": "",
            "insured": {
                "cpf_cnpj": TEST_CPF,
                "legal_name": TEST_NOME,
                "social_name": TEST_NOME.split()[0],
                "cep": TEST_CEP,
                "gender": "M",
                "birth_date": "1990-05-10",
            },
            "vehicle_fipe_code": TEST_FIPE,
            "vehicle_model_year": TEST_ANO_MODELO,
            "vehicle_overnight_cep": TEST_CEP,
            "vehicle_use": "personal",
            "is_zero_km": False,
            "under_24": False,
            "is_insured": False,
            "previous_bonus": "0",
            "broker_commission_percentage": 15,
        }
        r = await c.post("/brokers/quote", json=quote_payload, headers=headers)
        if not r.is_success:
            print(f"[ERRO Quote] {r.status_code}: {r.text}")
        r.raise_for_status()
        quote_resp = r.json()
        quote_id: str = str(quote_resp["quote_id"])
        coverages_available: dict = quote_resp.get("coverages_available", {})
        _ok("Quote criado", {"quote_id": quote_id, "coberturas": list(coverages_available.keys())})

        # Seleciona coberturas (opção mais barata de cada peril disponível)
        _PERILS_CORE = {
            "colisao-e-desastres-naturais", "roubo-e-furto", "incendio",
            "danos-materiais", "danos-corporais",
        }
        tem_mandatory = any(
            p.get("mandatory") for p in coverages_available.values() if p.get("peril_options")
        )
        coverages_selected: dict[str, str | None] = {}
        for slug, peril in coverages_available.items():
            opts = peril.get("peril_options", [])
            if not opts:
                continue
            is_core = slug in _PERILS_CORE
            if peril.get("mandatory") or (not tem_mandatory and is_core):
                cheapest = min(opts, key=lambda o: float(o.get("price", 0)))
                coverages_selected[slug] = str(cheapest["slug"])
            else:
                coverages_selected[slug] = None

        # 3. Pricing
        r = await c.post(
            f"/brokers/quote/{quote_id}/pricing",
            json={"coverages_selected": coverages_selected},
            headers=headers,
        )
        r.raise_for_status()
        pricing = r.json()
        _ok("Pricing", {
            "monthly_total": pricing.get("monthly", {}).get("total"),
            "annual_total": pricing.get("annual", {}).get("total"),
            "info": pricing.get("info", ""),
        })

        # 4. Coverages (PUT)
        r = await c.put(
            f"/brokers/quote/{quote_id}/coverages",
            json={"coverages_selected": coverages_selected, "policy_type": "monthly"},
            headers=headers,
        )
        r.raise_for_status()
        _ok("Coverages selecionadas", {"status": r.status_code})

        # 5. Convert-formal-quote
        r = await c.post(
            "/brokers/quote/convert-formal-quote",
            json={
                "quote_uuid": quote_id,
                "email": TEST_EMAIL,
                "given_phone_number": TEST_TELEFONE,
                "policy_type": "monthly",
                "scheduling_date": None,
            },
            headers=headers,
        )
        if not r.is_success:
            print(f"[ERRO convert-formal-quote] {r.status_code}: {r.text}")
        r.raise_for_status()
        convert_resp = r.json()
        _ok("Convert formal quote", convert_resp)

        # 6. Checkout link
        r = await c.get(
            f"/brokers/quote/{quote_id}/checkout-link",
            headers=headers,
        )
        r.raise_for_status()
        checkout = r.json()
        _ok("Checkout link", checkout)

    print("\n" + "=" * 60)
    print(f"[SUCESSO] E2E COMPLETO -- quote_id={quote_id}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run())
