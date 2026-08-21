"""Ponto de entrada da aplicação FastAPI."""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_router import router as auth_router
from app.api.cliente_router import router as cliente_router
from app.api.comparativo_router import router as comparativo_router
from app.api.cotacao_router import router as cotacao_router
from app.api.dominio_router import router as dominio_router
from app.api.fipe_router import router as fipe_router
from app.api.health import router as health_router
from app.api.home_router import router as home_router
from app.api.proposta_router import router as proposta_router
from app.api.relatorio_router import router as relatorio_router
from app.api.renovacao_router import router as renovacao_router
from app.infra.db import AsyncSessionLocal
from app.infra.logging_config import configure_logging
from app.infra.secrets import get_optional_secret
from app.infra.seed import seed_if_empty
from app.infra.seed_demo import criar_demo
from app.infra.worker import start_worker

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        await seed_if_empty(db)
    await criar_demo(AsyncSessionLocal)

    worker_task: asyncio.Task[None] | None = None
    if not get_optional_secret("DISABLE_WORKER", ""):
        worker_task = start_worker(AsyncSessionLocal)

    yield

    if worker_task is not None:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task


app = FastAPI(
    title="multi-K API",
    description="Multicálculo e gestão de seguros",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_cors_origins_raw = get_optional_secret("CORS_ORIGINS", "http://localhost:5173")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Cookie", "X-Request-ID"],
)


@app.middleware("http")
async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


@app.middleware("http")
async def correlation_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(cliente_router)
app.include_router(cotacao_router)
app.include_router(comparativo_router)
app.include_router(proposta_router)
app.include_router(renovacao_router)
app.include_router(dominio_router)
app.include_router(home_router)
app.include_router(relatorio_router)
app.include_router(fipe_router)
