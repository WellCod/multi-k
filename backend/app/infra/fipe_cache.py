"""Cache em memória para dados da Tabela FIPE.

TTL de 30 dias — FIPE atualiza mensalmente. Thread-safe via threading.Lock.
Reiniciar o processo descarta o cache; aceitável no MVP.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

TTL = 30 * 24 * 3600  # 30 dias em segundos
MAX_SIZE = 1_000  # evita crescimento ilimitado

_lock = threading.Lock()


@dataclass
class _Entry:
    data: list[dict[str, str]]
    expira_em: float = field(default_factory=lambda: time.monotonic() + TTL)


_cache: OrderedDict[str, _Entry] = OrderedDict()


def get(chave: str) -> list[dict[str, str]] | None:
    with _lock:
        entry = _cache.get(chave)
        if entry is None:
            return None
        if time.monotonic() > entry.expira_em:
            del _cache[chave]
            return None
        _cache.move_to_end(chave)  # LRU: promove para o fim
        return entry.data


def set(chave: str, data: list[dict[str, str]]) -> None:
    with _lock:
        if chave in _cache:
            _cache.move_to_end(chave)
        _cache[chave] = _Entry(data=data)
        while len(_cache) > MAX_SIZE:
            _cache.popitem(last=False)  # remove o mais antigo (LRU)
