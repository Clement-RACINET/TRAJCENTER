#!/usr/bin/env python3
"""Home actions for the TrajCenter TUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HomeAction:
    """One home menu action."""

    key: str
    label: str
    description: str


HOME_ACTIONS: tuple[HomeAction, ...] = (
    HomeAction(
        key="convert",
        label="Convertir une trajectoire",
        description="Importer un fichier CSV, Excel, APT ou RAPID MOD.",
    ),
    HomeAction(
        key="export",
        label="Exporter une trajectoire",
        description="Exporter une archive .trajcenter vers CSV ou Excel.",
    ),
    HomeAction(
        key="store",
        label="Explorer le store local",
        description="Lister et inspecter les archives .trajcenter disponibles.",
    ),
    HomeAction(
        key="robot",
        label="Démarrer supervision robot ABB",
        description="Lancer la supervision RWS pour transfert vers RAPID.",
    ),
    HomeAction(
        key="settings",
        label="Paramètres",
        description="Configurer le store, les chemins et options par défaut.",
    ),
    HomeAction(
        key="quit",
        label="Quitter",
        description="Fermer TrajCenter.",
    ),
)
