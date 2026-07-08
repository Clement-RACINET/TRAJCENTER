# examples/convert_apt_example.py

#!/usr/bin/env python3
"""
Exemple de conversion d'un fichier APT source CATIA (.aptsource) vers .trajcenter.

Trois cas sont illustrés :
  1. Conversion standard           → coordonnées brutes APT
  2. Avec transformation CATIA     → matrice de repère appliquée
  3. Avec defaults personnalisés   → vitesse et zone de secours

Modifiez les variables de la section "Configuration" ci-dessous,
puis lancez directement :

    python examples/convert_apt_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.apt_converter import AptConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — à adapter selon votre contexte
# ---------------------------------------------------------------------------

SOURCE = Path("trajectory_files/PrepaFlans_Pointage.aptsource")
DEST_DIR = Path("trajectory_store")

# ---------------------------------------------------------------------------
# Cas 1 — Conversion standard (coordonnées brutes)
# ---------------------------------------------------------------------------

print("=" * 60)
print("Cas 1 — Conversion standard")
print("=" * 60)

traj = AptConverter().convert(SOURCE)

print(traj)
print(f"  Outil détecté   : {traj.tools[0]!r}")
print(f"  Wobj par défaut : {traj.wobjs[0]!r}")
print(f"  Autocomplété    : {traj.meta.autocompleted}")
print()

# Aperçu des 3 premiers points
print(traj.points[["x", "y", "z", "q1", "move_type", "speed"]].head(3).to_string(index=False))
print()

dest = AptConverter().convert_and_save(source=SOURCE, dest_dir=DEST_DIR)
print(f"  Sauvegardé → {dest}")
print()

# ---------------------------------------------------------------------------
# Cas 2 — Avec transformation CATIA
# ---------------------------------------------------------------------------

print("=" * 60)
print("Cas 2 — Avec transformation CATIA (apply_catia_transform=True)")
print("=" * 60)

traj_transformed = AptConverter(apply_catia_transform=True).convert(SOURCE)

print(traj_transformed)
print()

# Comparaison premier point avant / après transformation
traj_raw = AptConverter().convert(SOURCE)
pt_raw = traj_raw.points.iloc[0]
pt_tr  = traj_transformed.points.iloc[0]

print(f"  Point 0 brut        : x={pt_raw['x']:.3f}  y={pt_raw['y']:.3f}  z={pt_raw['z']:.3f}")
print(f"  Point 0 transformé  : x={pt_tr['x']:.3f}  y={pt_tr['y']:.3f}  z={pt_tr['z']:.3f}")
print()

dest_tr = AptConverter(apply_catia_transform=True).convert_and_save(
    source=SOURCE,
    dest_dir=DEST_DIR,
    stem=SOURCE.stem + "_transformed",
)
print(f"  Sauvegardé → {dest_tr}")
print()

# ---------------------------------------------------------------------------
# Cas 3 — Defaults personnalisés
# ---------------------------------------------------------------------------

print("=" * 60)
print("Cas 3 — Defaults personnalisés")
print("=" * 60)

custom_defaults = ConversionDefaults(
    speed="v300",
    zone="z5",
    tool="Tool_Pointeur_D10",
    wobj="Wobj_Flan",
)

traj_custom = AptConverter(defaults=custom_defaults).convert(SOURCE)

print(traj_custom)
print(f"  Outil              : {traj_custom.tools[0]!r}")
print(f"  Wobj               : {traj_custom.wobjs[0]!r}")
print(f"  Vitesse point 0    : {traj_custom.points['speed'].iloc[0]!r}")
print(f"  Zone point 0       : {traj_custom.points['zone'].iloc[0]!r}")
print()

# ---------------------------------------------------------------------------
# Vérification roundtrip
# ---------------------------------------------------------------------------

print("=" * 60)
print("Vérification roundtrip save → load")
print("=" * 60)

saved = traj.save(DEST_DIR / "pointage_check.trajcenter")
loaded = Trajectory.load(saved)

assert loaded.point_count == traj.point_count
assert loaded.tools == traj.tools
assert loaded.is_complete

print(f"  ✓ {loaded.point_count} points rechargés avec succès")
print(f"  ✓ Complet : {loaded.is_complete}")
print(f"  ✓ Outil   : {loaded.tools[0]!r}")
