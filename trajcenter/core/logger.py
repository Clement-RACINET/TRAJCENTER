#!/usr/bin/env python3
# trajcenter/core/logger.py
"""Logging helpers for TrajCenter."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a TrajCenter logger.

    Args:
        name: Logger name.

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
