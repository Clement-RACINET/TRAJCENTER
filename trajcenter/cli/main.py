# trajcenter/cli/main.py
"""TrajCenter command line interface.

This module intentionally uses only the Python standard library so that the
base ``trajcenter`` command works without optional CLI dependencies.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

APP_NAME = "trajcenter"


def get_package_version() -> str:
    """Return the installed TrajCenter package version.

    Returns:
        Installed package version, or ``unknown`` if package metadata cannot be
        found.
    """
    try:
        return version("trajcenter")
    except PackageNotFoundError:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    """Build the TrajCenter command-line parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="TrajCenter command line interface.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
    )

    subparsers.add_parser(
        "version",
        help="Show the installed TrajCenter version.",
        description="Show the installed TrajCenter version.",
    )

    return parser


def run_command(args: argparse.Namespace) -> int:
    """Run the parsed TrajCenter command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    if args.command == "version":
        print(f"{APP_NAME} {get_package_version()}")
        return 0

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TrajCenter CLI.

    Args:
        argv: Optional command-line arguments. If ``None``, arguments are read
            from ``sys.argv``.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
