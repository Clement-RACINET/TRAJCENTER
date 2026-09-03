# trajcenter/cli/main.py
"""TrajCenter command line interface.

This module intentionally uses only the Python standard library so that the
base ``trajcenter`` command works without optional CLI dependencies.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from trajcenter.convert import AptConverter, CsvConverter, ExcelConverter, ModConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.export import CsvExporter, ExcelExporter
from trajcenter.rws.models import TrajectoryStoreEntry
from trajcenter.rws.store import scan_trajectory_store

APP_NAME = "trajcenter"
DEFAULT_STORE = Path("trajectory_store")
CSV_EXTENSIONS = {".csv", ".txt"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
APT_EXTENSIONS = {".apt", ".aptsource"}
RAPID_EXTENSIONS = {".mod"}


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
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert a source trajectory file to a .trajcenter archive.",
        description="Convert a source trajectory file to a .trajcenter archive.",
    )
    convert_parser.add_argument(
        "source",
        type=Path,
        help="Source file to convert (.csv, .xlsx, .xlsm, .xls, .apt, .aptsource, .mod).",
    )
    convert_parser.add_argument(
        "dest_dir",
        type=Path,
        help="Destination directory for the produced .trajcenter archive.",
    )
    convert_parser.add_argument(
        "--name",
        help="Optional output archive stem. Defaults to the source file stem.",
    )
    convert_parser.add_argument(
        "--format",
        choices=["csv", "excel", "xlsx", "apt", "rapid", "mod"],
        help="Optional source format override. By default, the format is inferred.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Export a .trajcenter archive to CSV or Excel.",
        description="Export a .trajcenter archive to CSV or Excel.",
    )
    export_parser.add_argument(
        "source",
        type=Path,
        help="Source .trajcenter archive.",
    )
    export_parser.add_argument(
        "dest_dir",
        type=Path,
        help="Destination directory for exported files.",
    )
    export_parser.add_argument(
        "--format",
        choices=["csv", "excel", "xlsx"],
        default="csv",
        help="Export format. Default: csv.",
    )

    store_parser = subparsers.add_parser(
        "store",
        help="Inspect local .trajcenter trajectory stores.",
        description="Inspect local .trajcenter trajectory stores.",
    )
    store_subparsers = store_parser.add_subparsers(
        dest="store_command",
        metavar="STORE_COMMAND",
    )

    store_list_parser = store_subparsers.add_parser(
        "list",
        help="List local .trajcenter archives.",
        description="List local .trajcenter archives.",
    )
    store_list_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )

    store_inspect_parser = store_subparsers.add_parser(
        "inspect",
        help="Inspect one local .trajcenter archive by name, filename or index.",
        description="Inspect one local .trajcenter archive by name, filename or index.",
    )
    store_inspect_parser.add_argument(
        "name",
        help=(
            "Trajectory to inspect. Accepts metadata name, archive filename, "
            "archive stem or one-based store index."
        ),
    )
    store_inspect_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )

    return parser


def format_store_entry(entry: TrajectoryStoreEntry) -> str:
    """Format one trajectory store entry as a compact table row.

    Args:
        entry: Store entry to format.

    Returns:
        Formatted row string.
    """
    return (
        f"{entry.index:>3}  "
        f"{entry.name:<32}  "
        f"{entry.point_count:>6}  "
        f"{entry.process_type:>7}  "
        f"{entry.path.name}"
    )


def print_store_entries(entries: Sequence[TrajectoryStoreEntry]) -> None:
    """Print trajectory store entries as a simple table.

    Args:
        entries: Store entries to print.

    Returns:
        None.
    """
    if not entries:
        print("No .trajcenter archives found.")
        return

    print(f"{'IDX':>3}  {'NAME':<32}  {'POINTS':>6}  {'PROCESS':>7}  FILE")
    print(f"{'-' * 3}  {'-' * 32}  {'-' * 6}  {'-' * 7}  {'-' * 4}")

    for entry in entries:
        print(format_store_entry(entry))


def find_store_entry(
    entries: Sequence[TrajectoryStoreEntry],
    query: str,
) -> TrajectoryStoreEntry:
    """Find one store entry by index, metadata name, filename or stem.

    Args:
        entries: Store entries to search.
        query: User query.

    Returns:
        Matching store entry.

    Raises:
        LookupError: If no entry matches the query or if the query is ambiguous.
    """
    normalized_query = query.casefold()

    if query.isdecimal():
        index = int(query)
        for entry in entries:
            if entry.index == index:
                return entry

    matches = [
        entry
        for entry in entries
        if normalized_query
        in {
            entry.name.casefold(),
            entry.path.name.casefold(),
            entry.path.stem.casefold(),
        }
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        names = ", ".join(f"{entry.index}:{entry.name}" for entry in matches)
        raise LookupError(f"Ambiguous trajectory query '{query}': {names}")

    raise LookupError(f"Trajectory not found in store: {query}")


def print_store_entry_details(entry: TrajectoryStoreEntry) -> None:
    """Print detailed information for one store entry.

    Args:
        entry: Store entry to print.

    Returns:
        None.
    """
    print(f"Index:        {entry.index}")
    print(f"Name:         {entry.name}")
    print(f"Point count:  {entry.point_count}")
    print(f"Process type: {entry.process_type}")
    print(f"File:         {entry.path.name}")
    print(f"Path:         {entry.path}")


def infer_converter(source: Path, format_name: str | None = None):
    """Return a converter instance for a source file.

    Args:
        source: Source file path.
        format_name: Optional explicit source format.

    Returns:
        Converter instance.

    Raises:
        ValueError: If the format is unsupported.
    """
    normalized_format = format_name.casefold() if format_name is not None else None
    suffix = source.suffix.casefold()

    if normalized_format == "csv" or (
        normalized_format is None and suffix in CSV_EXTENSIONS
    ):
        return CsvConverter()

    if normalized_format in {"excel", "xlsx"} or (
        normalized_format is None and suffix in EXCEL_EXTENSIONS
    ):
        return ExcelConverter()

    if normalized_format == "apt" or (
        normalized_format is None and suffix in APT_EXTENSIONS
    ):
        return AptConverter()

    if normalized_format in {"rapid", "mod"} or (
        normalized_format is None and suffix in RAPID_EXTENSIONS
    ):
        return ModConverter()

    supported = ", ".join(
        sorted(CSV_EXTENSIONS | EXCEL_EXTENSIONS | APT_EXTENSIONS | RAPID_EXTENSIONS)
    )
    raise ValueError(
        f"Unsupported source format for {source}. "
        f"Supported extensions: {supported}. "
        "Use --format to override detection."
    )


def infer_exporter(format_name: str):
    """Return an exporter instance for an output format.

    Args:
        format_name: Export format name.

    Returns:
        Exporter instance.

    Raises:
        ValueError: If the format is unsupported.
    """
    normalized_format = format_name.casefold()

    if normalized_format == "csv":
        return CsvExporter()

    if normalized_format in {"excel", "xlsx"}:
        return ExcelExporter()

    raise ValueError(f"Unsupported export format: {format_name}")


def handle_convert_command(args: argparse.Namespace) -> int:
    """Run the ``trajcenter convert`` command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    try:
        converter = infer_converter(args.source, args.format)
        output = converter.convert_and_save(
            source=args.source,
            dest_dir=args.dest_dir,
            stem=args.name,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Created: {output}")
    return 0


def handle_export_command(args: argparse.Namespace) -> int:
    """Run the ``trajcenter export`` command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    try:
        trajectory = Trajectory.load(args.source)
        exporter = infer_exporter(args.format)
        output = exporter.export(trajectory, args.dest_dir)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Exported: {output}")
    return 0


def handle_store_command(args: argparse.Namespace) -> int:
    """Run a ``trajcenter store`` subcommand.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    if args.store_command is None:
        print("Missing store command. Use: trajcenter store --help")
        return 2

    try:
        entries = scan_trajectory_store(args.store)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    if args.store_command == "list":
        print_store_entries(entries)
        return 0

    if args.store_command == "inspect":
        try:
            entry = find_store_entry(entries, args.name)
        except LookupError as exc:
            print(f"Error: {exc}")
            return 1

        print_store_entry_details(entry)
        return 0

    print(f"Unknown store command: {args.store_command}")
    return 2


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

    if args.command == "convert":
        return handle_convert_command(args)

    if args.command == "export":
        return handle_export_command(args)

    if args.command == "store":
        return handle_store_command(args)

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
