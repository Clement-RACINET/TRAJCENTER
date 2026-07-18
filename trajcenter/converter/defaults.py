#!/usr/bin/env python3
# trajcenter/converter/defaults.py
"""Optional conversion defaults for TrajCenter v2 converters.

Author: Clement RACINET

This module defines :class:`ConversionDefaults`, the configuration model
used by converters when the caller explicitly requests column
autocompletion.

TrajCenter v2 principle
-----------------------
Converters should preserve source data by default. They must not invent
robot/process values silently.

Autocompletion is therefore opt-in through
:attr:`ConversionDefaults.autocomplete_columns`.

For example, importing an APT file without defaults keeps only source
geometry and source-derived information. If the user wants to re-export
the trajectory to Excel and edit process values locally, selected columns
can be added explicitly.

ABB Route:
    N/A — local conversion configuration.

ABB Constraints:
    No ABB controller access. Values are not written to RAPID variables.
    The inactive external axis sentinel ``9E+9`` must never be configured
    or stored here.

Example:
    ::

        defaults = ConversionDefaults(
            autocomplete_columns={"tcp_speed", "zone_type"},
            tcp_speed=300.0,
            zone_type=10,
        )
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


_AUTOCOMPLETE_ALLOWED_COLUMNS: frozenset[str] = frozenset(
    {
        "cf1",
        "cf4",
        "cf6",
        "cfx",
        "move_type",
        "readconfs",
        "tcp_speed",
        "zone_type",
        "tool_name",
        "wobj_name",
    }
)


class ConversionDefaults(BaseModel):
    """Optional default values for explicit converter autocompletion.

    Autocompletion is disabled by default. A value is injected only when
    its column name is present in :attr:`autocomplete_columns`.

    Attributes:
        autocomplete_columns: Canonical column names to create when
            absent from the converted source.
        cf_value: Default value for ``cf1``, ``cf4``, ``cf6`` and ``cfx``.
        move_type: Default movement type, for example ``"MoveL"``.
        readconfs: Default RAPID ``ConfL``/configuration flag.
        tcp_speed: Default numeric TCP speed.
        zone_type: Default integer zone code. ``255`` represents ``fine``.
        tool_name: Default inline RAPID tool name.
        wobj_name: Default inline RAPID workobject name.

    ABB Route:
        N/A — local conversion configuration.

    ABB Constraints:
        Defaults are local file values only. No controller access is made.

    Example:
        ::

            defaults = ConversionDefaults(
                autocomplete_columns={"zone_type"},
                zone_type=10,
            )
    """

    autocomplete_columns: set[str] = Field(
        default_factory=set,
        description=(
            "Canonical columns to autocomplete when absent. Empty set means "
            "no optional autocompletion."
        ),
    )
    cf_value: int = Field(
        0,
        description="Default value for cf1, cf4, cf6 and cfx.",
    )
    move_type: str | None = Field(
        None,
        description="Default movement type, e.g. 'MoveL'.",
    )
    readconfs: bool | None = Field(
        None,
        description="Default read/configuration flag.",
    )
    tcp_speed: float | None = Field(
        None,
        description="Default numeric TCP speed.",
    )
    zone_type: int | None = Field(
        None,
        description="Default zone code. Use 255 for fine.",
    )
    tool_name: str | None = Field(
        None,
        description="Default inline RAPID tool name.",
    )
    wobj_name: str | None = Field(
        None,
        description="Default inline RAPID workobject name.",
    )

    @field_validator("autocomplete_columns")
    @classmethod
    def _validate_autocomplete_columns(cls, value: set[str]) -> set[str]:
        """Validate explicitly requested autocompletion columns.

        ABB Route:
            N/A — local Pydantic validation.

        ABB Constraints:
            External axes and RWS-only sentinels cannot be requested here.

        Args:
            value: Requested column names.

        Returns:
            Validated column names.

        Raises:
            ValueError: If an unsupported column is requested.

        Example:
            ::

                ConversionDefaults(autocomplete_columns={"zone_type"})
        """
        invalid = sorted(value - _AUTOCOMPLETE_ALLOWED_COLUMNS)
        if invalid:
            allowed = ", ".join(sorted(_AUTOCOMPLETE_ALLOWED_COLUMNS))
            raise ValueError(
                f"Unsupported autocomplete column(s): {invalid}. "
                f"Allowed columns: {allowed}."
            )
        return value
