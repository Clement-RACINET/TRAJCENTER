"""Conversion menu for the simple TrajCenter terminal UI."""

from __future__ import annotations

from pathlib import Path

from trajcenter.cli.main import infer_converter
from trajcenter.ui.config import UIConfig

VALID_INPUT_FORMATS = frozenset(
    {
        "",
        "auto",
        "csv",
        "excel",
        "xlsx",
        "apt",
        "rapid",
        "mod",
    }
)


def run_conversion_menu(config: UIConfig) -> None:
    """Run the conversion submenu."""
    while True:
        print()
        print("File conversion / trajectory store")
        print("----------------------------------")
        print(f"Store: {config.store}")
        print()
        print("1. List .trajcenter files")
        print("2. Convert a file to .trajcenter")
        print("b. Back")
        print()

        choice = input("Choice > ").strip().lower()

        if choice == "1":
            _list_trajcenter_files(config)
        elif choice == "2":
            _convert_file_interactive(config)
        elif choice in {"b", "back"}:
            return
        else:
            print("Invalid choice.")


def _list_trajcenter_files(config: UIConfig) -> None:
    """List .trajcenter files from the configured store."""
    store = config.store

    if not store.exists():
        print(f"Store does not exist: {store}")
        return

    files = sorted(store.glob("*.trajcenter"))

    if not files:
        print(f"No .trajcenter files found in: {store}")
        return

    print()
    print("Available .trajcenter files:")
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}")


def _print_supported_input_formats() -> None:
    """Print supported input formats."""
    print("Supported input formats:")
    print("  auto  : detect from file extension")
    print("  csv   : CSV or text table (.csv, .txt)")
    print("  excel : Excel workbook (.xlsx, .xlsm, .xls)")
    print("  xlsx  : alias for excel")
    print("  apt   : APT source file (.apt, .aptsource)")
    print("  mod   : ABB RAPID module (.mod)")
    print("  rapid : alias for mod")


def _prompt_input_format() -> str | None:
    """Ask the user for the input format."""
    print()
    _print_supported_input_formats()
    print()

    format_text = input("Format [auto] > ").strip().lower()

    if format_text not in VALID_INPUT_FORMATS:
        valid_values = ", ".join(
            sorted(value for value in VALID_INPUT_FORMATS if value)
        )
        msg = (
            f"Unsupported input format: {format_text}. "
            f"Expected one of: {valid_values}, or leave empty for auto."
        )
        raise ValueError(msg)

    if format_text in {"", "auto"}:
        return None

    return format_text


def _confirm_conversion(
    *,
    source: Path,
    dest_dir: Path,
    name: str | None,
    format_name: str | None,
) -> bool:
    """Ask the user to confirm conversion."""
    print()
    print("Conversion summary")
    print("------------------")
    print(f"Source      : {source}")
    print(f"Destination : {dest_dir}")
    print(f"Output name : {name or source.stem}")
    print(f"Format      : {format_name or 'auto'}")
    print()

    answer = input("Convert now? [Y/n] > ").strip().lower()

    return answer in {"", "y", "yes"}


def _convert_file_interactive(config: UIConfig) -> None:
    """Ask the user for conversion parameters and convert a source file."""
    print()
    print("Convert a file to .trajcenter")
    print("-----------------------------")
    print()

    _print_supported_input_formats()
    print()

    source_text = input("Source file path > ").strip().strip('"')
    if not source_text:
        print("Conversion cancelled: no source file provided.")
        return

    source = Path(source_text)

    if not source.exists():
        print(f"Error: source file does not exist: {source}")
        return

    if not source.is_file():
        print(f"Error: source path is not a file: {source}")
        return

    default_dest = config.store
    dest_text = input(f"Destination store [{default_dest}] > ").strip().strip('"')
    dest_dir = Path(dest_text) if dest_text else default_dest

    default_name = source.stem
    name_text = input(f"Output name [{default_name}] > ").strip()
    name = name_text or None

    try:
        format_name = _prompt_input_format()
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    if not _confirm_conversion(
        source=source,
        dest_dir=dest_dir,
        name=name,
        format_name=format_name,
    ):
        print("Conversion cancelled.")
        return

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)

        converter = infer_converter(source, format_name)
        output = converter.convert_and_save(
            source=source,
            dest_dir=dest_dir,
            stem=name,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return

    print()
    print(f"Created: {output}")
