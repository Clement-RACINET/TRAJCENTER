"""Configuration du pipeline documentaire TrajCenter."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


@dataclass(frozen=True)
class DocConfig:
    project_root: Path
    mkdocs_path: Path
    docs_src_dir: Path
    docs_api_dir: Path

    # Scan
    packages_to_scan: list[str] = field(default_factory=lambda: ["trajcenter"])
    exclude_dirs: set[str] = field(default_factory=lambda: {
        "__pycache__", ".pytest_cache", ".git", ".pixi",
        "trajcenter.egg-info",
    })
    exclude_files: list[str] = field(default_factory=lambda: [
        "__init__.py", "test_*.py"
    ])

    # Balises mkdocs.yml
    balise_api_debut: str = "# --- AUTOGEN_API_START ---"
    balise_api_fin:   str = "# --- AUTOGEN_API_END ---"


def build_config() -> DocConfig:
    return DocConfig(
        project_root = PROJECT_ROOT,
        mkdocs_path  = PROJECT_ROOT / "mkdocs.yml",
        docs_src_dir = PROJECT_ROOT / "docs",
        docs_api_dir = PROJECT_ROOT / "docs" / "api",
    )
