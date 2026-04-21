"""
Centralized logging configuration.

Log files written to:
  logs/app.log       — all INFO+ messages from every module
  logs/errors.log    — ERROR+ only (quick error review)
  logs/agents.log    — agent poll activity only

Rotation: 10 MB per file, keep 7 backups → max ~70 MB per log type.
Format:   2024-01-15 14:32:01,234 | INFO | app.agents.youtube | message

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()   # call once at startup (main.py / scheduler.py)
"""

import logging
import logging.handlers
from pathlib import Path


LOG_DIR = Path("logs")

LOG_FORMAT    = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT   = "%Y-%m-%d %H:%M:%S"
MAX_BYTES     = 10 * 1024 * 1024   # 10 MB
BACKUP_COUNT  = 7


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the entire application.
    Call once at FastAPI startup — safe to call multiple times.
    """
    LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter     = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Root logger ───────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Clear any handlers already added (e.g. by basicConfig)
    if root.handlers:
        root.handlers.clear()

    # ── Console (stdout) ──────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # ── logs/app.log — everything INFO+ ───────────────────────────────────
    app_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(formatter)
    root.addHandler(app_handler)

    # ── logs/errors.log — ERROR+ only ─────────────────────────────────────
    error_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "errors.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # ── logs/agents.log — agent activity only ─────────────────────────────
    agents_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "agents.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    agents_handler.setLevel(numeric_level)
    agents_handler.setFormatter(formatter)

    # Apply only to the agent/scheduler namespaces
    for name in ("app.agents", "app.core.scheduler", "app.core.tracking", "app.evaluator"):
        logging.getLogger(name).addHandler(agents_handler)

    # Quiet down noisy third-party libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialised — level={level} | "
        f"files: {LOG_DIR}/app.log, errors.log, agents.log"
    )
