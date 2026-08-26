"""Sliding-window rate limiter em memória.

Sem dependência externa. Adequado para MVP de baixo volume.
Não sobrevive a múltiplos processos — para produção distribuída usar Redis + lua script.
"""

import asyncio
import time
from collections import defaultdict

_counters: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


async def allow(key: str, max_requests: int = 60, window_seconds: float = 60.0) -> bool:
    """Retorna True se a requisição é permitida, False se o limite foi atingido."""
    now = time.monotonic()
    cutoff = now - window_seconds
    async with _lock:
        _counters[key] = [t for t in _counters[key] if t > cutoff]
        if len(_counters[key]) >= max_requests:
            return False
        _counters[key].append(now)
        return True
