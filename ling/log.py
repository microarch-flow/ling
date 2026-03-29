from __future__ import annotations
import logging
from pathlib import Path

def setup_logger() -> logging.Logger:
    log_path = Path.home() / ".ling" / "debug.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ling")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)

    return logger

log = setup_logger()
