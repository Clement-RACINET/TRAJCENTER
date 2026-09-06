#!/usr/bin/env python3
"""Optional feature detection for the TrajCenter TUI."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True, slots=True)
class UIFeatures:
    """Optional TUI feature flags."""

    robot: bool = False
    server: bool = False


def detect_ui_features() -> UIFeatures:
    """Detect optional features available in the current Python environment.

    Returns:
        Detected UI feature flags.
    """
    return UIFeatures(
        robot=is_robot_feature_available(),
        server=is_server_feature_available(),
    )


def is_robot_feature_available() -> bool:
    """Return whether ABB robot support is available."""
    return find_spec("httpx") is not None


def is_server_feature_available() -> bool:
    """Return whether server support is available."""
    return find_spec("fastapi") is not None and find_spec("uvicorn") is not None
