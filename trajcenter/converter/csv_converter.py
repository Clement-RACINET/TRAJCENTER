# trajcenter/converter/csv_converter.py

"""
Convertisseur de fichiers CSV / texte délimité vers ``.trajcenter``.

Délègue toute la logique de conversion à
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
Cette classe n'implémente que la lecture du fichier CSV avec détection
automatique du séparateur (virgule ``,`` ou point-virgule ``;``).

Séparateur
-----------
Le séparateur est détecté automatiquement via :func:`_detect_separator`
en lisant les 4 premières lignes du fichier. Si la détection échoue,
la virgule est utilisée par défaut.

Le séparateur peut également être forcé via le paramètre ``separator``
du constructeur.

Encodage
---------
L'encodage est détecté automatiquement (UTF-8 avec BOM, UTF-8, Latin-1).
Il peut être forcé via le paramètre ``encoding``.

Example:
    ::

        traj = CsvConverter().convert(Path("data/trajectoire.csv"))

        # Forcer le séparateur et l'encodage
        traj = CsvConverter(separator=";", encoding="latin-1").convert(
            Path("data/export_excel.csv")
        )
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.tabular_converter import _TabularConverter
from trajcenter.core.trajectory import SourceFormat


# ---------------------------------------------------------------------------
# Détection du séparateur
# ---------------------------------------------------------------------------

_CANDIDATE_SEPARATORS: list[str] = [",", ";", "\t", "|"]
_SNIFF_LINES: int = 4


def _detect_separator(source: Path, encoding: str = "utf-8-sig") -> str:
    """Détecte automatiquement le séparateur d'un fichier CSV.

    Lit les :data:`_SNIFF_LINES` premières lignes non vides et utilise
    :class:`csv.Sniffer` pour identifier le délimiteur. Si la détection
    échoue ou retourne un séparateur non standard, la virgule est utilisée.

    Args:
        source:   Chemin vers le fichier CSV.
        encoding: Encodage à utiliser pour la lecture. ``"utf-8-sig"``
                  gère automatiquement le BOM UTF-8.

    Returns:
        Séparateur détecté parmi ``","``, ``";"``, ``"\\t"``, ``"|"``,
        ou ``","`` par défaut.
    """
    try:
        lines: list[str] = []
        with source.open(encoding=encoding, errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
                if len(lines) >= _SNIFF_LINES:
                    break

        sample = "\n".join(lines)
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_CANDIDATE_SEPARATORS))
        return dialect.delimiter if dialect.delimiter in _CANDIDATE_SEPARATORS else ","

    except (csv.Error, UnicodeDecodeError, OSError):
        return ","


# ---------------------------------------------------------------------------
# Convertisseur CSV
# ---------------------------------------------------------------------------


class CsvConverter(_TabularConverter):
    """Convertisseur de fichiers CSV vers :class:`~trajcenter.core.trajectory.Trajectory`.

    Hérite de :class:`~trajcenter.converter.tabular_converter._TabularConverter`
    pour toute la logique métier. N'implémente que la lecture CSV avec
    détection automatique du séparateur.

    Attributes:
        defaults:  Valeurs par défaut pour l'autocomplétion.
        separator: Séparateur forcé. Si ``None``, détection automatique.
        encoding:  Encodage du fichier. Par défaut ``"utf-8-sig"``
                   (gère UTF-8 avec et sans BOM).

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.csv_converter import CsvConverter

            # Détection automatique du séparateur
            traj = CsvConverter().convert(Path("trajectoire.csv"))

            # Séparateur forcé (export Excel français)
            traj = CsvConverter(separator=";").convert(Path("export.csv"))
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        separator: str | None = None,
        encoding: str = "utf-8-sig",
    ) -> None:
        """Initialise le convertisseur CSV.

        Args:
            defaults:  Valeurs par défaut pour l'autocomplétion.
            separator: Séparateur CSV forcé (``","`` ou ``";"`` etc.).
                       Si ``None``, détection automatique.
            encoding:  Encodage du fichier source. ``"utf-8-sig"`` par défaut
                       (gère le BOM UTF-8 des exports Excel).
        """
        super().__init__(defaults)
        self.separator: str | None = separator
        self.encoding: str = encoding

    @property
    def _source_format(self) -> SourceFormat:
        return SourceFormat.CSV

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Lit le fichier CSV et retourne une feuille unique ``"sheet"``.

        Le séparateur est détecté automatiquement si non forcé.

        Args:
            source: Chemin vers le fichier CSV.

        Returns:
            Dictionnaire ``{"sheet": DataFrame brut}``.
        """
        sep = self.separator or _detect_separator(source, encoding=self.encoding)
        df = pd.read_csv(
            source,
            sep=sep,
            encoding=self.encoding,
            header=0,
        )
        return {"sheet": df}
