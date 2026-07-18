#!/usr/bin/env python3
# trajcenter/converter/tabular_converter.py
"""Abstract tabular converter shared by Excel and CSV converters.

Author: Clement RACINET

This module factors all tabular data conversion logic into the abstract
class :class:`_TabularConverter`.

Subclasses only implement :meth:`_TabularConverter._read_sheets`, which
returns a ``dict[str, pandas.DataFrame]``, and the
:attr:`_TabularConverter._source_format` property.

TrajCenter v2 import policy
---------------------------
The internal v2 schema stores machine-oriented canonical columns:

- ``tcp_speed`` as numeric TCP speed
- ``zone_type`` as integer zone code
- ``tool_name`` as inline RAPID tool name
- ``wobj_name`` as inline RAPID work-object name

For migration convenience, CSV and Excel imports still accept RAPID-like
human literals:

- ``v500`` -> ``tcp_speed = 500.0``
- ``z10`` -> ``zone_type = 10``
- ``fine`` -> ``zone_type = 255``

Reserved Excel sheets
---------------------
The legacy ``tools`` and ``wobjs`` sheets are ignored by v2. Tool and
work-object references are now carried directly by the point columns
``tool_name`` and ``wobj_name``.

ABB Route:
    N/A — local file conversion, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
    The RWS inactive-axis sentinel ``9E+9`` must not be stored in
    ``.trajcenter`` files.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.csv_converter import CsvConverter

        traj = CsvConverter().convert(Path("trajectory.csv"))
"""

from __future__ import annotations

import math
import re
import warnings
from abc import abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.column_mapper import resolve_columns
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.messages import msg
from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta

_SHEET_TOOLS: frozenset[str] = frozenset({"tools", "tool"})
_SHEET_WOBJS: frozenset[str] = frozenset({"wobjs", "wobj"})
_SHEET_META: frozenset[str] = frozenset({"meta", "metadata"})
_SHEET_RESERVED: frozenset[str] = _SHEET_TOOLS | _SHEET_WOBJS | _SHEET_META

_REQUIRED_COLS: frozenset[str] = frozenset({"x", "y", "z"})

_IDENTITY_QUATERNION: dict[str, float] = {
    "q1": 1.0,
    "q2": 0.0,
    "q3": 0.0,
    "q4": 0.0,
}

_SHEET_DEFAULT_NAMES: frozenset[str] = frozenset(
    {
        "feuil1",
        "sheet1",
        "traj",
        "trajectoire",
        "sheet",
    }
)

_META_APPLICABLE_FIELDS: frozenset[str] = frozenset({"name", "robot_model"})

_META_IGNORED_FIELDS: frozenset[str] = frozenset(
    {
        "source_format",
        "autocompleted",
        "created_at",
        "version",
        "point_count",
        "source_file",
    }
)

_SPEED_LITERAL_RE = re.compile(r"^v(?P<value>\d+(?:[.,]\d+)?)$", re.IGNORECASE)
_ZONE_LITERAL_RE = re.compile(r"^z(?P<value>-?\d+)$", re.IGNORECASE)
_FINE_ZONE_CODE = 255


class _TabularConverter(BaseConverter):
    """Abstract base for tabular CSV and Excel converters.

    Args:
        defaults: Autocompletion defaults. ``None`` uses the built-in
            :class:`~trajcenter.converter.defaults.ConversionDefaults`.

    ABB Route:
        N/A — local tabular conversion.

    ABB Constraints:
        No ABB controller access.

    Example:
        ::

            converter = CsvConverter()
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
    ) -> None:
        """Initialise the tabular converter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            defaults: Optional autocompletion defaults.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = CsvConverter(defaults=ConversionDefaults())
        """
        super().__init__(defaults=defaults)

    @property
    @abstractmethod
    def _source_format(self) -> SourceFormat:
        """Return the source format tag.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            None.

        Returns:
            Source format value stamped in trajectory metadata.

        Raises:
            NotImplementedError: If a subclass does not implement it.

        Example:
            ::

                fmt = converter._source_format
        """
        ...

    @abstractmethod
    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read a tabular source into sheet DataFrames.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            source: Source file path.

        Returns:
            Mapping of sheet names to raw DataFrames.

        Raises:
            FileNotFoundError: If source does not exist.
            ValueError: If the source cannot be parsed.

        Example:
            ::

                sheets = converter._read_sheets(Path("trajectory.xlsx"))
        """
        ...

    def convert(self, source: Path) -> Trajectory:
        """Convert a source file to a single trajectory.

        ABB Route:
            N/A — local file conversion.

        ABB Constraints:
            No RAPID write and no mastership acquisition.

        Args:
            source: Source CSV or Excel file.

        Returns:
            Converted trajectory.

        Raises:
            FileNotFoundError: If source does not exist.
            ValueError: If mandatory columns are missing or multiple
                trajectory sheets are present.

        Example:
            ::

                traj = CsvConverter().convert(Path("trajectory.csv"))
        """
        if not source.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=source))

        sheets = self._read_sheets(source)
        meta_overrides = self._extract_meta(sheets)
        traj_sheets = {
            name: df
            for name, df in sheets.items()
            if name.lower() not in _SHEET_RESERVED
        }

        if len(traj_sheets) > 1:
            raise ValueError(
                f"Multiple trajectory sheets found: {list(traj_sheets)}. "
                f"Use convert_all() to convert each sheet separately."
            )

        if not traj_sheets:
            raise ValueError("No trajectory sheet found.")

        sheet_name, df = next(iter(traj_sheets.items()))
        return self._build_trajectory(
            df=df,
            sheet_name=sheet_name,
            source=source,
            meta_overrides=meta_overrides,
        )

    def convert_all(self, source: Path) -> list[Trajectory]:
        """Convert all trajectory sheets from a source file.

        ABB Route:
            N/A — local file conversion.

        ABB Constraints:
            No RAPID write and no mastership acquisition.

        Args:
            source: Source CSV or Excel file.

        Returns:
            List of converted trajectories.

        Raises:
            FileNotFoundError: If source does not exist.
            ValueError: If a trajectory sheet is invalid.

        Example:
            ::

                trajectories = ExcelConverter().convert_all(Path("multi.xlsx"))
        """
        if not source.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=source))

        sheets = self._read_sheets(source)
        meta_overrides = self._extract_meta(sheets)

        return [
            self._build_trajectory(
                df=df,
                sheet_name=sheet_name,
                source=source,
                meta_overrides=meta_overrides,
            )
            for sheet_name, df in sheets.items()
            if sheet_name.lower() not in _SHEET_RESERVED
        ]

    def _build_trajectory(
        self,
        df: pd.DataFrame,
        sheet_name: str,
        source: Path,
        meta_overrides: dict[str, str],
    ) -> Trajectory:
        """Build one trajectory from one tabular DataFrame.

        ABB Route:
            N/A — local DataFrame conversion.

        ABB Constraints:
            No RAPID write and no mastership acquisition.

        Args:
            df: Raw sheet DataFrame.
            sheet_name: Sheet name used for naming and diagnostics.
            source: Source file path.
            meta_overrides: Metadata extracted from a ``meta`` sheet.

        Returns:
            Converted trajectory.

        Raises:
            ValueError: If mandatory XYZ columns are missing or if
                RAPID literals cannot be normalised.

        Example:
            ::

                traj = converter._build_trajectory(df, "traj", source, {})
        """
        points = df.dropna(how="all").reset_index(drop=True)
        points, unknown = resolve_columns(points)

        if unknown:
            warnings.warn(
                msg("UNKNOWN_COLUMNS", cols=unknown),
                UserWarning,
                stacklevel=3,
            )

        missing = sorted(_REQUIRED_COLS - set(points.columns))
        if missing:
            raise ValueError(
                msg("SHEET_MANDATORY_COLUMNS_MISSING", sheet=sheet_name, cols=missing)
            )

        quat_autocompleted: list[str] = []
        for qcol, qval in _IDENTITY_QUATERNION.items():
            if qcol not in points.columns:
                points[qcol] = qval
                quat_autocompleted.append(qcol)

        points = self._normalise_tabular_values(points)

        points, autocompleted = self._autocomplete(points)
        autocompleted = quat_autocompleted + autocompleted

        stem = source.stem
        sheet_lower = sheet_name.lower()
        name = stem if sheet_lower in _SHEET_DEFAULT_NAMES else f"{stem}_{sheet_name}"
        if "name" in meta_overrides:
            name = meta_overrides["name"]

        meta = TrajectoryMeta(
            name=name,
            source_format=self._source_format,
            source_file=source.name,
            robot_model=meta_overrides.get("robot_model"),
            autocompleted=autocompleted,
            extra={
                k: v
                for k, v in meta_overrides.items()
                if k not in _META_APPLICABLE_FIELDS and k not in _META_IGNORED_FIELDS
            },
        )
        return Trajectory(meta=meta, points=points)

    @classmethod
    def _normalise_tabular_values(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise imported RAPID-like tabular values to v2 storage.

        ABB Route:
            N/A — local DataFrame transformation.

        ABB Constraints:
            RAPID literals are parsed but no controller access is made.

        Args:
            df: DataFrame with canonical column names.

        Returns:
            DataFrame with normalised ``tcp_speed`` and ``zone_type``
            columns when present.

        Raises:
            ValueError: If a non-empty speed or zone literal is invalid.

        Example:
            ::

                out = _TabularConverter._normalise_tabular_values(df)
        """
        out = df.copy()

        if "tcp_speed" in out.columns:
            out["tcp_speed"] = out["tcp_speed"].map(cls._parse_tcp_speed)
            out["tcp_speed"] = out["tcp_speed"].astype("float64")

        if "zone_type" in out.columns:
            out["zone_type"] = out["zone_type"].map(cls._parse_zone_type)
            out["zone_type"] = out["zone_type"].astype(pd.Int16Dtype())

        if "readconfs" in out.columns:
            out["readconfs"] = out["readconfs"].map(cls._parse_bool_like)
            out["readconfs"] = out["readconfs"].astype("boolean")

        return out

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        """Return whether a tabular cell value is empty.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            value: Cell value.

        Returns:
            ``True`` when the value should be treated as empty.

        Raises:
            TypeError: If pandas scalar inspection fails.

        Example:
            ::

                assert _TabularConverter._is_empty_value("")
        """
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        if pd.isna(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    @classmethod
    def _parse_tcp_speed(cls, value: Any) -> float | None:
        """Parse a TCP speed value.

        Accepted examples are ``500``, ``500.0`` and ``"v500"``.

        ABB Route:
            N/A.

        ABB Constraints:
            This parser does not resolve RAPID variables such as
            ``vitesse`` because no controller access is available.

        Args:
            value: Raw tabular value.

        Returns:
            Numeric TCP speed or ``None`` for empty cells.

        Raises:
            ValueError: If the value cannot be converted.

        Example:
            ::

                assert _TabularConverter._parse_tcp_speed("v500") == 500.0
        """
        if cls._is_empty_value(value):
            return None

        if isinstance(value, int | float):
            return float(value)

        text = str(value).strip()
        match = _SPEED_LITERAL_RE.fullmatch(text)
        if match is not None:
            return float(match.group("value").replace(",", "."))

        try:
            return float(text.replace(",", "."))
        except ValueError as exc:
            raise ValueError(
                f"Invalid tcp_speed value {value!r}. Expected numeric value "
                "or RAPID literal such as 'v500'."
            ) from exc

    @classmethod
    def _parse_zone_type(cls, value: Any) -> int | None:
        """Parse a zone type value.

        Accepted examples are ``10``, ``"z10"`` and ``"fine"``.
        ``"fine"`` is stored as ``255``.

        ABB Route:
            N/A.

        ABB Constraints:
            This parser does not resolve RAPID zone variables because no
            controller access is available.

        Args:
            value: Raw tabular value.

        Returns:
            Integer zone code or ``None`` for empty cells.

        Raises:
            ValueError: If the value cannot be converted.

        Example:
            ::

                assert _TabularConverter._parse_zone_type("fine") == 255
        """
        if cls._is_empty_value(value):
            return None

        if isinstance(value, int):
            return int(value)

        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError(f"Invalid zone_type value {value!r}.")
            return int(value)

        text = str(value).strip()
        if text.casefold() == "fine":
            return _FINE_ZONE_CODE

        match = _ZONE_LITERAL_RE.fullmatch(text)
        if match is not None:
            return int(match.group("value"))

        try:
            zone = float(text.replace(",", "."))
        except ValueError as exc:
            raise ValueError(
                f"Invalid zone_type value {value!r}. Expected integer, "
                "'fine' or RAPID literal such as 'z10'."
            ) from exc

        if not zone.is_integer():
            raise ValueError(f"Invalid zone_type value {value!r}.")
        return int(zone)

    @classmethod
    def _parse_bool_like(cls, value: Any) -> bool | None:
        """Parse a boolean-like tabular value.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            value: Raw tabular value.

        Returns:
            Boolean value or ``None`` for empty cells.

        Raises:
            ValueError: If the value cannot be interpreted as boolean.

        Example:
            ::

                assert _TabularConverter._parse_bool_like("true") is True
        """
        if cls._is_empty_value(value):
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, int | float):
            if float(value) == 1.0:
                return True
            if float(value) == 0.0:
                return False

        text = str(value).strip().casefold()
        if text in {"true", "t", "yes", "y", "oui", "o", "1"}:
            return True
        if text in {"false", "f", "no", "n", "non", "0"}:
            return False

        raise ValueError(f"Invalid readconfs value {value!r}.")

    @staticmethod
    def _extract_meta(sheets: dict[str, pd.DataFrame]) -> dict[str, str]:
        """Extract key/value metadata from a meta sheet.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            sheets: All read sheets.

        Returns:
            Metadata dictionary.

        Raises:
            ValueError: Never intentionally raised; malformed meta sheets
                are ignored.

        Example:
            ::

                meta = _TabularConverter._extract_meta(sheets)
        """
        for sheet_name, df in sheets.items():
            if sheet_name.lower() in _SHEET_META:
                if "key" in df.columns and "value" in df.columns:
                    return dict(
                        zip(
                            df["key"].astype(str),
                            df["value"].astype(str),
                            strict=False,
                        )
                    )
        return {}
