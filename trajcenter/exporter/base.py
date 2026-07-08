# trajcenter/exporter/base.py

"""
Classe de base abstraite pour tous les exporters TrajCenter.

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
    """Classe de base abstraite pour tous les exporters.

    Attributes:
        options: Options d'export (précision, encodage, etc.).
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        self.options: ExportOptions = options or ExportOptions()

    # ------------------------------------------------------------------
    # Interface à implémenter
    # ------------------------------------------------------------------

    @abstractmethod
    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Exporte une trajectoire vers un fichier.

        Args:
            trajectory: Trajectoire à exporter.
            dest_dir:   Dossier de destination (créé si absent).

        Returns:
            Chemin du fichier produit.
        """
        ...

    # ------------------------------------------------------------------
    # Helpers communs
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_dir(dest_dir: Path) -> Path:
        """Crée le dossier de destination s'il n'existe pas.

        Args:
            dest_dir: Chemin du dossier cible.

        Returns:
            Le même chemin, résolu et créé.
        """
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir
