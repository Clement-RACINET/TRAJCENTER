#!/usr/bin/env python3
# examples/convert_mod_example.py

"""
Exemple minimal de conversion d'un fichier RAPID .mod vers .trajcenter.

Modifiez les variables de la section "Configuration" ci-dessous,
puis lancez directement :

    python examples/convert_mod_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — à adapter selon votre contexte
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("trajectory_files/mod_exemple.mod")
OUTPUT_DIR  = Path("trajectory_store")

# Valeurs de remplacement pour les colonnes absentes dans le .mod
# (ici "vitesse" est une variable RAPID → speed sera autocomplété)
DEFAULTS = ConversionDefaults(
    speed     = "v500",
    zone      = "z0",
    move_type = "MoveL",
)

# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

traj: Trajectory = ModConverter(defaults=DEFAULTS).convert(SOURCE_FILE)

print(traj)
print(f"  tools          : {traj.tools}")
print(f"  wobjs          : {traj.wobjs}")
print(f"  autocompleted  : {traj.meta.autocompleted}")
print(f"  is_complete    : {traj.is_complete}")
print()
print(traj.points.head())

# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------

dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
print(f"\nSauvegardé → {dest}")
