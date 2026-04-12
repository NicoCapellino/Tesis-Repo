"""
Structured logging configuration for the pipeline.

Uses ``structlog`` to produce human-readable logs in development and
JSON-structured logs when the ``NYC_PIPELINE_LOG_JSON`` env var is set.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(*, json_output: bool = False, level: int = logging.INFO) -> None:
    """Configure structured logging for the entire application.

    Args:
        json_output: If ``True``, emit logs as JSON lines (useful for
            production / log aggregation). Defaults to human-readable.
        level: Minimum log level.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with the given name.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.
    """
    return structlog.get_logger(name)
