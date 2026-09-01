"""SSE endpoint — notificações em tempo real para o corretor logado."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra import events_bus
from app.infra.db import get_db  # noqa: F401 — side-effect import keeps DI working

router = APIRouter(prefix="/events", tags=["events"])

_KEEPALIVE_INTERVAL = 20  # segundos


@router.get("")
async def stream_events(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Server-Sent Events — envia 'cotacao.pronta' quando cotação finaliza."""
    uid = usuario.id
    _ = db  # sessão fechada após autenticação; SSE não precisa de DB

    async def generate() -> AsyncGenerator[bytes, None]:
        q = events_bus.subscribe(uid)
        try:
            yield b"data: {\"tipo\":\"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_KEEPALIVE_INTERVAL)
                    payload = json.dumps(event, default=str)
                    yield f"data: {payload}\n\n".encode()
                except TimeoutError:
                    yield b": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            events_bus.unsubscribe(uid, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
