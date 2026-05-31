"""
src/utils/logger.py
Centralised logging setup. Every module calls get_logger(__name__).
Logs go to stdout (GitHub Actions) and to logs/pipeline.log (rotated).
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "pipeline.log"
# ~5 MB × 3 files — keeps local/CI disk use small; full history goes to S3 in prod
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 5 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 3))


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

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    LOG_DIR.mkdir(exist_ok=True)
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
