#!/usr/bin/env python3
# trajcenter/converter/defaults.py
"""Default values applied during conversion to ``.trajcenter``.

Author: Clement RACINET

This module defines :class:`ConversionDefaults`, the Pydantic model that
centralises values used to fill selected columns absent from a source
file.

TrajCenter v2 principle
-----------------------
Converters may safely autocomplete only structural robot-target columns:

- ``cf1``, ``cf4``, ``cf6``, ``cfx``
- ``move_type`` when configured

Cell-specific process and send parameters must not be invented by
default. Therefore ``tcp_speed``, ``zone_type``, ``tool_name`` and
``wobj_name`` default to ``None`` and are added only when explicitly
configured.

ABB Route:
    N/A — local conversion defaults, no RWS route.

ABB Constraints:
    These defaults do not acquire mastership and do not write RAPID
    variables. They also must not inject the RWS inactive-axis sentinel
    ``9E+9``.

Example:
    ::

        from trajcenter.converter.defaults import ConversionDefaults

        defaults = ConversionDefaults()
        assert defaults.move_type == "MoveL"
        assert defaults.tcp_speed is None

        defaults_cell = ConversionDefaults(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_formage",
            wobj_name="Wobj_SerreFlan",
        )
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversionDefaults(BaseModel):
    """Default values applied to absent columns during conversion.

    Attributes:
        move_type: Default RAPID movement type. When ``None``,
            ``move_type`` is not autocompleted.
        cf_value: Integer value applied to the four confdata columns
            ``cf1``, ``cf4``, ``cf6`` and ``cfx``.
        readconfs: Optional ABB ``readconf`` flag. Added only when not
            ``None``.
        tcp_speed: Optional TCP speed value. Added only when not
            ``None``.
        zone_type: Optional zone type value. Added only when not
            ``None``.
        tool_name: Optional RAPID tool name. Added only when not
            ``None``.
        wobj_name: Optional RAPID work-object name. Added only when not
            ``None``.

    ABB Route:
        N/A — local conversion defaults.

    ABB Constraints:
        Defaults are metadata only. No RAPID write is performed.

    Raises:
        pydantic.ValidationError: If field types are invalid.

    Example:
        ::

            d = ConversionDefaults(tcp_speed=500.0, zone_type=10)
            assert d.tcp_speed == 500.0
    """

    move_type: str | None = Field(
        "MoveL",
        description=(
            "Default RAPID movement type. Use None to disable move_type autocompletion."
        ),
    )
    cf_value: int = Field(
        0,
        description=(
            "Default confdata value applied to cf1, cf4, cf6 and cfx. "
            "0 = unconstrained configuration."
        ),
    )
    readconfs: bool | None = Field(
        None,
        description="Optional readconf flag. Added only when explicitly configured.",
    )
    tcp_speed: float | None = Field(
        None,
        description="Optional TCP speed. Added only when explicitly configured.",
    )
    zone_type: int | None = Field(
        None,
        description="Optional zone type. Added only when explicitly configured.",
    )
    tool_name: str | None = Field(
        None,
        description="Optional RAPID tool name. Added only when explicitly configured.",
    )
    wobj_name: str | None = Field(
        None,
        description=(
            "Optional RAPID work-object name. Added only when explicitly configured."
        ),
    )
