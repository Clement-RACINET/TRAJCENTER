# scripts/doc/config.py
"""TrajCenter documentation pipeline configuration.

> **Author**: Clément RACINET
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


@dataclass(frozen=True)
class DocConfig:
    """Configuration dataclass for the documentation generation pipeline.

    Attributes:
        project_root: Absolute path to the project root directory.
        mkdocs_path: Path to the ``mkdocs.yml`` configuration file.
        docs_src_dir: Path to the documentation source directory.
        docs_api_dir: Path to the auto-generated API reference directory.
        packages_to_scan: List of Python packages to scan for modules.
        exclude_dirs: Set of directory names to ignore during scanning.
        exclude_files: List of filename patterns to exclude from scanning.
        balise_api_debut: YAML marker indicating the start of the auto-generated API block.
        balise_api_fin: YAML marker indicating the end of the auto-generated API block.
    """

    project_root: Path
    mkdocs_path: Path
    docs_src_dir: Path
    docs_api_dir: Path

    # Scan
    packages_to_scan: list[str] = field(default_factory=lambda: ["trajcenter"])
    exclude_dirs: set[str] = field(
        default_factory=lambda: {
            "__pycache__",
            ".pytest_cache",
            ".git",
            ".pixi",
            "trajcenter.egg-info",
        }
    )
    exclude_files: list[str] = field(
        default_factory=lambda: ["__init__.py", "test_*.py"]
    )

    # mkdocs.yml markers
    balise_api_debut: str = "# --- AUTOGEN_API_START ---"
    balise_api_fin: str = "# --- AUTOGEN_API_END ---"


def build_config() -> DocConfig:
    """Build and return the default documentation pipeline configuration.

    Returns:
        A :class:`DocConfig` instance populated with paths derived from
        the project root.

    Example:
        ::

            cfg = build_config()
            print(cfg.mkdocs_path)  # /path/to/project/mkdocs.yml
    """
    return DocConfig(
        project_root=PROJECT_ROOT,
        mkdocs_path=PROJECT_ROOT / "mkdocs.yml",
        docs_src_dir=PROJECT_ROOT / "docs",
        docs_api_dir=PROJECT_ROOT / "docs" / "api",
    )
