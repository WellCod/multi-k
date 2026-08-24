"""Proxy para a Tabela FIPE com cache em memória de 30 dias.

Fonte: Parallelum — https://parallelum.com.br/fipe/api/v1/
(BrasilAPI só tem /marcas e usa campo "valor" em vez de "codigo" — inconsistente.)

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

_PARALLELUM = "https://parallelum.com.br/fipe/api/v1"
_TIPO = {"carros": "carros", "motos": "motos", "caminhoes": "caminhoes"}
_TIMEOUT = httpx.Timeout(15.0)


async def _get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_PARALLELUM}{path}")
        r.raise_for_status()
        return r.json()


def _norm(items: list[Any]) -> list[dict[str, str]]:
    return [
        {"codigo": str(m.get("codigo", "")), "nome": str(m.get("nome", ""))}
        for m in items
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
        raw = await _get(f"/{_TIPO[tipo]}/marcas")
    except Exception as exc:
        raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    data = _norm(raw)
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
        raw = await _get(f"/{_TIPO[tipo]}/marcas/{marca_id}/modelos")
        items: list[Any] = raw if isinstance(raw, list) else raw.get("modelos", [])
    except Exception as exc:
        raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    data = _norm(items)
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
        raw = await _get(f"/{_TIPO[tipo]}/marcas/{marca_id}/modelos/{modelo_id}/anos")
    except Exception as exc:
        raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    data = _norm(raw)
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
        item: dict[str, Any] = await _get(
            f"/{_TIPO[tipo]}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
        )
    except Exception as exc:
        raise HTTPException(502, f"FIPE indisponível: {exc}") from exc

    # Parallelum usa PascalCase: CodigoFipe, Valor, Marca, Modelo, AnoModelo, etc.
    result = {
        "codigo_fipe": str(item.get("CodigoFipe", "")),
        "marca": str(item.get("Marca", "")),
        "modelo": str(item.get("Modelo", "")),
        "ano_modelo": str(item.get("AnoModelo", "")),
        "combustivel": str(item.get("Combustivel", "")),
        "valor": str(item.get("Valor", "")),
        "mes_referencia": str(item.get("MesReferencia", "")),
    }

    fipe_cache.set(chave, [result])
    return result
