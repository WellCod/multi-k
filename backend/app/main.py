"""Ponto de entrada da aplicação FastAPI."""

import asyncio
import contextlib
import secrets
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.auditoria_router import router as auditoria_router
from app.api.auth_router import router as auth_router
from app.api.events_router import router as events_router
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
_debug = get_optional_secret("DEBUG", "false").lower() in ("true", "1", "yes")
if "*" in _cors_origins and not _debug:
    raise RuntimeError(
        "CORS_ORIGINS contém '*' em produção — defina origens explícitas."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Cookie", "X-Request-ID", "X-CSRF-Token"],
)


_CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_CSRF_EXEMPT_PATHS = frozenset({"/auth/login", "/auth/logout"})
_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


@app.middleware("http")
async def body_size_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                return Response(
                    content='{"detail":"Request body muito grande (máx 10 MB)."}',
                    status_code=413,
                    media_type="application/json",
                )
        except ValueError:
            pass
    return await call_next(request)


@app.middleware("http")
async def csrf_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if (
        request.method not in _CSRF_SAFE_METHODS
        and request.url.path not in _CSRF_EXEMPT_PATHS
        and request.cookies.get("sid")  # só requisições autenticadas
    ):
        csrf_cookie = request.cookies.get("csrf_token", "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_header):
            return Response(
                content='{"detail":"CSRF token inválido ou ausente."}',
                status_code=403,
                media_type="application/json",
            )
    return await call_next(request)


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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
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
app.include_router(auditoria_router)
app.include_router(events_router)
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
