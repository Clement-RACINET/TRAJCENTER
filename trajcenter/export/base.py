#!/usr/bin/env python3
# trajcenter/export/base.py
"""Abstract base class for all TrajCenter exporters.

> **Author**: Clément RACINET

Architecture
------------
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
from trajcenter.export.options import ExportOptions


class BaseExporter(ABC):
    """Abstract base class for all exporters.

    ABB Route:
        N/A — local file export, no RWS route.

    ABB Constraints:
        No mastership is acquired. No RAPID variable is read or written.

    Attributes:
        options: Export options.

    Example:
        ::

            exporter = CsvExporter()
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the exporter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            options: Export options. When ``None``,
                :class:`~trajcenter.export.options.ExportOptions`
                is instantiated with its own default values.

        Returns:
            None.

        Example:
            ::

                exporter = CsvExporter(options=ExportOptions())
        """
        self.options: ExportOptions = options or ExportOptions()

    @abstractmethod
    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Export a trajectory to a file.

        ABB Route:
            N/A — local file export.

        ABB Constraints:
            No ABB controller access.

        Args:
            trajectory: Trajectory to export.
            dest_dir: Destination directory, created when absent.

        Returns:
            Path of the produced main file.

        Raises:
            OSError: If the destination directory or output file cannot
                be created.

        Example:
            ::

                path = exporter.export(traj, Path("exports"))
        """
        ...

    @staticmethod
    def _ensure_dir(dest_dir: Path) -> Path:
        """Create the destination directory if it does not exist.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            dest_dir: Path to the target directory.

        Returns:
            The resolved directory path.

        Raises:
            OSError: If the directory cannot be created.

        Example:
            ::

                dest = BaseExporter._ensure_dir(Path("exports"))
        """
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir
