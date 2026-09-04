"""Configuration model for the simple TrajCenter terminal UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class UIConfig:
    """Configuration shared by UI menus."""

    store: Path = Path("trajectory_store")
    env_file: Path | None = None
    env_override: bool = False

    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    password_env: str | None = None
    timeout: float | None = None

    task: str = "T_ROB1"
    module: str = "TRAJCENTER"
    mastership_retries: int = 3
    log_level: str = "INFO"
