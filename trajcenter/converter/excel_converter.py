#!/usr/bin/env python3
# trajcenter/converter/excel_converter.py
"""Converter for Excel files (``.xlsx``, ``.xls``) to ``.trajcenter``.

> **Author**: Clément RACINET

Delegates all conversion logic to
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
This class only implements Excel workbook reading via ``openpyxl``.

TrajCenter v2 mapping
---------------------
The converter imports tabular trajectory sheets into canonical v2
trajectory columns:

- ``speed`` / ``v500`` / numeric speed aliases -> ``tcp_speed``.
- ``zone`` / ``z10`` -> ``zone_type=10``.
- ``zone`` / ``fine`` -> ``zone_type=255``.
- ``tool`` / tool aliases -> ``tool_name``.
- ``wobj`` / work-object aliases -> ``wobj_name``.

Legacy ``tools`` and ``wobjs`` sheets are ignored. Tool and work-object
names must be stored inline in the trajectory sheet.

Process import
--------------
When a workbook contains an active process, it must provide:

- Sheet ``meta`` with keys ``process_type`` and ``process_param_names``.
- A point column ``process_param_index`` in the trajectory sheet.
- Sheet ``process_params`` with one row per process parameter set.

The process parameter sheet must contain ``process_param_index`` and the
parameter columns listed in ``process_param_names``.

Unmapped columns
----------------
Columns that cannot be mapped to the TrajCenter v2 schema are not stored
in ``Trajectory.points``. A ``UserWarning`` is emitted and their names are
recorded in ``Trajectory.meta.extra["unmapped_columns"]`` for audit.

Expected workbook structure
---------------------------
- Trajectory sheets: any sheet whose name is not reserved.
- Sheet ``meta``: optional key/value metadata sheet.
- Sheet ``process_params``: optional process parameter table.
- Sheets ``tools`` and ``wobjs``: legacy v1 sheets, ignored in v2.

Mandatory columns are ``x``, ``y`` and ``z``.
Missing quaternions are replaced by the identity orientation
``[1, 0, 0, 0]``.

Optional send columns such as ``tcp_speed``, ``zone_type``,
``tool_name`` and ``wobj_name`` are preserved when present or added only
when explicit :class:`~trajcenter.converter.defaults.ConversionDefaults`
values are provided.

ABB Route:
    N/A — local Excel file conversion, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.excel_converter import ExcelConverter

        traj = ExcelConverter().convert(Path("data/single.xlsx"))
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

    The class inherits all v2 tabular conversion rules from
    :class:`~trajcenter.converter.tabular_converter._TabularConverter` and
    only implements Excel sheet loading.

    ABB Route:
        N/A — local Excel file conversion.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        defaults: Optional conversion defaults used only for missing optional
            v2 columns.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.excel_converter import ExcelConverter

            traj = ExcelConverter().convert(Path("trajectoires.xlsx"))
            traj.save("trajectory_store/trajectoires.trajcenter")
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the Excel converter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            defaults: Default values for optional v2 columns. When ``None``,
                no optional send column is added unless present in the source.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = ExcelConverter(defaults=ConversionDefaults())
        """
        super().__init__(defaults)

    @property
    def _source_format(self) -> SourceFormat:
        """Return the source format identifier for Excel imports.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            None.

        Returns:
            :attr:`trajcenter.core.trajectory.SourceFormat.EXCEL`.

        Example:
            ::

                assert converter._source_format == SourceFormat.EXCEL
        """
        return SourceFormat.EXCEL

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read all sheets from an Excel workbook.

        ABB Route:
            N/A — local Excel file read.

        ABB Constraints:
            No ABB controller access.

        Args:
            source: Path to the ``.xlsx`` or ``.xls`` file.

        Returns:
            Dictionary mapping sheet names to raw pandas DataFrames.

        Raises:
            FileNotFoundError: If the workbook path does not exist.
            ValueError: If pandas/openpyxl cannot parse the workbook.

        Example:
            ::

                sheets = converter._read_sheets(Path("trajectory.xlsx"))
        """
        xl = pd.ExcelFile(source, engine="openpyxl")
        return {
            str(sheet): pd.read_excel(xl, sheet_name=sheet, header=0)
            for sheet in xl.sheet_names
        }
