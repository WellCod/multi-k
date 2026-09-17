"""In-process pub/sub via asyncio.Queue.

Single-process only — adequate for single-uvicorn-worker deployments.
Multi-worker or multi-process requires a Redis pub/sub layer.
"""

import asyncio
import contextlib
import uuid
from collections import defaultdict
from typing import Any

_subscribers: dict[uuid.UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

# O desligamento gracioso espera as respostas terminarem, e um stream SSE não
# termina sozinho. Este sinal avisa os streams abertos para encerrarem.
_parada = asyncio.Event()


def sinalizar_parada() -> None:
    """Pede que os streams abertos se encerrem — chamado no shutdown."""
    _parada.set()


def limpar_parada() -> None:
    """Reabre para novos streams (uso em teste e em reinício no mesmo processo)."""
    _parada.clear()


def parando() -> bool:
    return _parada.is_set()


async def aguardar_parada() -> None:
    await _parada.wait()


def subscribe(usuario_id: uuid.UUID) -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50)
    _subscribers[usuario_id].add(q)
    return q


def unsubscribe(usuario_id: uuid.UUID, q: asyncio.Queue[dict[str, Any]]) -> None:
    _subscribers[usuario_id].discard(q)
    if not _subscribers[usuario_id]:
        del _subscribers[usuario_id]


def publish(usuario_id: uuid.UUID, event: dict[str, Any]) -> None:
    for q in list(_subscribers.get(usuario_id, [])):
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(event)
