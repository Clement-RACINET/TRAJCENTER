# trajcenter/exporter/excel_exporter.py

"""Exporteur Excel — produit un fichier ``.xlsx`` à 4 feuilles."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class ExcelExporter(_TabularExporter):
    """Exporte une trajectoire vers un fichier ``.xlsx``.

    Le fichier produit contient jusqu'à 4 feuilles :

    - ``traj``  : points de la trajectoire (tool/wobj résolus en noms).
    - ``tools`` : table des noms de tools.
    - ``wobjs`` : table des noms de wobjs.
    - ``meta``  : métadonnées clé/valeur (si ``options.include_meta=True``).

    Ce format est directement relisible par
    :class:`~trajcenter.converter.excel_converter.ExcelConverter`.

    Example:
        >>> from trajcenter.exporter.excel_exporter import ExcelExporter
        >>> ExcelExporter().export(traj, dest_dir=Path("exports/"))
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
        """Écrit le fichier ``.xlsx`` avec les 4 feuilles.

        Args:
            stem:      Nom de base du fichier (sans extension).
            dest_dir:  Dossier de destination.
            traj_df:   DataFrame des points.
            tools_df:  DataFrame des tools.
            wobjs_df:  DataFrame des wobjs.
            meta_df:   DataFrame des métadonnées, ou ``None``.

        Returns:
            Chemin du fichier ``.xlsx`` produit.
        """
        dest = dest_dir / f"{stem}.xlsx"

        with pd.ExcelWriter(dest, engine="openpyxl") as writer:
            traj_df.to_excel(writer,  sheet_name="traj",  index=False)
            tools_df.to_excel(writer, sheet_name="tools", index=False)
            wobjs_df.to_excel(writer, sheet_name="wobjs", index=False)
            if meta_df is not None:
                meta_df.to_excel(writer, sheet_name="meta", index=False)

        return dest
