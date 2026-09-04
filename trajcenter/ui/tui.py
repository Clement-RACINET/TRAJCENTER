#!/usr/bin/env python3
"""Compatibility entry point for the TrajCenter TUI."""

from __future__ import annotations

from trajcenter.ui.app import TrajCenterTUI
from trajcenter.ui.config import UIConfig


def run_tui(*, config: UIConfig | None = None) -> int:
    """Run the TrajCenter Textual TUI.

    Args:
        config: Optional UI configuration.

    Returns:
        Process exit code.
    """
    app = TrajCenterTUI(config=config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_tui())
