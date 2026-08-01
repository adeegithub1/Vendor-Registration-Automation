"""
Centralized logging setup for Vendor Questionnaire AI.

WHY THIS EXISTS
----------------
In a commercial product, you will not be sitting next to the manufacturing
company's computer when something goes wrong. Logs are how you find out
what happened. Every module in this project calls get_logger(__name__)
instead of configuring its own logging, so:

  1. All logs share the same format (easy to search/grep).
  2. All logs go to the same rotating file (won't fill up the client's disk).
  3. Changing the log level or format in one place changes it everywhere.

HOW ROTATION WORKS
-------------------
We use RotatingFileHandler, which caps each log file at a fixed size and
keeps a limited number of backup files (log.txt, log.txt.1, log.txt.2 ...).
Once the limit is reached, the oldest backup is deleted. This prevents logs
from growing forever on a client machine that might run this software daily
for years.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Imported lazily inside get_logger to avoid a circular import between
# config.py and logger.py (config may eventually want to log its own
# validation warnings).
_LOGGERS_CONFIGURED = set()


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Usage in any module:
        from modules.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")

    Args:
        name: Typically __name__ of the calling module, so log lines show
              exactly which file produced them (e.g. "modules.docx_reader").

    Returns:
        A logging.Logger instance, configured once and reused on every
        subsequent call (Python's logging module caches loggers by name,
        so calling this repeatedly for the same name is cheap and safe).
    """
    from config import settings  # local import: avoids circular import at module load time

    logger = logging.getLogger(name)

    # Only attach handlers once per logger name. Without this guard, calling
    # get_logger() multiple times for the same module would duplicate every
    # log line (a very common logging bug).
    if name in _LOGGERS_CONFIGURED:
        return logger

    logger.setLevel(settings.log_level)

    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler: for when you're developing and watching the terminal ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # --- Rotating file handler: for persistent logs on the client's machine ---
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path: Path = settings.logs_dir / "vendor_ai.log"

    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file before rotating
        backupCount=5,  # keep 5 old log files, then start deleting the oldest
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # Prevent log lines from also being handled by the root logger
    # (which would otherwise print everything twice).
    logger.propagate = False

    _LOGGERS_CONFIGURED.add(name)
    return logger
