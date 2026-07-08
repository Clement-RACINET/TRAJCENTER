# examples/convert_excel_example.py

#!/usr/bin/env python3
"""
Exemple de conversion d'un fichier Excel (.xlsx) vers .trajcenter.

Deux cas sont illustrés :
  1. Classeur à feuille unique  → convert()
  2. Classeur multi-feuilles    → convert_all()

Modifiez les variables de la section "Configuration" ci-dessous,
puis lancez directement :

    python examples/convert_excel_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — à adapter selon votre contexte
# ---------------------------------------------------------------------------

# Cas 1 — classeur à feuille unique (XYZ + colonnes optionnelles)
SOURCE_SINGLE = Path("trajectory_files/trajectoires_mono.xlsx")

# Cas 2 — classeur multi-feuilles (une trajectoire par feuille)
SOURCE_MULTI  = Path("trajectory_files/trajectoires_multi.xlsx")

OUTPUT_DIR = Path("trajectory_store")

# Valeurs de remplacement pour les colonnes absentes dans le fichier Excel.
# Utile notamment si le classeur ne contient que des colonnes XYZ
# (les quaternions seront complétés avec l'orientation identité).
DEFAULTS = ConversionDefaults(
    move_type = "MoveL",
    speed     = "v10",
    zone      = "z0",
)

# ---------------------------------------------------------------------------
# Cas 1 — feuille unique
# ---------------------------------------------------------------------------

print("=" * 60)
print("Cas 1 — Classeur à feuille unique")
print("=" * 60)

traj: Trajectory = ExcelConverter(defaults=DEFAULTS).convert(SOURCE_SINGLE)

print(traj)
print(f"  tools         : {traj.tools}")
print(f"  wobjs         : {traj.wobjs}")
print(f"  autocompleted : {traj.meta.autocompleted}")
print(f"  is_complete   : {traj.is_complete}")
print()
print(traj.points.head())

dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
print(f"\nSauvegardé → {dest}")

# ---------------------------------------------------------------------------
# Cas 2 — multi-feuilles
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print("Cas 2 — Classeur multi-feuilles")
print("=" * 60)

trajs: list[Trajectory] = ExcelConverter(defaults=DEFAULTS).convert_all(SOURCE_MULTI)

print(f"{len(trajs)} trajectoire(s) extraite(s) :\n")

for traj in trajs:
    print(f"  [{traj.meta.name}]  {traj.point_count} points  "
          f"| tools={traj.tools}  wobjs={traj.wobjs}")
    dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
    print(f"    → Sauvegardé : {dest}")
