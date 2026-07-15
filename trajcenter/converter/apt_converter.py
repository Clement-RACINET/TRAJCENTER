#!/usr/bin/env python3
# trajcenter/converter/apt_converter.py
"""Converter for CATIA APT source files (``.aptsource``) to ``.trajcenter``.

Author: Clement RACINET

A CATIA APT file contains ``GOTO`` instructions with position and tool
vector, preceded by ``RAPID`` or ``FEDRAT`` modifiers.

Expected GOTO line format
--------------------------
::

    GOTO  /   x,  y,  z,  i,  j,  k

Where ``(x, y, z)`` is the position in mm and ``(i, j, k)`` is the
(normalised) tool direction vector.

Parsing rules
--------------
- ``RAPID`` is **non-modal**: applies only to the next ``GOTO``
  (→ ``MoveJ``). Every other ``GOTO`` is ``MoveL``.
- ``FEDRAT`` resets the mode to ``MoveL`` (machining).
- ``TPRINT`` provides the human-readable tool name
  (e.g. ``T1 PointeurD10``). This name is used as ``tools[0]``.
  If absent, ``defaults.tool`` is used.
- The tool vector ``(i, j, k)`` is converted to an ABB quaternion
  ``[q1, q2, q3, q4] = [w, x, y, z]`` via the minimal rotation
  from ``(0, 0, 1)``.
- The CATIA transformation matrix (3 ``$$`` comment lines at the top
  of the file) can be applied optionally via
  ``apply_catia_transform=True``.
- Wobjs are not present in the APT format: ``wobjs[0]`` is initialised
  from ``defaults.wobj``.
- Lines ``$$``, ``PARTNO``, ``COOLNT``, ``CUTCOM``, ``MULTAX``,
  ``SPINDL``, ``CYCLE``, ``CUTTER``, ``TOOLNO``,
  ``LOADTL``, ``REWIND``, ``END`` → ignored.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.apt_converter import AptConverter

        traj = AptConverter().convert(Path("PrepaFlans_Pointage.aptsource"))
        print(traj)
        # Trajectory(name='PrepaFlans_Pointage', points=N, tools=1, wobjs=1, ...)

        # With CATIA transformation
        traj = AptConverter(apply_catia_transform=True).convert(
            Path("PrepaFlans_Pointage.aptsource")
        )
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import (
    MoveType,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


# ---------------------------------------------------------------------------
# Internal TypedDicts
# ---------------------------------------------------------------------------


class _RawPoint(TypedDict):
    """Raw point extracted from the APT file, before quaternion conversion."""

    x: float
    y: float
    z: float
    i: float
    j: float
    k: float
    is_rapid: bool


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

#: GOTO line: captures x, y, z, i, j, k (spaces and signs allowed)
_RE_GOTO: re.Pattern[str] = re.compile(
    r"^\s*GOTO\s*/\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"  # x
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"  # y
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"  # z
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"  # i
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"  # j
    r"([+-]?\d+(?:\.\d+)?)",  # k
    re.IGNORECASE,
)

#: RAPID line (alone on its line)
_RE_RAPID: re.Pattern[str] = re.compile(r"^\s*RAPID\s*$", re.IGNORECASE)

#: FEDRAT line: resets rapid mode
_RE_FEDRAT: re.Pattern[str] = re.compile(r"^\s*FEDRAT\s*/", re.IGNORECASE)

#: TPRINT line: captures the tool name (e.g. "T1 PointeurD10")
_RE_TPRINT: re.Pattern[str] = re.compile(r"^\s*TPRINT\s*/\s*(.+)", re.IGNORECASE)

#: CATIA matrix: ``$$`` comment line with exactly 4 floats
_RE_CATIA_MATRIX_ROW: re.Pattern[str] = re.compile(
    r"^\s*\$\$\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s*$"
)


# ---------------------------------------------------------------------------
# Geometric utilities
# ---------------------------------------------------------------------------


def _tool_vector_to_quaternion(
    i: float, j: float, k: float
) -> tuple[float, float, float, float]:
    """Convert an APT tool vector to an ABB quaternion ``[w, x, y, z]``.

    Computes the minimal rotation (smallest angle) that brings the
    reference vector ``(0, 0, 1)`` onto the tool vector ``(i, j, k)``.

    ABB RAPID convention: ``[q1, q2, q3, q4] = [w, x, y, z]``
    (scalar-first).

    Args:
        i: X component of the tool vector.
        j: Y component of the tool vector.
        k: Z component of the tool vector.

    Returns:
        Tuple ``(q1, q2, q3, q4)`` = ``(w, x, y, z)``.
    """
    tool = np.array([i, j, k], dtype=np.float64)
    norm = float(np.linalg.norm(tool))
    if norm > 1e-10:
        tool = tool / norm

    z_ref = np.array([0.0, 0.0, 1.0])
    dot = float(np.clip(np.dot(z_ref, tool), -1.0, 1.0))

    # Degenerate case: vector identical to z_ref → identity quaternion
    if dot >= 1.0 - 1e-10:
        return (1.0, 0.0, 0.0, 0.0)

    # Degenerate case: vector opposite to z_ref → 180° rotation around X
    if dot <= -1.0 + 1e-10:
        return (0.0, 1.0, 0.0, 0.0)

    axis = np.cross(z_ref, tool)
    axis = axis / np.linalg.norm(axis)
    angle = np.arccos(dot)

    half = angle / 2.0
    w = float(np.cos(half))
    x = float(axis[0] * np.sin(half))
    y = float(axis[1] * np.sin(half))
    z = float(axis[2] * np.sin(half))

    return (w, x, y, z)


def _parse_catia_matrix(lines: Sequence[str]) -> np.ndarray | None:
    """Extract the CATIA transformation matrix from the file lines.

    Searches for 3 consecutive ``$$`` comment lines each containing
    4 floats (3×4 matrix: 3×3 rotation + 3×1 translation).
    The search stops as soon as a non-comment line is encountered
    after accumulation has started.

    Args:
        lines: All lines of the APT file.

    Returns:
        A ``(4, 4)`` homogeneous numpy matrix if found, ``None`` otherwise.
    """
    matrix_rows: list[list[float]] = []

    for line in lines:
        stripped = line.strip()

        if not stripped.startswith("$$") and not stripped.upper().startswith("PARTNO"):
            if matrix_rows:
                break
            continue

        m = _RE_CATIA_MATRIX_ROW.match(stripped)
        if m:
            matrix_rows.append([float(m.group(g)) for g in range(1, 5)])
            if len(matrix_rows) == 3:
                break
        elif matrix_rows:
            break

    if len(matrix_rows) != 3:
        return None

    mat = np.eye(4, dtype=np.float64)
    for row_idx, row in enumerate(matrix_rows):
        mat[row_idx, :3] = row[:3]  # rotation
        mat[row_idx, 3] = row[3]  # translation
    return mat


def _apply_transform(
    points: list[_RawPoint],
    matrix: np.ndarray,
) -> list[_RawPoint]:
    """Apply a 4×4 homogeneous matrix to positions and tool vectors.

    The translation is applied to positions ``(x, y, z)``.
    Only the rotation (3×3 sub-matrix) is applied to tool vectors
    ``(i, j, k)``.

    Args:
        points: List of :class:`_RawPoint` instances.
        matrix: ``(4, 4)`` homogeneous transformation matrix.

    Returns:
        New list of :class:`_RawPoint` with transformed positions and vectors.
    """
    R = matrix[:3, :3]
    transformed: list[_RawPoint] = []

    for pt in points:
        pos = np.array([pt["x"], pt["y"], pt["z"], 1.0])
        new_pos = matrix @ pos
        vec = np.array([pt["i"], pt["j"], pt["k"]])
        new_vec = R @ vec
        transformed.append(
            _RawPoint(
                x=float(new_pos[0]),
                y=float(new_pos[1]),
                z=float(new_pos[2]),
                i=float(new_vec[0]),
                j=float(new_vec[1]),
                k=float(new_vec[2]),
                is_rapid=pt["is_rapid"],
            )
        )

    return transformed


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


class AptConverter(BaseConverter):
    """Converter for CATIA APT source files to :class:`~trajcenter.core.trajectory.Trajectory`.

    Parses all ``GOTO`` instructions in a ``.aptsource`` file, taking
    into account ``RAPID`` (→ ``MoveJ``) and ``FEDRAT`` (→ ``MoveL``)
    modifiers.

    The tool name is extracted from the ``TPRINT`` directive when present,
    otherwise ``defaults.tool`` is used.

    Attributes:
        defaults: Default values used for autocompletion.
        apply_catia_transform: When ``True``, applies the CATIA
            transformation matrix if present at the top of the file.
            Defaults to ``False``.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.apt_converter import AptConverter

            traj = AptConverter().convert(Path("Pointage.aptsource"))
            traj.save("trajectory_store/Pointage.trajcenter")
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        apply_catia_transform: bool = False,
    ) -> None:
        """Initialise the APT converter.

        Args:
            defaults: Default values used for autocompletion.
            apply_catia_transform: Apply the CATIA matrix if present.
                Defaults to ``False``.
        """
        super().__init__(defaults)
        self.apply_catia_transform: bool = apply_catia_transform

    def convert(self, source: Path) -> Trajectory:
        """Convert a ``.aptsource`` file to a :class:`~trajcenter.core.trajectory.Trajectory`.

        Args:
            source: Path to the ``.aptsource`` file to convert.

        Returns:
            A valid, complete, unsaved
            :class:`~trajcenter.core.trajectory.Trajectory` object.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If no ``GOTO`` instruction is found in the file.
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        lines: Sequence[str] = source.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()

        # --- Optional CATIA matrix ---
        catia_matrix: np.ndarray | None = None
        if self.apply_catia_transform:
            catia_matrix = _parse_catia_matrix(lines)
            if catia_matrix is None:
                warnings.warn(
                    f"{source.name}: apply_catia_transform=True but no CATIA "
                    f"matrix found — raw coordinates preserved.",
                    UserWarning,
                    stacklevel=2,
                )

        # --- Parsing: GOTO + tool name ---
        raw_points, tool_name = self._parse_lines(lines)

        if not raw_points:
            raise ValueError(f"No GOTO instruction found in: {source}")

        # --- Optional transformation ---
        if catia_matrix is not None:
            raw_points = _apply_transform(raw_points, catia_matrix)

        # --- Vector → quaternion conversion + DataFrame construction ---
        rows: list[dict[str, float | str]] = []
        for pt in raw_points:
            q1, q2, q3, q4 = _tool_vector_to_quaternion(pt["i"], pt["j"], pt["k"])
            move_type = (
                MoveType.MOVE_J.value if pt["is_rapid"] else MoveType.MOVE_L.value
            )
            rows.append(
                {
                    "x": pt["x"],
                    "y": pt["y"],
                    "z": pt["z"],
                    "q1": q1,
                    "q2": q2,
                    "q3": q3,
                    "q4": q4,
                    "move_type": move_type,
                }
            )

        df = pd.DataFrame(rows)

        # --- tools / wobjs tables ---
        # The APT tool (TPRINT) is registered as tools[0].
        # No wobj in APT format → defaults.wobj.
        tools: list[str] = [tool_name or self.defaults.tool]
        wobjs: list[str] = [self.defaults.wobj]

        df, autocompleted = self._autocomplete(df, tools, wobjs)

        meta = TrajectoryMeta(
            name=source.stem,
            source_file=source.name,
            source_format=SourceFormat.APT,
            autocompleted=autocompleted,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_lines(
        lines: Sequence[str],
    ) -> tuple[list[_RawPoint], str | None]:
        """Iterate over lines and extract GOTO points and the tool name.

        State machine for ``move_type``:

        - ``RAPID``  → next GOTO will be ``MoveJ`` (non-modal)
        - ``FEDRAT`` → resets mode to ``MoveL``
        - ``GOTO``   → creates a point, resets ``is_rapid`` to ``False``
        - ``TPRINT`` → captures the tool name (first occurrence only)

        Args:
            lines: Raw lines from the APT file.

        Returns:
            Tuple ``(raw_points, tool_name)`` where ``tool_name`` is the
            name extracted from ``TPRINT``, or ``None`` if absent.
        """
        points: list[_RawPoint] = []
        is_rapid: bool = False
        tool_name: str | None = None

        for line in lines:
            # --- TPRINT: tool name (first occurrence only) ---
            if tool_name is None:
                m_tprint = _RE_TPRINT.match(line)
                if m_tprint:
                    tool_name = m_tprint.group(1).strip()
                    continue

            # --- RAPID: non-modal ---
            if _RE_RAPID.match(line):
                is_rapid = True
                continue

            # --- FEDRAT: reset rapid mode ---
            if _RE_FEDRAT.match(line):
                is_rapid = False
                continue

            # --- GOTO: trajectory point ---
            m = _RE_GOTO.match(line)
            if m:
                points.append(
                    _RawPoint(
                        x=float(m.group(1)),
                        y=float(m.group(2)),
                        z=float(m.group(3)),
                        i=float(m.group(4)),
                        j=float(m.group(5)),
                        k=float(m.group(6)),
                        is_rapid=is_rapid,
                    )
                )
                is_rapid = False  # non-modal: reset after consumption

        return points, tool_name
