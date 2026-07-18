#!/usr/bin/env python3
# trajcenter/converter/base.py
"""Abstract base class for all TrajCenter converters.

Author: Clement RACINET

A converter transforms a local source file, such as RAPID ``.mod``,
CSV, Excel or APT, into a
:class:`~trajcenter.core.trajectory.Trajectory`.

TrajCenter v2 autocompletion principle
--------------------------------------
Converters preserve the source by default. They do not invent RAPID,
process or cell-specific values unless the caller explicitly requests
column autocompletion through
:attr:`trajcenter.converter.defaults.ConversionDefaults.autocomplete_columns`.

This enables two workflows:

1. **Faithful import**: keep only source-derived data.
2. **Editable preparation**: explicitly add selected columns, export to
   Excel, edit locally, then re-import.

ABB Route:
    N/A — local file conversion, no RWS route.

ABB Constraints:
    No mastership is acquired here. No RAPID variable is read or written.
    The RWS inactive-axis sentinel ``9E+9`` must not be injected by
    converters.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.defaults import ConversionDefaults
        from trajcenter.converter.apt_converter import AptConverter

        converter = AptConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"tcp_speed", "zone_type"},
                tcp_speed=300.0,
                zone_type=10,
            )
        )
        traj = converter.convert(Path("trajectory_files/path.aptsource"))
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import CONFDATA_COLUMNS, Trajectory


class BaseConverter(ABC):
    """Abstract base for all source-file converters.

    Attributes:
        defaults: Default values used for explicit autocompletion.

    ABB Route:
        N/A — local conversion helper.

    ABB Constraints:
        This class does not communicate with ABB RWS.

    Example:
        ::

            converter = SomeConverter(defaults=ConversionDefaults())
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the converter with optional default values.

        Args:
            defaults: Optional autocompletion defaults. When ``None``,
                autocompletion is disabled.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access is performed.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = SomeConverter(defaults=ConversionDefaults())
        """
        self.defaults: ConversionDefaults = defaults or ConversionDefaults()

    @abstractmethod
    def convert(self, source: Path) -> Trajectory:
        """Convert a source file into a trajectory.

        ABB Route:
            N/A — local file conversion, no RWS route.

        ABB Constraints:
            No RAPID write and no mastership acquisition.

        Args:
            source: Path to the source file to convert.

        Returns:
            Valid unsaved :class:`~trajcenter.core.trajectory.Trajectory`.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the file is invalid or malformed.

        Example:
            ::

                traj = converter.convert(Path("trajectory.mod"))
        """
        ...

    def _autocomplete(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Fill explicitly requested missing columns with default values.

        The method never overwrites existing columns. No column is added
        unless its name is present in
        ``self.defaults.autocomplete_columns``.

        Supported explicit autocompletion columns are:

        - ``cf1``
        - ``cf4``
        - ``cf6``
        - ``cfx``
        - ``move_type``
        - ``readconfs``
        - ``tcp_speed``
        - ``zone_type``
        - ``tool_name``
        - ``wobj_name``

        ``eax_*`` columns and ``process_param_index`` are never added
        here.

        ABB Route:
            N/A — local DataFrame transformation.

        ABB Constraints:
            The method must not infer cell-specific values unless they
            are explicitly requested.

        Args:
            df: Partially filled point DataFrame.

        Returns:
            Tuple ``(completed_df, autocompleted_columns)``.

        Raises:
            ValueError: If a requested column has no configured value.

        Example:
            ::

                df_out, autocompleted = converter._autocomplete(df)
        """
        out = df.copy()
        autocompleted: list[str] = []
        requested = self.defaults.autocomplete_columns
        row_count = len(out)

        for col in sorted(CONFDATA_COLUMNS):
            if col not in requested or col in out.columns:
                continue
            out[col] = pd.Series(
                [self.defaults.cf_value] * row_count,
                dtype=pd.Int8Dtype(),
            )
            autocompleted.append(col)

        optional_values: dict[str, str | int | float | bool | None] = {
            "move_type": self.defaults.move_type,
            "readconfs": self.defaults.readconfs,
            "tcp_speed": self.defaults.tcp_speed,
            "zone_type": self.defaults.zone_type,
            "tool_name": self.defaults.tool_name,
            "wobj_name": self.defaults.wobj_name,
        }

        for col, value in optional_values.items():
            if col not in requested or col in out.columns:
                continue
            if value is None:
                raise ValueError(
                    f"Column {col!r} was requested for autocompletion but "
                    "no default value was configured."
                )
            out[col] = value
            autocompleted.append(col)

        if "readconfs" in autocompleted:
            out["readconfs"] = out["readconfs"].astype("boolean")
        if "tcp_speed" in autocompleted:
            out["tcp_speed"] = out["tcp_speed"].astype("float64")
        if "zone_type" in autocompleted:
            out["zone_type"] = out["zone_type"].astype(pd.Int16Dtype())

        return out, autocompleted

    def convert_and_save(
        self,
        source: Path,
        dest_dir: Path,
        stem: str | None = None,
    ) -> Path:
        """Convert a source file and save it as ``.trajcenter``.

        ABB Route:
            N/A — local conversion and archive serialisation.

        ABB Constraints:
            No RAPID write and no mastership acquisition.

        Args:
            source: Path to the source file.
            dest_dir: Destination directory, created if absent.
            stem: Output filename without extension. Defaults to the
                source file stem.

        Returns:
            Absolute path of the created ``.trajcenter`` file.

        Raises:
            FileNotFoundError: If ``source`` does not exist.
            ValueError: If conversion fails.

        Example:
            ::

                path = converter.convert_and_save(
                    source=Path("trajectory.mod"),
                    dest_dir=Path("trajectory_store"),
                )
        """
        traj = self.convert(Path(source))
        name = stem or Path(source).stem
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        return traj.save(dest / f"{name}.trajcenter")
