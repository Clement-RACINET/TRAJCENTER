# trajcenter/converter/excel_converter.py

"""
Convertisseur de fichiers Excel (``.xlsx``, ``.xls``) vers ``.trajcenter``.

Délègue toute la logique de conversion à
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
Cette classe n'implémente que la lecture du fichier Excel via ``openpyxl``.

Structure attendue du classeur
--------------------------------
- **Feuilles trajectoire** : toute feuille dont le nom n'est pas réservé.
- **Feuille** ``tools``    : table des tools (colonne ``name``). Optionnelle.
- **Feuille** ``wobjs``    : table des wobjs (colonne ``name``). Optionnelle.
- **Feuille** ``meta``     : ignorée silencieusement.

Colonnes obligatoires : ``x``, ``y``, ``z``.
Toutes les autres colonnes sont autocomplétées depuis
:class:`~trajcenter.converter.defaults.ConversionDefaults` si absentes.
Les quaternions absents sont remplacés par l'orientation identité ``[1,0,0,0]``.

Example:
    ::

        traj  = ExcelConverter().convert(Path("data/single.xlsx"))
        trajs = ExcelConverter().convert_all(Path("data/multi.xlsx"))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.tabular_converter import _TabularConverter
from trajcenter.core.trajectory import SourceFormat


class ExcelConverter(_TabularConverter):
    """Convertisseur de classeurs Excel vers :class:`~trajcenter.core.trajectory.Trajectory`.

    Hérite de :class:`~trajcenter.converter.tabular_converter._TabularConverter`
    pour toute la logique métier. N'implémente que la lecture Excel.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.excel_converter import ExcelConverter

            traj = ExcelConverter().convert(Path("trajectoires.xlsx"))
            traj.save("trajectory_store/trajectoires.trajcenter")
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        super().__init__(defaults)

    @property
    def _source_format(self) -> SourceFormat:
        return SourceFormat.EXCEL

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Lit toutes les feuilles du classeur Excel.

        Args:
            source: Chemin vers le fichier ``.xlsx`` / ``.xls``.

        Returns:
            Dictionnaire ordonné ``{nom_feuille: DataFrame brut}``.
        """
        xl = pd.ExcelFile(source, engine="openpyxl")
        return {
            str(sheet): pd.read_excel(xl, sheet_name=sheet, header=0)
            for sheet in xl.sheet_names
        }
