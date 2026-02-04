from __future__ import annotations

import logging
from logging.config import dictConfig

from asgi_correlation_id.context import correlation_id
from pythonjsonlogger import jsonlogger


class CorrelationIdFilter(logging.Filter):
    """Attach the current request correlation ID to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "unknown"
        return True


def configure_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"with_correlation": {"()": CorrelationIdFilter}},
            "formatters": {
                "json": {
                    "()": jsonlogger.JsonFormatter,
                    "fmt": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "%(message)s %(correlation_id)s"
                    ),
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["with_correlation"],
                }
            },
            "root": {"handlers": ["default"], "level": level},
            "loggers": {
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": level,
                    "propagate": False,
                },
            },
        }
    )
