"""
src/utils/logger.py
Centralised logging setup. Every module calls get_logger(__name__).
Logs go to stdout (captured by Docker / CloudWatch) and to logs/pipeline.log.
"""
import logging
import os
import sys
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)

    if logger.handlers:          # avoid adding duplicate handlers
        return logger

    logger.setLevel(log_level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler (captured by Docker / CloudWatch)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # file handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
