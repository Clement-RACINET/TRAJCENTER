# run_docs.py

"""Orchestrateur : génère la doc API, le rapport coverage, et lance mkdocs serve."""
from __future__ import annotations

import subprocess
import sys

from scripts.doc.config import build_config
from scripts.doc.generate_api import generate_api_docs, update_mkdocs_nav


def _generate_coverage(project_root) -> None:
    """Lance pytest --cov pour produire le rapport HTML dans docs/coverage/."""
    print("\n📊 Génération du rapport coverage...")
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "--cov=trajcenter",
            "--cov-branch",
            "--cov-report=html:docs/coverage",
            "--no-header", "-q",
        ],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("⚠️  Des tests ont échoué — rapport coverage peut être incomplet.")


def main() -> None:
    cfg = build_config()

    nav = generate_api_docs(cfg)
    update_mkdocs_nav(cfg, nav)

    _generate_coverage(cfg.project_root)

    print("\n🚀 Lancement de mkdocs serve...  (Ctrl+C pour arrêter)")
    try:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "serve"],
            cwd=cfg.project_root,
        )
    except KeyboardInterrupt:
        print("\n👋 Serveur arrêté.")
        sys.exit(0)


if __name__ == "__main__":
    main()
