#!/usr/bin/env python3
# examples/export_excel.py
"""
Exemple d'import puis de réexport d'une trajectoire vers Excel (.xlsx).

Deux cas sont illustrés :
  1. Import depuis un fichier .trajcenter  → export Excel
  2. Import depuis un fichier .xlsx        → export Excel (re-export)

Modifiez les variables de la section "Configuration" ci-dessous,
puis lancez directement :

    python examples/export_excel_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions

# ---------------------------------------------------------------------------
# Configuration — à adapter selon votre contexte
# ---------------------------------------------------------------------------

# Cas 1 — source : fichier .trajcenter déjà converti
SOURCE_TRAJCENTER = Path("trajectory_store/test_basic.trajcenter")

# Cas 2 — source : fichier Excel original (re-export direct)
SOURCE_XLSX = Path("trajectory_files/test_basic.xlsx")

OUTPUT_DIR = Path("trajectory_exports")

# Options d'export :
#   float_precision : nombre de décimales pour XYZ et quaternions
#   include_meta    : ajoute une feuille "meta" avec les métadonnées
EXPORT_OPTIONS = ExportOptions(
    float_precision = 6,
    include_meta    = True,
)

# ---------------------------------------------------------------------------
# Cas 1 — import .trajcenter → export .xlsx
# ---------------------------------------------------------------------------

print("=" * 60)
print("Cas 1 — Import .trajcenter → Export Excel")
print("=" * 60)

traj: Trajectory = Trajectory.load(SOURCE_TRAJCENTER)

print(traj)
print(f"  tools         : {traj.tools}")
print(f"  wobjs         : {traj.wobjs}")
print(f"  autocompleted : {traj.meta.autocompleted}")
print(f"  is_complete   : {traj.is_complete}")
print()
print(traj.points.head())

dest = ExcelExporter(options=EXPORT_OPTIONS).export(traj, OUTPUT_DIR)
print(f"\nExporté → {dest}")

# ---------------------------------------------------------------------------
# Cas 2 — import .xlsx → export .xlsx (re-export)
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print("Cas 2 — Import Excel → Re-export Excel")
print("=" * 60)

traj_from_xlsx: Trajectory = ExcelConverter().convert(SOURCE_XLSX)

print(traj_from_xlsx)
print(f"  tools         : {traj_from_xlsx.tools}")
print(f"  wobjs         : {traj_from_xlsx.wobjs}")
print(f"  autocompleted : {traj_from_xlsx.meta.autocompleted}")
print(f"  is_complete   : {traj_from_xlsx.is_complete}")
print()
print(traj_from_xlsx.points.head())

dest = ExcelExporter(options=EXPORT_OPTIONS).export(traj_from_xlsx, OUTPUT_DIR)
print(f"\nRe-exporté → {dest}")
