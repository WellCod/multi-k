"""O stream de eventos precisa terminar quando a aplicação desliga.

Sem isso o desligamento gracioso espera para sempre: o uvicorn aguarda as
respostas em curso e um gerador SSE infinito nunca termina. Foi o que travou
a API em desenvolvimento ao recarregar com um stream aberto.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest

from app.api import events_router
from app.api.events_router import gerar_eventos
from app.infra import events_bus


@pytest.fixture(autouse=True)
def _sem_parada_pendente() -> AsyncGenerator[None, None]:
    events_bus.limpar_parada()
    yield
    events_bus.limpar_parada()


async def _proximo(fluxo: AsyncGenerator[bytes, None]) -> bytes:
    """Nunca espera para sempre: regressão vira falha, não suíte pendurada."""
    return await asyncio.wait_for(anext(fluxo), timeout=5)


async def test_stream_encerra_quando_a_aplicacao_desliga() -> None:
    fluxo = gerar_eventos(uuid.uuid4())
    assert b"connected" in await _proximo(fluxo)

    events_bus.sinalizar_parada()

    assert b"encerrando" in await _proximo(fluxo)
    with pytest.raises(StopAsyncIteration):
        await _proximo(fluxo)


async def test_stream_nem_comeca_durante_o_desligamento() -> None:
    events_bus.sinalizar_parada()
    fluxo = gerar_eventos(uuid.uuid4())
    with pytest.raises(StopAsyncIteration):
        await _proximo(fluxo)


async def test_evento_publicado_chega_ao_fluxo() -> None:
    uid = uuid.uuid4()
    fluxo = gerar_eventos(uid)
    await _proximo(fluxo)  # connected cria a assinatura

    events_bus.publish(uid, {"tipo": "cotacao.pronta", "status": "sucesso"})

    recebido = await _proximo(fluxo)
    assert b"cotacao.pronta" in recebido
    await fluxo.aclose()


async def test_eventos_seguidos_nao_se_perdem() -> None:
    """O get() pendente atravessa as iterações justamente para não perder."""
    uid = uuid.uuid4()
    fluxo = gerar_eventos(uid)
    await _proximo(fluxo)

    events_bus.publish(uid, {"tipo": "primeiro"})
    events_bus.publish(uid, {"tipo": "segundo"})

    assert b"primeiro" in await _proximo(fluxo)
    assert b"segundo" in await _proximo(fluxo)
    await fluxo.aclose()


async def test_keepalive_sai_quando_nao_ha_evento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(events_router, "_KEEPALIVE_INTERVAL", 0.05)
    fluxo = gerar_eventos(uuid.uuid4())
    await _proximo(fluxo)

    assert b"keepalive" in await _proximo(fluxo)
    await fluxo.aclose()


async def test_assinatura_e_desfeita_ao_fechar() -> None:
    uid = uuid.uuid4()
    fluxo = gerar_eventos(uid)
    await _proximo(fluxo)
    assert uid in events_bus._subscribers

    await fluxo.aclose()

    assert uid not in events_bus._subscribers
