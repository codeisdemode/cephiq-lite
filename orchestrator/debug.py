from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os


_CONFIGURED = False


def _ensure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = Path(__file__).resolve().parent.parent  # docs/
    log_path = root / "debug.log"
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear any existing handlers to prevent duplicates
    logger.handlers.clear()

    # File handler (rotating)
    fh = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler (info+)
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Suppress verbose HTTP client logging to prevent reentrancy issues
    # These libraries generate excessive debug logs that cause file locking conflicts
    http_loggers = ["httpx", "httpcore", "anthropic"]
    for lib_name in http_loggers:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(logging.WARNING)  # Only show warnings and errors
        lib_logger.propagate = False  # Prevent propagation to root logger

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _ensure_logging()
    return logging.getLogger(name)

