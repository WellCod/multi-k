"""SSE endpoint — notificações em tempo real para o corretor logado."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.infra import events_bus
from app.infra.db import get_db  # noqa: F401 — side-effect import keeps DI working

router = APIRouter(prefix="/events", tags=["events"])

_KEEPALIVE_INTERVAL = 20  # segundos


async def gerar_eventos(uid: uuid.UUID) -> AsyncGenerator[bytes, None]:
    """Fluxo SSE do usuário, encerrado pelo sinal de parada da aplicação.

    Sem esse sinal o gerador nunca termina, e o desligamento gracioso — que
    espera as respostas em curso — fica preso indefinidamente.
    """
    q = events_bus.subscribe(uid)
    # asyncio.wait exige um tipo só; o resultado de cada uma é lido à parte.
    parada: asyncio.Future[Any] = asyncio.ensure_future(events_bus.aguardar_parada())
    # A espera pela fila atravessa as iterações: cancelar um get() que já
    # recebeu o item perderia o evento.
    proximo: asyncio.Future[Any] = asyncio.ensure_future(q.get())
    try:
        if events_bus.parando():
            return
        yield b'data: {"tipo":"connected"}\n\n'
        while True:
            done, _pendentes = await asyncio.wait(
                {proximo, parada},
                timeout=_KEEPALIVE_INTERVAL,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if parada in done:
                # Avisa o cliente para reconectar, em vez de sumir calado.
                yield b'data: {"tipo":"encerrando"}\n\n'
                return
            if proximo in done:
                payload = json.dumps(proximo.result(), default=str)
                yield f"data: {payload}\n\n".encode()
                proximo = asyncio.ensure_future(q.get())
            else:
                yield b": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        for tarefa in (proximo, parada):
            tarefa.cancel()
        events_bus.unsubscribe(uid, q)


@router.get("")
async def stream_events(
    usuario: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Server-Sent Events — envia 'cotacao.pronta' quando cotação finaliza."""
    _ = db  # sessão fechada após autenticação; SSE não precisa de DB
    return StreamingResponse(
        gerar_eventos(usuario.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
