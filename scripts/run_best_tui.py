#!/usr/bin/env python3
"""Run TrajCenter TUI from the best already-installed Pixi environment."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PREFERRED_ENVS: tuple[str, ...] = (
    "full",
    "tui",
    "default",
)


def get_project_root() -> Path:
    """Return the repository root from this script location."""
    return Path(__file__).resolve().parents[1]


def get_clean_env() -> dict[str, str]:
    """Return a cleaned environment for subprocess execution."""
    env = os.environ.copy()

    ssl_cert_dir = env.get("SSL_CERT_DIR")
    if ssl_cert_dir and not Path(ssl_cert_dir).exists():
        env.pop("SSL_CERT_DIR", None)

    return env


def get_candidate_python_paths(project_root: Path, env_name: str) -> tuple[Path, ...]:
    """Return possible Python executable paths for a Pixi environment.

    Pixi layouts may differ depending on platform/version.

    On your Windows setup, Python is located at:
        .pixi/envs/<env>/python.exe

    Some environments may also expose:
        .pixi/envs/<env>/Scripts/python.exe
    """
    env_dir = project_root / ".pixi" / "envs" / env_name

    if os.name == "nt":
        return (
            env_dir / "python.exe",
            env_dir / "Scripts" / "python.exe",
        )

    return (
        env_dir / "bin" / "python",
        env_dir / "python",
    )


def get_env_python_if_installed(project_root: Path, env_name: str) -> Path | None:
    """Return Python executable if the Pixi environment is already installed."""
    for python_path in get_candidate_python_paths(project_root, env_name):
        if python_path.exists():
            return python_path

    return None


def python_can_import_textual(python_exe: Path, project_root: Path) -> bool:
    """Return whether the given Python executable can import Textual."""
    result = subprocess.run(
        [
            str(python_exe),
            "-c",
            "import textual",
        ],
        cwd=project_root,
        env=get_clean_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    return result.returncode == 0


def choose_best_env(project_root: Path) -> tuple[str, Path] | None:
    """Choose the best already-installed Pixi environment for the TUI.

    Preference order:
        1. full
        2. tui
        3. default

    Environments are not created by this function.
    """
    for env_name in PREFERRED_ENVS:
        python_exe = get_env_python_if_installed(project_root, env_name)

        if python_exe is None:
            continue

        if python_can_import_textual(python_exe, project_root):
            return env_name, python_exe

    return None


def main() -> int:
    """Run TrajCenter TUI using the best already-installed Pixi environment."""
    project_root = get_project_root()
    selected = choose_best_env(project_root)

    if selected is None:
        print(
            "[TrajCenter] No installed Pixi environment can run the TUI.\n"
            "\n"
            "Install one of these environments first:\n"
            "  pixi install -e full\n"
            "  pixi install -e tui\n"
            "\n"
            "Then run:\n"
            "  pixi run trajcenter-tui"
        )
        return 1

    env_name, python_exe = selected

    command = [
        str(python_exe),
        "-m",
        "trajcenter.cli.main",
        "tui",
        *sys.argv[1:],
    ]

    print(f"[TrajCenter] Using Pixi environment: {env_name}")
    print(f"[TrajCenter] Python: {python_exe}")

    return subprocess.call(
        command,
        cwd=project_root,
        env=get_clean_env(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
