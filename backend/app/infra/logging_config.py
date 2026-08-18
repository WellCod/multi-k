import logging
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog
import structlog.contextvars

ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "event",
        "level",
        "timestamp",
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "usuario_id",
        "papel",
        "cia",
        "cotacao_id",
        "exc_info",
        "stack_info",
        "_record",
    }
)


def allowlist_processor(
    logger: Any, method: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    return {k: v for k, v in event_dict.items() if k in ALLOWED_FIELDS}


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            allowlist_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
