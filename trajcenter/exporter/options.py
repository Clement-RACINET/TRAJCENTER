# trajcenter/exporter/options.py

"""Options de configuration pour les exporters tabulaires."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExportOptions:
    """Options de configuration pour les exporters tabulaires.

    Attributes:
        float_precision: Nombre de décimales pour les colonnes numériques flottantes.
        csv_separator:   Séparateur de colonnes pour le format CSV.
        csv_encoding:    Encodage du fichier CSV.
                         ``utf-8-sig`` inclut un BOM, ce qui permet à Excel
                         d'ouvrir le fichier sans problème d'encodage.
        include_meta:    Si ``True``, une feuille / fichier ``meta`` est produit
                         avec les métadonnées de la trajectoire.
    """

    float_precision: int = 6
    csv_separator:   str = ","
    csv_encoding:    str = "utf-8-sig"
    include_meta:    bool = True
