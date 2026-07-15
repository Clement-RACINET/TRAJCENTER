#!/usr/bin/env python3
# trajcenter/converter/base.py
"""Abstract base class for all TrajCenter converters.

Author: Clement RACINET

A converter transforms a source file (RAPID ``.mod``, Excel, APT …)
into a :class:`~trajcenter.core.trajectory.Trajectory` that is
**always complete** and ready to be saved as ``.trajcenter``.

Autocompletion principle
-------------------------
:meth:`BaseConverter._autocomplete` guarantees that all columns in
:data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` are present in
the ``DataFrame`` before the trajectory is constructed.  Missing
columns are filled with values from
:class:`~trajcenter.converter.defaults.ConversionDefaults` and their
names are returned for storage in
:attr:`~trajcenter.core.trajectory.TrajectoryMeta.autocompleted`.

The ``eax_*`` columns are **never** autocompleted — their absence
means the axis does not exist on this robot.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.mod_converter import ModConverter
        from trajcenter.converter.defaults import ConversionDefaults

        converter = ModConverter()
        traj = converter.convert(Path("trajectory_files/soudure.mod"))
        traj.save("trajectory_store/soudure.trajcenter")

        # With custom defaults
        converter_slow = ModConverter(
            defaults=ConversionDefaults(speed="v100", zone="fine")
        )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import CONFDATA_COLUMNS, CONVERTER_COLUMNS, Trajectory


class BaseConverter(ABC):
    """Abstract base for all source-file converters.

    All subclasses must implement :meth:`convert`.  The utility methods
    :meth:`_autocomplete` and :meth:`convert_and_save` are provided by
    this base class.

    Attributes:
        defaults: Default values used for autocompletion.

    Example:
        ::

            from trajcenter.converter.mod_converter import ModConverter
            from trajcenter.converter.defaults import ConversionDefaults

            traj = ModConverter(
                defaults=ConversionDefaults(speed="v200", zone="fine")
            ).convert(Path("trajectory_files/soudure.mod"))
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the converter with optional default values.

        Args:
            defaults: Autocompletion defaults. When ``None``,
                :class:`~trajcenter.converter.defaults.ConversionDefaults`
                is instantiated with its own built-in values.
        """
        self.defaults: ConversionDefaults = defaults or ConversionDefaults()

    @abstractmethod
    def convert(self, source: Path) -> Trajectory:
        """Convert a source file into a :class:`~trajcenter.core.trajectory.Trajectory`.

        The returned trajectory must be **complete**: all columns in
        :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` must be
        present (guaranteed by a call to :meth:`_autocomplete`).

        ABB Route:
            N/A — local file conversion, no RWS call.

        ABB Constraints:
            None.

        Args:
            source: Path to the source file to convert.

        Returns:
            Valid, complete, unsaved
            :class:`~trajcenter.core.trajectory.Trajectory`.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the file is invalid or malformed.

        Example:
            ::

                traj = ModConverter().convert(Path("soudure.mod"))
        """
        ...

    # ------------------------------------------------------------------
    # Autocompletion
    # ------------------------------------------------------------------

    def _autocomplete(
        self,
        df: pd.DataFrame,
        tools: list[str],
        wobjs: list[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        """Fill missing converter columns with default values.

        Iterates over :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS`
        and adds each absent column with the corresponding value from
        :attr:`defaults`.  Columns already present are **never**
        overwritten.  ``eax_*`` columns are never added.

        If *tools* is empty, ``defaults.tool`` is appended in-place and
        ``tool_index`` is autocompleted to ``0``.  Same logic applies
        to *wobjs* / ``wobj_index``.

        Confdata columns (``cf1``, ``cf4``, ``cf6``, ``cfx``) are
        created as nullable ``pd.Int8Dtype()`` series to support
        ``NaN`` values, unlike ``np.int8``.

        Args:
            df: Partially filled ``DataFrame`` (after source parsing).
                Modified columns are **never** overwritten.
            tools: Tool name list built by the converter.
                Modified **in-place** when empty.
            wobjs: Wobj name list built by the converter.
                Modified **in-place** when empty.

        Returns:
            A tuple ``(completed_df, autocompleted_columns)`` where:

            - ``completed_df`` has all converter columns present.
            - ``autocompleted_columns`` is the sorted list of column
              names that were inferred (not present in the source).

        Example:
            ::

                df_out, autocompleted = converter._autocomplete(df, tools, wobjs)
                # autocompleted → ["cf1", "cf4", "cf6", "cfx", "speed", "zone"]
        """
        df = df.copy()
        autocompleted: list[str] = []
        n = len(df)

        # Populate default tool/wobj tables when empty
        if not tools:
            tools.append(self.defaults.tool)
        if not wobjs:
            wobjs.append(self.defaults.wobj)

        # Typed fill maps — kept separate to satisfy basedpyright
        _fill_str: dict[str, str] = {
            "move_type": self.defaults.move_type,
            "speed": self.defaults.speed,
            "zone": self.defaults.zone,
        }
        _fill_int: dict[str, int] = {
            "tool_index": 0,
            "wobj_index": 0,
        }

        for col in CONVERTER_COLUMNS:
            if col in df.columns:
                continue
            if col in CONFDATA_COLUMNS:
                # Nullable Int8 — pd.Series is the only clean path
                df[col] = pd.Series(
                    [self.defaults.cf_value] * n,
                    dtype=pd.Int8Dtype(),
                )
                autocompleted.append(col)
            elif col in _fill_str:
                df[col] = _fill_str[col]
                autocompleted.append(col)
            elif col in _fill_int:
                df[col] = _fill_int[col]
                autocompleted.append(col)

        return df, autocompleted

    # ------------------------------------------------------------------
    # Convert and save
    # ------------------------------------------------------------------

    def convert_and_save(
        self,
        source: Path,
        dest_dir: Path,
        stem: str | None = None,
    ) -> Path:
        """Convert a source file and save the result as ``.trajcenter``.

        Convenience wrapper around :meth:`convert` and
        :meth:`~trajcenter.core.trajectory.Trajectory.save`.

        ABB Route:
            N/A — local file conversion, no RWS call.

        ABB Constraints:
            None.

        Args:
            source: Path to the source file.
            dest_dir: Destination directory (created if absent).
            stem: Output filename without extension. Defaults to the
                source file stem.

        Returns:
            Absolute path of the created ``.trajcenter`` file.

        Raises:
            FileNotFoundError: If *source* does not exist.
            ValueError: If the source file is invalid.

        Example:
            ::

                path = ModConverter().convert_and_save(
                    source=Path("trajectory_files/soudure.mod"),
                    dest_dir=Path("trajectory_store"),
                )
                # → trajectory_store/soudure.trajcenter
        """
        traj = self.convert(Path(source))
        name = stem or Path(source).stem
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        return traj.save(dest / f"{name}.trajcenter")
