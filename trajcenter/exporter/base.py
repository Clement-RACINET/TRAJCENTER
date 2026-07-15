#!/usr/bin/env python3
# trajcenter/exporter/base.py
"""Abstract base class for all TrajCenter exporters.

Author: Clement RACINET

Architecture
-------------
::

    BaseExporter (ABC)
        └── _TabularExporter (ABC)
                ├── ExcelExporter
                └── CsvExporter
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.options import ExportOptions


class BaseExporter(ABC):
    """Abstract base class for all exporters.

    Attributes:
        options: Export options (precision, encoding, etc.).
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the exporter.

        Args:
            options: Export options. When ``None``,
                :class:`~trajcenter.exporter.options.ExportOptions`
                is instantiated with its own default values.
        """
        self.options: ExportOptions = options or ExportOptions()

    # ------------------------------------------------------------------
    # Interface to implement
    # ------------------------------------------------------------------

    @abstractmethod
    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Export a trajectory to a file.

        Args:
            trajectory: Trajectory to export.
            dest_dir: Destination directory (created when absent).

        Returns:
            Path of the produced file.
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_dir(dest_dir: Path) -> Path:
        """Create the destination directory if it does not exist.

        Args:
            dest_dir: Path to the target directory.

        Returns:
            The same path, resolved and created.
        """
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir
