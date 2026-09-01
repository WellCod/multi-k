"""In-process pub/sub via asyncio.Queue.

Single-process only — adequate for single-uvicorn-worker deployments.
Multi-worker or multi-process requires a Redis pub/sub layer.
"""

import asyncio
import contextlib
import uuid
from collections import defaultdict

_subscribers: dict[uuid.UUID, set[asyncio.Queue[dict]]] = defaultdict(set)


def subscribe(usuario_id: uuid.UUID) -> asyncio.Queue[dict]:
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
    _subscribers[usuario_id].add(q)
    return q


def unsubscribe(usuario_id: uuid.UUID, q: asyncio.Queue[dict]) -> None:
    _subscribers[usuario_id].discard(q)
    if not _subscribers[usuario_id]:
        del _subscribers[usuario_id]


def publish(usuario_id: uuid.UUID, event: dict) -> None:
    for q in list(_subscribers.get(usuario_id, [])):
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(event)


