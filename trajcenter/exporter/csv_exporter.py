# trajcenter/exporter/csv_exporter.py

"""Exporteur CSV — produit 4 fichiers dans un dossier."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class CsvExporter(_TabularExporter):
    """Exporte une trajectoire vers 4 fichiers CSV dans un dossier.

    Fichiers produits (``stem`` = ``trajectory.meta.name``) :

    - ``{stem}.csv``        : points de la trajectoire.
    - ``{stem}_tools.csv``  : table des noms de tools.
    - ``{stem}_wobjs.csv``  : table des noms de wobjs.
    - ``{stem}_meta.csv``   : métadonnées clé/valeur (si ``options.include_meta=True``).

    Example:
        >>> from trajcenter.exporter.csv_exporter import CsvExporter
        >>> CsvExporter().export(traj, dest_dir=Path("exports/"))
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        super().__init__(options)

    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        tools_df: pd.DataFrame,
        wobjs_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
    ) -> Path:
        """Écrit les 4 fichiers CSV.

        Args:
            stem:      Nom de base des fichiers (sans extension).
            dest_dir:  Dossier de destination.
            traj_df:   DataFrame des points.
            tools_df:  DataFrame des tools.
            wobjs_df:  DataFrame des wobjs.
            meta_df:   DataFrame des métadonnées, ou ``None``.

        Returns:
            Chemin du fichier principal ``{stem}.csv``.
        """
        sep = self.options.csv_separator
        enc = self.options.csv_encoding

        main = dest_dir / f"{stem}.csv"

        traj_df.to_csv(main,                              sep=sep, encoding=enc, index=False)
        tools_df.to_csv(dest_dir / f"{stem}_tools.csv",  sep=sep, encoding=enc, index=False)
        wobjs_df.to_csv(dest_dir / f"{stem}_wobjs.csv",  sep=sep, encoding=enc, index=False)

        if meta_df is not None:
            meta_df.to_csv(dest_dir / f"{stem}_meta.csv", sep=sep, encoding=enc, index=False)

        return main
