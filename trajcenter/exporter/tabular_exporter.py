# trajcenter/exporter/tabular_exporter.py

"""
Exporteur tabulaire abstrait — logique commune Excel et CSV.

Ce module factorise la construction des quatre DataFrames (traj, tools,
wobjs, meta) dans :class:`_TabularExporter`.

Les sous-classes n'ont qu'une seule méthode à implémenter :
:meth:`_write_sheets` qui reçoit les DataFrames prêts et écrit le(s) fichier(s).

Architecture
-------------
::

    BaseExporter (ABC)
        └── _TabularExporter (ABC)
                ├── ExcelExporter   → _write_sheets() via openpyxl
                └── CsvExporter     → _write_sheets() via 4 fichiers CSV

Symétrie import / export
-------------------------
La feuille ``traj`` exportée est le miroir exact de la feuille importée :
- ``tool_index`` et ``wobj_index`` sont résolus en noms (colonnes ``tool`` et ``wobj``).
- Les floats sont arrondis selon :attr:`ExportOptions.float_precision`.
- La feuille ``meta`` est produite en format clé/valeur, relisible à l'import.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.core.trajectory import Trajectory, TrajectoryMeta
from trajcenter.exporter.base import BaseExporter
from trajcenter.exporter.options import ExportOptions


#: Colonnes flottantes à arrondir à l'export.
_FLOAT_COLS: frozenset[str] = frozenset({"x", "y", "z", "q1", "q2", "q3", "q4"})

#: Champs de TrajectoryMeta à ignorer à l'export
#: (recalculés à l'import ou redondants).
_META_SKIP_FIELDS: frozenset[str] = frozenset({
    "point_count",   # recalculé depuis le DataFrame
    "autocompleted", # propre à l'import, sans sens à la relecture
})

#: Ordre préféré des colonnes dans la feuille traj.
_TRAJ_COL_ORDER: list[str] = [
    "x", "y", "z",
    "q1", "q2", "q3", "q4",
    "cf1", "cf4", "cf6", "cfx",
    "move_type", "speed", "zone",
    "tool", "wobj",
]


class _TabularExporter(BaseExporter):
    """Exporteur abstrait pour les formats tabulaires (Excel, CSV).

    Sous-classes concrètes :
    :class:`~trajcenter.exporter.excel_exporter.ExcelExporter` et
    :class:`~trajcenter.exporter.csv_exporter.CsvExporter`.

    Les sous-classes doivent implémenter :meth:`_write_sheets`.

    Attributes:
        options: Options d'export.
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        super().__init__(options)

    # ------------------------------------------------------------------
    # Interface à implémenter
    # ------------------------------------------------------------------

    @abstractmethod
    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        tools_df: pd.DataFrame,
        wobjs_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
    ) -> Path:
        """Écrit le(s) fichier(s) de sortie depuis les DataFrames préparés.

        Args:
            stem:      Nom de base du fichier (sans extension).
            dest_dir:  Dossier de destination (déjà créé).
            traj_df:   DataFrame des points (tool/wobj résolus en noms).
            tools_df:  DataFrame des tools (colonne ``name``).
            wobjs_df:  DataFrame des wobjs (colonne ``name``).
            meta_df:   DataFrame clé/valeur des métadonnées, ou ``None``
                       si ``options.include_meta`` est ``False``.

        Returns:
            Chemin du fichier principal produit.
        """
        ...

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Exporte une trajectoire vers un fichier tabulaire.

        Args:
            trajectory: Trajectoire à exporter.
            dest_dir:   Dossier de destination (créé si absent).

        Returns:
            Chemin du fichier principal produit.
        """
        dest_dir = self._ensure_dir(dest_dir)
        stem = trajectory.meta.name

        traj_df  = self._build_traj_df(trajectory)
        tools_df = self._build_tools_df(trajectory)
        wobjs_df = self._build_wobjs_df(trajectory)
        meta_df  = self._build_meta_df(trajectory) if self.options.include_meta else None

        return self._write_sheets(
            stem=stem,
            dest_dir=dest_dir,
            traj_df=traj_df,
            tools_df=tools_df,
            wobjs_df=wobjs_df,
            meta_df=meta_df,
        )

    # ------------------------------------------------------------------
    # Construction des DataFrames
    # ------------------------------------------------------------------

    def _build_traj_df(self, trajectory: Trajectory) -> pd.DataFrame:
        """Construit le DataFrame des points prêt à l'export.

        - ``tool_index`` → colonne ``tool`` (noms résolus depuis ``trajectory.tools``).
        - ``wobj_index`` → colonne ``wobj`` (noms résolus depuis ``trajectory.wobjs``).
        - Floats arrondis selon :attr:`ExportOptions.float_precision`.
        - Colonnes ordonnées selon :data:`_TRAJ_COL_ORDER`.

        Args:
            trajectory: Trajectoire source.

        Returns:
            DataFrame prêt à l'écriture.
        """
        df = trajectory.points.copy()
        prec = self.options.float_precision

        # Résolution tool_index → nom
        if "tool_index" in df.columns and trajectory.tools:
            df["tool"] = df["tool_index"].apply(
                lambda i: trajectory.tools[int(i)]
                if 0 <= int(i) < len(trajectory.tools)
                else trajectory.tools[0]
            )
            df = df.drop(columns=["tool_index"])

        # Résolution wobj_index → nom
        if "wobj_index" in df.columns and trajectory.wobjs:
            df["wobj"] = df["wobj_index"].apply(
                lambda i: trajectory.wobjs[int(i)]
                if 0 <= int(i) < len(trajectory.wobjs)
                else trajectory.wobjs[0]
            )
            df = df.drop(columns=["wobj_index"])

        # Arrondi des floats
        float_cols = [c for c in df.columns if c in _FLOAT_COLS]
        df[float_cols] = df[float_cols].round(prec)

        # Réordonnancement des colonnes
        ordered = [c for c in _TRAJ_COL_ORDER if c in df.columns]
        extras  = [c for c in df.columns if c not in _TRAJ_COL_ORDER]
        df = df[ordered + extras]

        return df.reset_index(drop=True)

    @staticmethod
    def _build_tools_df(trajectory: Trajectory) -> pd.DataFrame:
        """Construit le DataFrame de la table tools.

        Args:
            trajectory: Trajectoire source.

        Returns:
            DataFrame à une colonne ``name``.
        """
        return pd.DataFrame({"name": trajectory.tools})

    @staticmethod
    def _build_wobjs_df(trajectory: Trajectory) -> pd.DataFrame:
        """Construit le DataFrame de la table wobjs.

        Args:
            trajectory: Trajectoire source.

        Returns:
            DataFrame à une colonne ``name``.
        """
        return pd.DataFrame({"name": trajectory.wobjs})

    @staticmethod
    def _build_meta_df(trajectory: Trajectory) -> pd.DataFrame:
        """Sérialise :class:`TrajectoryMeta` en DataFrame clé/valeur.

        Les champs dans :data:`_META_SKIP_FIELDS` sont omis.
        Les champs ``None`` ou listes vides sont omis.
        Les champs ``extra`` sont dépliés comme entrées individuelles.

        Args:
            trajectory: Trajectoire source.

        Returns:
            DataFrame à deux colonnes ``key`` et ``value``.
        """
        meta: TrajectoryMeta = trajectory.meta
        rows: list[dict[str, str]] = []

        # Champs directs de TrajectoryMeta
        direct_fields: dict[str, object] = {
            "name":          meta.name,
            "source_file":   meta.source_file,
            "source_format": meta.source_format.value if meta.source_format else None,
            "robot_model":   meta.robot_model,
            "created_at":    meta.created_at.isoformat() if meta.created_at else None,
            "version":       meta.version,
        }

        for key, value in direct_fields.items():
            if key in _META_SKIP_FIELDS:
                continue
            if value is None:
                continue
            rows.append({"key": key, "value": str(value)})

        # Champs extra{} dépliés
        if meta.extra:
            for key, value in meta.extra.items():
                if value is not None:
                    rows.append({"key": key, "value": str(value)})

        return pd.DataFrame(rows, columns=["key", "value"])
