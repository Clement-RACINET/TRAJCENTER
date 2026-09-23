#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 C. RACINET
#
# SPDX-License-Identifier: X11

# trajcenter/core/logger.py
"""Logging helpers for TrajCenter."""

from __future__ import annotations

import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_TRAJCENTER_LOGGER_NAME = "trajcenter"


def configure_logging(level: LogLevel = "INFO") -> None:
    """Configure logging for the complete TrajCenter package.

    This configuration only targets loggers whose name begins with
    ``trajcenter``. It therefore avoids modifying the logging configuration
    used internally by the ABB RWS client library.

    Args:
        level: Minimum logging level to display.
    """
    package_logger = logging.getLogger(_TRAJCENTER_LOGGER_NAME)

    package_logger.setLevel(getattr(logging, level))
    package_logger.propagate = False

    # Avoid adding duplicate handlers if configuration is called more than once.
    if not package_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            fmt=("%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"),
            datefmt="%H:%M:%S",
        )

        handler.setFormatter(formatter)
        package_logger.addHandler(handler)

    # The handler must accept all messages allowed by the package logger.
    for handler in package_logger.handlers:
        handler.setLevel(getattr(logging, level))


def get_logger(name: str) -> logging.Logger:
    """Return a TrajCenter logger.

    Args:
        name: Logger name, normally ``__name__``.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
