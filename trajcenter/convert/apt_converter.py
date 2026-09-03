#!/usr/bin/env python3
# trajcenter/convert/apt_converter.py
"""Converter for CATIA APT source files to the TrajCenter v2 format.

> **Author**: Clément RACINET

This module converts CATIA APT ``.aptsource`` files containing ``GOTO``
instructions into :class:`trajcenter.core.trajectory.Trajectory`.

APT movement logic
------------------
The movement logic intentionally keeps the legacy behaviour:

- ``RAPID`` is non-modal and applies only to the next ``GOTO``.
- A ``GOTO`` following ``RAPID`` is converted to ``MoveJ``.
- Every other ``GOTO`` is converted to ``MoveL``.
- ``FEDRAT`` resets the movement mode to ``MoveL``.

TrajCenter v2 mapping
---------------------
The converter stores canonical v2 columns only:

- APT position ``x, y, z`` -> ``x, y, z``
- APT tool vector ``i, j, k`` -> ABB quaternion ``q1, q2, q3, q4``
- APT ``TPRINT`` -> inline ``tool_name``
- Optional defaults may add ``tcp_speed``, ``zone_type`` or ``wobj_name``

No legacy ``tools`` / ``wobjs`` tables are produced, and no
``tool_index`` / ``wobj_index`` columns are written.

ABB Route:
    N/A — local file conversion, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.

Example:
    ::

        from pathlib import Path
        from trajcenter.convert.apt_converter import AptConverter

        traj = AptConverter().convert(Path("PrepaFlans_Pointage.aptsource"))
        traj.save(Path("PrepaFlans_Pointage.trajcenter"))
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd

from trajcenter.convert.base import BaseConverter
from trajcenter.convert.defaults import ConversionDefaults
from trajcenter.core.trajectory import (
    MoveType,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


class _RawPoint(TypedDict):
    """Raw APT point extracted before quaternion conversion."""

    x: float
    y: float
    z: float
    i: float
    j: float
    k: float
    is_rapid: bool


_RE_GOTO: re.Pattern[str] = re.compile(
    r"^\s*GOTO\s*/\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"
    r"([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_RE_RAPID: re.Pattern[str] = re.compile(r"^\s*RAPID\s*$", re.IGNORECASE)
_RE_FEDRAT: re.Pattern[str] = re.compile(r"^\s*FEDRAT\s*/", re.IGNORECASE)
_RE_TPRINT: re.Pattern[str] = re.compile(r"^\s*TPRINT\s*/\s*(.+)", re.IGNORECASE)
_RE_TPRINT_TOOL_PREFIX: re.Pattern[str] = re.compile(
    r"^\s*T\d+\s+(?P<name>.+?)\s*$",
    re.IGNORECASE,
)


_RE_CATIA_MATRIX_ROW: re.Pattern[str] = re.compile(
    r"^\s*\$\$\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s*$"
)


def _tool_vector_to_quaternion(
    i: float,
    j: float,
    k: float,
) -> tuple[float, float, float, float]:
    """Convert an APT tool vector to an ABB scalar-first quaternion.

    ABB Route:
        N/A — local geometric conversion.

    ABB Constraints:
        The returned quaternion follows ABB RAPID convention
        ``[q1, q2, q3, q4] = [w, x, y, z]``.

    Args:
        i: X component of the APT tool vector.
        j: Y component of the APT tool vector.
        k: Z component of the APT tool vector.

    Returns:
        Tuple ``(q1, q2, q3, q4)`` representing the minimal rotation
        from ``(0, 0, 1)`` to ``(i, j, k)``.

    Raises:
        ValueError: Never intentionally raised.

    Example:
        ::

            q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
    """
    tool = np.array([i, j, k], dtype=np.float64)
    norm = float(np.linalg.norm(tool))
    if norm > 1e-10:
        tool = tool / norm

    z_ref = np.array([0.0, 0.0, 1.0])
    dot = float(np.clip(np.dot(z_ref, tool), -1.0, 1.0))

    if dot >= 1.0 - 1e-10:
        return (1.0, 0.0, 0.0, 0.0)

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
    """Extract a CATIA 3x4 transformation matrix from APT comments.

    ABB Route:
        N/A — local file parsing.

    ABB Constraints:
        No ABB controller access.

    Args:
        lines: Raw APT file lines.

    Returns:
        Homogeneous ``(4, 4)`` matrix when three CATIA matrix rows are
        found, otherwise ``None``.

    Raises:
        ValueError: Never intentionally raised.

    Example:
        ::

            matrix = _parse_catia_matrix(lines)
    """
    matrix_rows: list[list[float]] = []

    for line in lines:
        stripped = line.strip()

        if not stripped.startswith("$$") and not stripped.upper().startswith("PARTNO"):
            if matrix_rows:
                break
            continue

        match = _RE_CATIA_MATRIX_ROW.match(stripped)
        if match:
            matrix_rows.append([float(match.group(group)) for group in range(1, 5)])
            if len(matrix_rows) == 3:
                break
        elif matrix_rows:
            break

    if len(matrix_rows) != 3:
        return None

    matrix = np.eye(4, dtype=np.float64)
    for row_idx, row in enumerate(matrix_rows):
        matrix[row_idx, :3] = row[:3]
        matrix[row_idx, 3] = row[3]

    return matrix


def _apply_transform(
    points: list[_RawPoint],
    matrix: np.ndarray,
) -> list[_RawPoint]:
    """Apply a homogeneous CATIA transform to APT points.

    ABB Route:
        N/A — local geometric conversion.

    ABB Constraints:
        Translation is applied only to positions. Tool vectors receive
        only the rotation part of the matrix.

    Args:
        points: Raw APT points.
        matrix: Homogeneous ``(4, 4)`` transformation matrix.

    Returns:
        Transformed raw APT points.

    Raises:
        ValueError: Never intentionally raised.

    Example:
        ::

            transformed = _apply_transform(points, matrix)
    """
    rotation = matrix[:3, :3]
    transformed: list[_RawPoint] = []

    for point in points:
        pos = np.array([point["x"], point["y"], point["z"], 1.0])
        new_pos = matrix @ pos

        vec = np.array([point["i"], point["j"], point["k"]])
        new_vec = rotation @ vec

        transformed.append(
            _RawPoint(
                x=float(new_pos[0]),
                y=float(new_pos[1]),
                z=float(new_pos[2]),
                i=float(new_vec[0]),
                j=float(new_vec[1]),
                k=float(new_vec[2]),
                is_rapid=point["is_rapid"],
            )
        )

    return transformed


def _normalise_tprint_tool_name(value: str) -> str:
    """Normalise a CATIA APT TPRINT tool label.

    CATIA APT commonly emits labels such as ``TPRINT/T1 PointeurD10``.
    In this form, ``T1`` is a tool identifier prefix and the useful
    TrajCenter/RAPID inline tool name is ``PointeurD10``.

    The prefix is removed only when it matches ``T`` followed by digits
    and at least one whitespace before a non-empty remaining name.

    ABB Route:
        N/A — local APT parsing.

    ABB Constraints:
        No ABB controller access.

    Args:
        value: Raw value extracted after ``TPRINT/``.

    Returns:
        Normalised tool name.

    Raises:
        ValueError: Never intentionally raised.

    Example:
        ::

            name = _normalise_tprint_tool_name("T1 PointeurD10")
    """
    cleaned = value.strip()
    match = _RE_TPRINT_TOOL_PREFIX.fullmatch(cleaned)
    if match is None:
        return cleaned
    return match.group("name").strip()


class AptConverter(BaseConverter):
    """Converter for CATIA APT source files.

    ABB Route:
        N/A — local file parsing.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        defaults: Optional conversion defaults inherited from
            :class:`trajcenter.convert.base.BaseConverter`.
        apply_catia_transform: Whether to apply the CATIA matrix when
            present.

    Example:
        ::

            traj = AptConverter(apply_catia_transform=True).convert(path)
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        apply_catia_transform: bool = False,
    ) -> None:
        """Initialise the APT converter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            defaults: Optional conversion defaults.
            apply_catia_transform: Apply CATIA transformation matrix
                when present.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = AptConverter(apply_catia_transform=True)
        """
        super().__init__(defaults)
        self.apply_catia_transform = apply_catia_transform

    def convert(self, source: Path) -> Trajectory:
        """Convert an APT source file to a TrajCenter trajectory.

        ABB Route:
            N/A — local file conversion.

        ABB Constraints:
            No mastership, no RAPID read/write.

        Args:
            source: Path to the ``.aptsource`` file.

        Returns:
            Converted trajectory.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If no ``GOTO`` instruction is found.

        Example:
            ::

                traj = AptConverter().convert(Path("file.aptsource"))
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        lines: Sequence[str] = source.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        catia_matrix: np.ndarray | None = None
        if self.apply_catia_transform:
            catia_matrix = _parse_catia_matrix(lines)
            if catia_matrix is None:
                warnings.warn(
                    f"{source.name}: apply_catia_transform=True but no CATIA "
                    "matrix found — raw coordinates preserved.",
                    UserWarning,
                    stacklevel=2,
                )

        raw_points, tool_name = self._parse_lines(lines)

        if not raw_points:
            raise ValueError(f"No GOTO instruction found in: {source}")

        if catia_matrix is not None:
            raw_points = _apply_transform(raw_points, catia_matrix)

        rows: list[dict[str, float | str]] = []
        for point in raw_points:
            q1, q2, q3, q4 = _tool_vector_to_quaternion(
                point["i"],
                point["j"],
                point["k"],
            )
            move_type = (
                MoveType.MOVE_J.value if point["is_rapid"] else MoveType.MOVE_L.value
            )

            row: dict[str, float | str] = {
                "x": point["x"],
                "y": point["y"],
                "z": point["z"],
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "q4": q4,
                "move_type": move_type,
            }

            if tool_name is not None:
                row["tool_name"] = tool_name

            rows.append(row)

        points = pd.DataFrame(rows)
        points, autocompleted = self._autocomplete(points)

        meta = TrajectoryMeta(
            name=source.stem,
            source_file=source.name,
            source_format=SourceFormat.APT,
            autocompleted=autocompleted,
        )

        return Trajectory(meta=meta, points=points)

    @staticmethod
    def _parse_lines(
        lines: Sequence[str],
    ) -> tuple[list[_RawPoint], str | None]:
        """Extract raw GOTO points and the optional TPRINT tool name.

        ABB Route:
            N/A — local APT parsing.

        ABB Constraints:
            No ABB controller access.

        Args:
            lines: Raw APT file lines.

        Returns:
            Tuple ``(points, tool_name)``. ``tool_name`` is ``None`` when
            no ``TPRINT`` directive exists.

        Raises:
            ValueError: Never intentionally raised.

        Example:
            ::

                points, tool_name = AptConverter._parse_lines(lines)
        """
        points: list[_RawPoint] = []
        is_rapid = False
        tool_name: str | None = None

        for line in lines:
            if tool_name is None:
                tprint_match = _RE_TPRINT.match(line)
                if tprint_match:
                    tool_name = _normalise_tprint_tool_name(tprint_match.group(1))
                    continue

            if _RE_RAPID.match(line):
                is_rapid = True
                continue

            if _RE_FEDRAT.match(line):
                is_rapid = False
                continue

            goto_match = _RE_GOTO.match(line)
            if goto_match:
                points.append(
                    _RawPoint(
                        x=float(goto_match.group(1)),
                        y=float(goto_match.group(2)),
                        z=float(goto_match.group(3)),
                        i=float(goto_match.group(4)),
                        j=float(goto_match.group(5)),
                        k=float(goto_match.group(6)),
                        is_rapid=is_rapid,
                    )
                )
                is_rapid = False

        return points, tool_name
