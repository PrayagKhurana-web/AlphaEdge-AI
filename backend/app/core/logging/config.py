"""Central application logging configuration."""

from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    """Configure consistent application logging."""

    log_level = os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=(
            "%(asctime)s | %(levelname)s | %(name)s | "
            "%(message)s"
        ),
        stream=sys.stdout,
        force=True,
    )
