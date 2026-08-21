"""Proxy para a Tabela FIPE com cache em memória de 30 dias.

Fonte primária: BrasilAPI  — https://brasilapi.com.br/api/fipe/tabelas/v1
Fallback:       Parallelum — https://parallelum.com.br/fipe/api/v1/

Rotas públicas (sem autenticação):
  GET /fipe/marcas?tipo=carros|motos
  GET /fipe/modelos?tipo=carros&marca_id={codigo}
  GET /fipe/anos?tipo=carros&marca_id={codigo}&modelo_id={codigo}
  GET /fipe/preco?tipo=carros&marca_id={m}&modelo_id={m}&ano_id={a}
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.infra import fipe_cache

router = APIRouter(prefix="/fipe", tags=["fipe"])

_BRASIL_API = "https://brasilapi.com.br/api/fipe"
_PARALLELUM = "https://parallelum.com.br/fipe/api/v1"

_TIPO_PARALLELUM = {"carros": "carros", "motos": "motos", "caminhoes": "caminhoes"}

_TIMEOUT = httpx.Timeout(15.0)


async def _get_brasil_api(path: str) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_BRASIL_API}{path}")
        r.raise_for_status()
        return r.json()


async def _get_parallelum(path: str) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_PARALLELUM}{path}")
        r.raise_for_status()
        return r.json()


def _normalizar_marcas_brasil(raw: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"codigo": str(m.get("codigo", "")), "nome": str(m.get("nome", ""))}
        for m in raw
    ]


def _normalizar_marcas_parallelum(raw: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"codigo": str(m.get("codigo", "")), "nome": str(m.get("nome", ""))}
        for m in raw
    ]


@router.get("/marcas")
async def marcas(
    tipo: str = Query(default="carros", pattern="^(carros|motos|caminhoes)$"),
) -> list[dict[str, str]]:
    chave = f"marcas:{tipo}"
    cached = fipe_cache.get(chave)
    if cached is not None:
        return cached

    try:
        raw = await _get_brasil_api(f"/marcas/v1?tipoVeiculo={tipo}")
        data = _normalizar_marcas_brasil(raw)
    except Exception:
        try:
            raw = await _get_parallelum(f"/{_TIPO_PARALLELUM[tipo]}/marcas")
            data = _normalizar_marcas_parallelum(raw)
        except Exception as exc:
            raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    fipe_cache.set(chave, data)
    return data


@router.get("/modelos")
async def modelos(
    tipo: str = Query(default="carros", pattern="^(carros|motos|caminhoes)$"),
    marca_id: str = Query(),
) -> list[dict[str, str]]:
    chave = f"modelos:{tipo}:{marca_id}"
    cached = fipe_cache.get(chave)
    if cached is not None:
        return cached

    try:
        raw = await _get_brasil_api(
            f"/modelos/v1?tipoVeiculo={tipo}&codigoMarca={marca_id}"
        )
        raw_modelos: list[dict[str, str]] = (
            raw if isinstance(raw, list) else raw.get("modelos", [])
        )
        data = [
            {"codigo": str(m.get("codigo", "")), "nome": str(m.get("nome", ""))}
            for m in raw_modelos
        ]
    except Exception:
        try:
            raw2 = await _get_parallelum(
                f"/{_TIPO_PARALLELUM[tipo]}/marcas/{marca_id}/modelos"
            )
            modelos_list: list[dict[str, str]] = (
                raw2 if isinstance(raw2, list) else raw2.get("modelos", [])
            )
            data = [
                {"codigo": str(m.get("codigo", "")), "nome": str(m.get("nome", ""))}
                for m in modelos_list
            ]
        except Exception as exc:
            raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    fipe_cache.set(chave, data)
    return data


@router.get("/anos")
async def anos(
    tipo: str = Query(default="carros", pattern="^(carros|motos|caminhoes)$"),
    marca_id: str = Query(),
    modelo_id: str = Query(),
) -> list[dict[str, str]]:
    chave = f"anos:{tipo}:{marca_id}:{modelo_id}"
    cached = fipe_cache.get(chave)
    if cached is not None:
        return cached

    try:
        raw = await _get_brasil_api(
            f"/anos/v1?tipoVeiculo={tipo}&codigoMarca={marca_id}&codigoModelo={modelo_id}"
        )
        data = [
            {"codigo": str(a.get("codigo", "")), "nome": str(a.get("nome", ""))}
            for a in raw
        ]
    except Exception:
        try:
            raw2 = await _get_parallelum(
                f"/{_TIPO_PARALLELUM[tipo]}/marcas/{marca_id}/modelos/{modelo_id}/anos"
            )
            data = [
                {"codigo": str(a.get("codigo", "")), "nome": str(a.get("nome", ""))}
                for a in raw2
            ]
        except Exception as exc:
            raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    fipe_cache.set(chave, data)
    return data


@router.get("/preco")
async def preco(
    tipo: str = Query(default="carros", pattern="^(carros|motos|caminhoes)$"),
    marca_id: str = Query(),
    modelo_id: str = Query(),
    ano_id: str = Query(),
) -> dict[str, str]:
    chave = f"preco:{tipo}:{marca_id}:{modelo_id}:{ano_id}"
    cached = fipe_cache.get(chave)
    if cached is not None:
        return cached[0] if cached else {}

    try:
        raw = await _get_brasil_api(
            f"/preco/v1?tipoVeiculo={tipo}&codigoMarca={marca_id}"
            f"&codigoModelo={modelo_id}&anoModelo={ano_id}"
        )
        item: dict[str, str] = raw[0] if isinstance(raw, list) else raw
    except Exception:
        try:
            item = await _get_parallelum(
                f"/{_TIPO_PARALLELUM[tipo]}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
            )
        except Exception as exc:
            raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    result = {
        "codigo_fipe": str(item.get("codigoFipe", item.get("codigo_fipe", ""))),
        "marca": str(item.get("marca", "")),
        "modelo": str(item.get("modelo", item.get("name", ""))),
        "ano_modelo": str(item.get("anoModelo", item.get("ano_modelo", ""))),
        "combustivel": str(item.get("combustivel", item.get("fuel", ""))),
        "valor": str(item.get("valor", item.get("price", ""))),
        "mes_referencia": str(
            item.get("mesReferencia", item.get("mes_referencia", ""))
        ),
    }

    fipe_cache.set(chave, [result])
    return result
