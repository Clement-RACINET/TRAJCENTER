#!/usr/bin/env python3
# trajcenter/converter/defaults.py
"""Default values applied during conversion to ``.trajcenter``.

Author: Clement RACINET

This module defines :class:`ConversionDefaults`, the Pydantic model that
centralises all values used to fill columns absent from a source file
(CSV, Excel, APT, …).

Principle
----------
At the output of any converter, the ``.trajcenter`` file is **always
complete**: all columns listed in
:data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` are present.
If a column is absent from the source, its value is inferred from
:class:`ConversionDefaults` and its name is added to
:attr:`~trajcenter.core.trajectory.TrajectoryMeta.autocompleted`.

This model is **independent of the target cell**: it describes generic
RAPID names and values, not a physical configuration.

Example:
    Using standard default values::

        from trajcenter.converter.defaults import ConversionDefaults

        d = ConversionDefaults()
        print(d.move_type)  # "MoveJ"
        print(d.speed)      # "v10"

    Override for a slow approach trajectory::

        d = ConversionDefaults(speed="v100", zone="fine", move_type="MoveJ")
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversionDefaults(BaseModel):
    """Default values applied to absent columns during conversion.

    All fields have a sensible default value. They can be overridden
    when instantiating the converter or passed as arguments to the
    conversion method.

    Attributes:
        move_type: Default RAPID movement type.
            Accepted values: ``"MoveL"``, ``"MoveJ"``, ``"MoveC"``.
        speed: Default RAPID speed (e.g. ``"v500"``).
            Must be a valid RAPID identifier (``speeddata``).
        zone: Default RAPID zone (e.g. ``"z10"``).
            Must be a valid RAPID identifier (``zonedata``).
        tool: Default RAPID tool name (e.g. ``"tool0"``).
            Used to build ``tools[0]`` when no tool is present in the
            source.
        wobj: Default RAPID work-object name (e.g. ``"wobj0"``).
            Used to build ``wobjs[0]`` when no wobj is present in the
            source.
        cf_value: Integer value applied to the four confdata columns
            (``cf1``, ``cf4``, ``cf6``, ``cfx``) when absent.
            ``0`` corresponds to configuration ``[0, 0, 0, 0]``
            (conf off — robot in unconstrained configuration).

    Example:
        ::

            from trajcenter.converter.defaults import ConversionDefaults

            # Standard values
            d = ConversionDefaults()

            # Override for a finishing trajectory
            d_finish = ConversionDefaults(speed="v200", zone="fine")
    """

    move_type: str = Field(
        "MoveJ",
        description=("Default RAPID movement type: 'MoveL', 'MoveJ' or 'MoveC'."),
    )
    speed: str = Field(
        "v10",
        description=("Default RAPID speed (speeddata). E.g.: 'v500', 'v1000'."),
    )
    zone: str = Field(
        "z10",
        description=("Default RAPID zone (zonedata). E.g.: 'z0', 'z10', 'fine'."),
    )
    tool: str = Field(
        "tool0",
        description=(
            "Default RAPID tool name. Used when no tool is found in the source."
        ),
    )
    wobj: str = Field(
        "wobj0",
        description=(
            "Default RAPID work-object name. Used when no wobj is found in the source."
        ),
    )
    cf_value: int = Field(
        0,
        description=(
            "Default confdata value applied to cf1, cf4, cf6, cfx. "
            "0 = unconstrained configuration (conf off)."
        ),
    )
