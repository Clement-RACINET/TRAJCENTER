#!/usr/bin/env python3
# scripts/examples/convert_apt_example.py
"""APT source to ``.trajcenter`` conversion example.

Author: Clement RACINET

Demonstrates three conversion scenarios for a CATIA APT source file
(``.aptsource``):

1. **Standard conversion** — raw APT coordinates.
2. **With CATIA transform** — frame matrix applied to all points.
3. **With custom defaults** — override speed, zone, tool and wobj.

Edit the variables in the "Configuration" section below, then run
directly::

    python scripts/examples/convert_apt_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.apt_converter import AptConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — adjust to your context
# ---------------------------------------------------------------------------

SOURCE = Path("trajectory_files/PrepaFlans_Pointage.aptsource")
DEST_DIR = Path("trajectory_store")

# ---------------------------------------------------------------------------
# Case 1 — Standard conversion (raw coordinates)
# ---------------------------------------------------------------------------

print("=" * 60)
print("Case 1 — Standard conversion")
print("=" * 60)

traj = AptConverter().convert(SOURCE)

print(traj)
print(f"  Detected tool    : {traj.tools[0]!r}")
print(f"  Default wobj     : {traj.wobjs[0]!r}")
print(f"  Autocompleted    : {traj.meta.autocompleted}")
print()

# Preview of the first 3 points
print(
    traj.points[["x", "y", "z", "q1", "move_type", "speed"]]
    .head(3)
    .to_string(index=False)
)
print()

dest = AptConverter().convert_and_save(source=SOURCE, dest_dir=DEST_DIR)
print(f"  Saved → {dest}")
print()

# ---------------------------------------------------------------------------
# Case 2 — With CATIA transform
# ---------------------------------------------------------------------------

print("=" * 60)
print("Case 2 — With CATIA transform (apply_catia_transform=True)")
print("=" * 60)

traj_transformed = AptConverter(apply_catia_transform=True).convert(SOURCE)

print(traj_transformed)
print()

# Compare first point before / after transform
traj_raw = AptConverter().convert(SOURCE)
pt_raw = traj_raw.points.iloc[0]
pt_tr = traj_transformed.points.iloc[0]

print(
    f"  Point 0 raw         : x={pt_raw['x']:.3f}  y={pt_raw['y']:.3f}  z={pt_raw['z']:.3f}"
)
print(
    f"  Point 0 transformed : x={pt_tr['x']:.3f}  y={pt_tr['y']:.3f}  z={pt_tr['z']:.3f}"
)
print()

dest_tr = AptConverter(apply_catia_transform=True).convert_and_save(
    source=SOURCE,
    dest_dir=DEST_DIR,
    stem=SOURCE.stem + "_transformed",
)
print(f"  Saved → {dest_tr}")
print()

# ---------------------------------------------------------------------------
# Case 3 — Custom defaults
# ---------------------------------------------------------------------------

print("=" * 60)
print("Case 3 — Custom defaults")
print("=" * 60)

custom_defaults = ConversionDefaults(
    speed="v300",
    zone="z5",
    tool="Tool_Pointeur_D10",
    wobj="Wobj_Flan",
)

traj_custom = AptConverter(defaults=custom_defaults).convert(SOURCE)

print(traj_custom)
print(f"  Tool              : {traj_custom.tools[0]!r}")
print(f"  Wobj              : {traj_custom.wobjs[0]!r}")
print(f"  Speed at point 0  : {traj_custom.points['speed'].iloc[0]!r}")
print(f"  Zone at point 0   : {traj_custom.points['zone'].iloc[0]!r}")
print()

# ---------------------------------------------------------------------------
# Roundtrip verification
# ---------------------------------------------------------------------------

print("=" * 60)
print("Roundtrip verification: save → load")
print("=" * 60)

saved = traj.save(DEST_DIR / "pointage_check.trajcenter")
loaded = Trajectory.load(saved)

assert loaded.point_count == traj.point_count
assert loaded.tools == traj.tools
assert loaded.is_complete

print(f"  ✓ {loaded.point_count} points reloaded successfully")
print(f"  ✓ Complete : {loaded.is_complete}")
print(f"  ✓ Tool     : {loaded.tools[0]!r}")
