#!/usr/bin/env python3
# trajcenter/converter/base.py
"""Abstract base class shared by all TrajCenter converters.

Author: Clement RACINET

A converter transforms a source file (RAPID ``.mod``, Excel, APT, …)
into a :class:`~trajcenter.core.trajectory.Trajectory` object that is
**always complete** and ready to be saved as ``.trajcenter``.

Autocompletion principle
-------------------------
The :meth:`BaseConverter._autocomplete` method guarantees that all
columns listed in
:data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` are present in
the ``DataFrame`` before the trajectory is constructed.
Missing columns are filled with values from
:class:`~trajcenter.converter.defaults.ConversionDefaults`, and their
names are returned so they can be stored in
:attr:`~trajcenter.core.trajectory.TrajectoryMeta.autocompleted`.

``eax_*`` columns are **never** autocompleted — their absence means
the axis does not exist on that robot.

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
    """Base converter from a source file to a :class:`~trajcenter.core.trajectory.Trajectory`.

    All subclasses must implement :meth:`convert`.
    The utility methods :meth:`_autocomplete` and
    :meth:`convert_and_save` are provided by this base class.

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
            defaults: Default values for autocompletion.
                When ``None``,
                :class:`~trajcenter.converter.defaults.ConversionDefaults`
                is instantiated with its own default values.
        """
        self.defaults: ConversionDefaults = defaults or ConversionDefaults()

    @abstractmethod
    def convert(self, source: Path) -> Trajectory:
        """Convert a source file into a :class:`~trajcenter.core.trajectory.Trajectory`.

        The returned trajectory must be **complete**: all columns listed
        in :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` must be
        present (guaranteed by calling :meth:`_autocomplete`).

        Args:
            source: Path to the source file to convert.

        Returns:
            A valid, complete, unsaved
            :class:`~trajcenter.core.trajectory.Trajectory` object.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the file is invalid or malformed.
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
        """Fill missing columns with values from ``self.defaults``.

        Iterates over :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS`
        and adds each absent column using the corresponding value from
        :attr:`defaults`. ``eax_*`` columns are never touched.

        If ``tools`` is empty, a default tool (``defaults.tool``) is
        appended to the list and ``tool_index`` is autocompleted to ``0``.
        The same logic applies to ``wobjs`` / ``wobj_index``.

        Args:
            df: Partially filled ``DataFrame`` (after source parsing).
            tools: List of tool names built by the converter.
                Modified **in place** when empty.
            wobjs: List of wobj names built by the converter.
                Modified **in place** when empty.

        Returns:
            Tuple ``(df_complete, autocompleted)`` where:

            - ``df_complete``: ``DataFrame`` with all columns present.
            - ``autocompleted``: list of column names that were inferred
              (not present in the source).
        """
        df = df.copy()
        autocompleted: list[str] = []
        n = len(df)

        # --- Empty tools / wobjs tables → default ---
        if not tools:
            tools.append(self.defaults.tool)
        if not wobjs:
            wobjs.append(self.defaults.wobj)

        # --- Column → fill value mapping (strings only) ---
        # confdata columns are handled separately (nullable Int8)
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

        Args:
            source: Path to the source file.
            dest_dir: Destination directory (created if absent).
            stem: Output filename without extension.
                Defaults to the source file stem.

        Returns:
            Absolute path to the created ``.trajcenter`` file.

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
