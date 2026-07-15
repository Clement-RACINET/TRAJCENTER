# trajcenter/core/logger.py
"""Centralised logging access for TrajCenter.

Re-exports :func:`get_logger` from ``abb_rws_client`` so that all TrajCenter
modules obtain a properly namespaced child logger without importing the lib
directly.

The module is intentionally named ``logger`` (not ``logging``) to avoid
shadowing the Python standard-library :mod:`logging` module.

Usage::

    from trajcenter.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("TrajCenter started")
"""

from __future__ import annotations

from abb_rws_client_python_rw6.core.logger import get_logger

__all__ = ["get_logger"]
