#!/usr/bin/env python3
# trajcenter/converter/excel_converter.py
"""Converter for Excel files (``.xlsx``, ``.xls``) to ``.trajcenter``.

Author: Clement RACINET

Delegates all conversion logic to
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
This class only implements Excel file reading via ``openpyxl``.

Expected workbook structure
-----------------------------
- **Trajectory sheets**: any sheet whose name is not reserved.
- **Sheet** ``tools``: tool table (``name`` column). Optional.
- **Sheet** ``wobjs``: wobj table (``name`` column). Optional.
- **Sheet** ``meta``: silently ignored.

Mandatory columns: ``x``, ``y``, ``z``.
All other columns are autocompleted from
:class:`~trajcenter.converter.defaults.ConversionDefaults` when absent.
Missing quaternions are replaced by the identity orientation
``[1, 0, 0, 0]``.

Example:
    ::

        traj  = ExcelConverter().convert(Path("data/single.xlsx"))
        trajs = ExcelConverter().convert_all(Path("data/multi.xlsx"))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.tabular_converter import _TabularConverter
from trajcenter.core.trajectory import SourceFormat


class ExcelConverter(_TabularConverter):
    """Converter for Excel workbooks to :class:`~trajcenter.core.trajectory.Trajectory`.

    Inherits from
    :class:`~trajcenter.converter.tabular_converter._TabularConverter`
    for all business logic. Only implements Excel reading.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.excel_converter import ExcelConverter

            traj = ExcelConverter().convert(Path("trajectoires.xlsx"))
            traj.save("trajectory_store/trajectoires.trajcenter")
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the Excel converter.

        Args:
            defaults: Default values for autocompletion.
                When ``None``,
                :class:`~trajcenter.converter.defaults.ConversionDefaults`
                is instantiated with its own default values.
        """
        super().__init__(defaults)

    @property
    def _source_format(self) -> SourceFormat:
        """Source format identifier for this converter.

        Returns:
            :attr:`~trajcenter.core.trajectory.SourceFormat.EXCEL`.
        """
        return SourceFormat.EXCEL

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read all sheets from the Excel workbook.

        Args:
            source: Path to the ``.xlsx`` / ``.xls`` file.

        Returns:
            Ordered dictionary ``{sheet_name: raw_DataFrame}``.
        """
        xl = pd.ExcelFile(source, engine="openpyxl")
        return {
            str(sheet): pd.read_excel(xl, sheet_name=sheet, header=0)
            for sheet in xl.sheet_names
        }
