#!/usr/bin/env python3
# trajcenter/converter/mod_converter.py
"""Converter for ABB RAPID modules to the TrajCenter v2 format.

Author: Clement RACINET

This module converts ABB RAPID ``.mod`` files containing inline
``MoveL``, ``MoveJ`` or ``MoveC`` instructions into
:class:`trajcenter.core.trajectory.Trajectory`.

TrajCenter v2 RAPID mapping
---------------------------
The converter stores canonical v2 columns:

- RAPID ``v500`` -> ``tcp_speed = 500.0``
- RAPID ``z10`` -> ``zone_type = 10``
- RAPID ``fine`` -> ``zone_type = 255``
- RAPID tool argument -> ``tool_name``
- RAPID ``\\wobj:=...`` argument -> ``wobj_name``

Unresolved RAPID speed or zone variables are not stored. Explicit
converter defaults may still add ``tcp_speed`` or ``zone_type`` through
:class:`trajcenter.converter.defaults.ConversionDefaults`.

ABB Route:
    N/A — local RAPID module parsing, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
    Inactive external axes encoded as ``9E9`` are not stored in
    ``.trajcenter`` files.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.mod_converter import ModConverter

        traj = ModConverter().convert(Path("trajectory.mod"))
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.messages import msg
from trajcenter.core.trajectory import (
    MoveType,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)

_RE_MOVE_TYPE: re.Pattern[str] = re.compile(r"^\s*(MoveL|MoveJ|MoveC)\b", re.IGNORECASE)

_RE_ROBTARGET: re.Pattern[str] = re.compile(
    r"\[\s*"
    r"(\[.*?\]"
    r"\s*,\s*\[.*?\]"
    r"\s*,\s*\[.*?\]"
    r"\s*,\s*\[.*?\])"
    r"\s*\]",
    re.DOTALL,
)

_RE_PARAMS: re.Pattern[str] = re.compile(
    r"\]\]\s*,"
    r"\s*(?P<speed>\S+?)\s*,"
    r"\s*(?P<zone>\w+)\s*,"
    r"\s*(?P<tool>\w+)"
    r"(?:\s*\\[Ww][Oo][Bb][Jj]\s*:=\s*(?P<wobj>\w+))?",
    re.IGNORECASE,
)

_RE_SPEED_LITERAL: re.Pattern[str] = re.compile(
    r"^v(?P<value>\d+(?:[.,]\d+)?)$",
    re.IGNORECASE,
)
_RE_ZONE_LITERAL: re.Pattern[str] = re.compile(r"^z(?P<value>\d+)$", re.IGNORECASE)

_EAX_ACTIVE_THRESHOLD: float = 1e8
_FINE_ZONE_CODE: int = 255
_EAX_COLS: tuple[str, str, str, str, str, str] = (
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
)

_MOVE_TYPE_MAP: dict[str, MoveType] = {
    "movel": MoveType.MOVE_L,
    "movej": MoveType.MOVE_J,
    "movec": MoveType.MOVE_C,
}


class ModConverter(BaseConverter):
    """Converter for ABB RAPID modules.

    Attributes:
        defaults: Optional conversion defaults inherited from
            :class:`trajcenter.converter.base.BaseConverter`.

    ABB Route:
        N/A — local file parsing.

    ABB Constraints:
        No ABB controller access.

    Example:
        ::

            traj = ModConverter().convert(Path("trajectory.mod"))
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the RAPID module converter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            defaults: Optional conversion defaults.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = ModConverter(defaults=ConversionDefaults())
        """
        super().__init__(defaults)

    def convert(self, source: Path) -> Trajectory:
        """Convert a RAPID ``.mod`` file to a trajectory.

        ABB Route:
            N/A — local file conversion.

        ABB Constraints:
            No mastership, no RAPID write.

        Args:
            source: Path to the ``.mod`` file.

        Returns:
            Converted trajectory.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If no Move instruction is found or parsing fails.

        Example:
            ::

                traj = ModConverter().convert(Path("trajectory.mod"))
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=source))

        raw_lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        move_lines = self._extract_move_lines(raw_lines)

        if not move_lines:
            raise ValueError(msg("NO_MOVE_INSTRUCTION", path=source))

        rows = self._parse_move_lines(move_lines, source)
        rows = self._apply_literal_variable_policy(rows)

        points = pd.DataFrame(rows)
        points, autocompleted = self._autocomplete(points)

        meta = TrajectoryMeta(
            name=source.stem,
            source_file=source.name,
            source_format=SourceFormat.RAPID,
            autocompleted=autocompleted,
        )

        return Trajectory(meta=meta, points=points)

    @staticmethod
    def _extract_move_lines(lines: list[str]) -> list[str]:
        """Extract complete Move instructions from RAPID source lines.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            lines: Raw file lines.

        Returns:
            Complete Move instructions without trailing semicolon.

        Raises:
            ValueError: Never intentionally raised.

        Example:
            ::

                moves = ModConverter._extract_move_lines(lines)
        """
        result: list[str] = []
        buffer = ""
        in_move = False

        for line in lines:
            stripped = line.strip()

            if not stripped or stripped.startswith("!"):
                continue

            if not in_move:
                match = _RE_MOVE_TYPE.search(stripped)
                if match is None:
                    continue
                in_move = True
                buffer = stripped[match.start() :]
            else:
                buffer = f"{buffer} {stripped}"

            while ";" in buffer:
                instruction, _, remainder = buffer.partition(";")
                instruction = instruction.strip()
                if instruction:
                    result.append(instruction)

                buffer = remainder.strip()
                match = _RE_MOVE_TYPE.search(buffer)
                if match is None:
                    buffer = ""
                    in_move = False
                else:
                    buffer = buffer[match.start() :]
                    in_move = True

        return result

    def _parse_move_lines(
        self,
        move_lines: list[str],
        source: Path,
    ) -> list[dict[str, str | int | float | None]]:
        """Parse Move instructions into point rows.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            move_lines: Complete Move instructions.
            source: Source path for diagnostics.

        Returns:
            Parsed point rows.

        Raises:
            ValueError: If one Move instruction cannot be parsed.

        Example:
            ::

                rows = converter._parse_move_lines(lines, source)
        """
        rows: list[dict[str, str | int | float | None]] = []

        for line_no, line in enumerate(move_lines, start=1):
            try:
                row = self._parse_single_move(line, line_no)
            except ValueError as exc:
                raise ValueError(
                    f"{source.name} — Move line #{line_no}: {exc}\n"
                    f"  Content: {line[:120]!r}"
                ) from exc
            rows.append(row)

        return rows

    def _parse_single_move(
        self,
        line: str,
        point_idx: int = 0,
    ) -> dict[str, str | int | float | None]:
        """Parse one RAPID Move instruction.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            line: Complete Move instruction.
            point_idx: Point index used for diagnostics.

        Returns:
            Point row dictionary.

        Raises:
            ValueError: If robtarget or parameters cannot be parsed.

        Example:
            ::

                row = converter._parse_single_move(move_line)
        """
        m_type = _RE_MOVE_TYPE.match(line)
        if not m_type:
            raise ValueError("Movement type not found.")
        move_type = _MOVE_TYPE_MAP[m_type.group(1).lower()]

        m_robt = _RE_ROBTARGET.search(line)
        if not m_robt:
            raise ValueError(
                msg("INSTRUCTION_WITHOUT_ROBTARGET", line=point_idx, content=line[:80])
            )

        sublists = re.findall(r"\[([^\[\]]+)\]", m_robt.group(1))
        if len(sublists) < 4:
            raise ValueError(
                f"Malformed robtarget — {len(sublists)} sub-list(s) found, 4 expected."
            )

        try:
            trans = [float(v) for v in sublists[0].split(",")]
            rot = [float(v) for v in sublists[1].split(",")]
            eax = [float(v) for v in sublists[3].split(",")]
        except ValueError as exc:
            raise ValueError(f"Numeric conversion failed in robtarget: {exc}") from exc

        try:
            conf = [int(float(v)) for v in sublists[2].split(",")]
        except ValueError as exc:
            raise ValueError(
                msg("INVALID_CONFDATA", line=point_idx, content=sublists[2])
            ) from exc

        if len(trans) != 3:
            raise ValueError(f"trans must have 3 values, got {len(trans)}.")
        if len(rot) != 4:
            raise ValueError(f"rot must have 4 values, got {len(rot)}.")
        if len(conf) != 4:
            raise ValueError(f"conf must have 4 values, got {len(conf)}.")
        if len(eax) != 6:
            raise ValueError(f"eax must have 6 values, got {len(eax)}.")

        m_params = _RE_PARAMS.search(line)
        if not m_params:
            raise ValueError("Move parameters (speed/zone/tool) not found.")

        speed_raw = m_params.group("speed")
        zone_raw = m_params.group("zone")
        tool_name = m_params.group("tool")
        wobj_name = m_params.group("wobj") or "wobj0"

        row: dict[str, str | int | float | None] = {
            "x": trans[0],
            "y": trans[1],
            "z": trans[2],
            "q1": rot[0],
            "q2": rot[1],
            "q3": rot[2],
            "q4": rot[3],
            "cf1": conf[0],
            "cf4": conf[1],
            "cf6": conf[2],
            "cfx": conf[3],
            "move_type": move_type.value,
            "tool_name": tool_name,
            "wobj_name": wobj_name,
            "_raw_speed": speed_raw,
            "_raw_zone": zone_raw,
        }

        speed = self._parse_speed_literal(speed_raw)
        if speed is not None:
            row["tcp_speed"] = speed

        zone = self._parse_zone_literal(zone_raw)
        if zone is not None:
            row["zone_type"] = zone

        for col, val in zip(_EAX_COLS, eax, strict=True):
            if abs(val) < _EAX_ACTIVE_THRESHOLD:
                row[col] = val

        return row

    @staticmethod
    def _parse_speed_literal(value: str) -> float | None:
        """Parse a RAPID speed literal.

        ABB Route:
            N/A.

        ABB Constraints:
            RAPID variables are not resolved.

        Args:
            value: RAPID speed token.

        Returns:
            Numeric speed for ``vN`` literals, otherwise ``None``.

        Raises:
            ValueError: Never intentionally raised.

        Example:
            ::

                assert ModConverter._parse_speed_literal("v500") == 500.0
        """
        match = _RE_SPEED_LITERAL.fullmatch(value.strip())
        if match is None:
            return None
        return float(match.group("value").replace(",", "."))

    @staticmethod
    def _parse_zone_literal(value: str) -> int | None:
        """Parse a RAPID zone literal.

        ABB Route:
            N/A.

        ABB Constraints:
            RAPID variables are not resolved.

        Args:
            value: RAPID zone token.

        Returns:
            Integer zone code, ``255`` for ``fine``, or ``None`` for
            variables.

        Raises:
            ValueError: Never intentionally raised.

        Example:
            ::

                assert ModConverter._parse_zone_literal("fine") == 255
        """
        text = value.strip()
        if text.casefold() == "fine":
            return _FINE_ZONE_CODE

        match = _RE_ZONE_LITERAL.fullmatch(text)
        if match is None:
            return None

        return int(match.group("value"))

    @staticmethod
    def _apply_literal_variable_policy(
        rows: list[dict[str, str | int | float | None]],
    ) -> list[dict[str, str | int | float | None]]:
        """Apply all-literal/all-variable policy for speed and zone.

        For each of ``tcp_speed`` and ``zone_type``:

        - all rows literal: keep the column;
        - all rows variable: remove the internal raw column and leave
          the canonical column absent;
        - mixed literal/variable: raise ``ValueError``.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            rows: Parsed rows containing internal ``_raw_speed`` and
                ``_raw_zone`` markers.

        Returns:
            Rows cleaned from internal marker columns.

        Raises:
            ValueError: If literals and unresolved variables are mixed.

        Example:
            ::

                rows = ModConverter._apply_literal_variable_policy(rows)
        """
        has_speed = ["tcp_speed" in row for row in rows]
        has_zone = ["zone_type" in row for row in rows]

        if any(has_speed) and not all(has_speed):
            raise ValueError(
                "Mixed RAPID speed literals and unresolved speed variables are not "
                "supported. Use only vN literals or only variables."
            )

        if any(has_zone) and not all(has_zone):
            raise ValueError(
                "Mixed RAPID zone literals and unresolved zone variables are not "
                "supported. Use only zN/fine literals or only variables."
            )

        cleaned: list[dict[str, str | int | float | None]] = []
        for row in rows:
            out = dict(row)
            out.pop("_raw_speed", None)
            out.pop("_raw_zone", None)
            cleaned.append(out)

        return cleaned


def _index_to_list(index: dict[str, int]) -> list[str]:
    """Convert a name-to-index dictionary to an ordered list.

    This helper is kept for backward compatibility with old tests and
    downstream users. It is no longer used by the v2 converter.

    ABB Route:
        N/A.

    ABB Constraints:
        No ABB controller access.

    Args:
        index: Mapping from name to dense integer index.

    Returns:
        Ordered list where ``result[index[name]] == name``.

    Raises:
        IndexError: If an index is outside the dense list range.

    Example:
        ::

            _index_to_list({"Tool_A": 0, "Tool_B": 1})
    """
    result: list[str] = [""] * len(index)
    for name, idx in index.items():
        result[idx] = name
    return result
