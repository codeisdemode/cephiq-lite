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

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _ensure_logging()
    return logging.getLogger(name)

