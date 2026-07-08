# trajcenter/converter/defaults.py

"""
Valeurs par défaut appliquées lors de la conversion vers ``.trajcenter``.

Ce module définit :class:`ConversionDefaults`, le modèle Pydantic qui
centralise toutes les valeurs utilisées pour compléter les colonnes
absentes d'un fichier source (CSV, Excel, APT…).

Principe
---------
À la sortie de n'importe quel convertisseur, le ``.trajcenter`` est
**toujours complet** : toutes les colonnes de
:data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` sont présentes.
Si une colonne est absente dans la source, sa valeur est inférée depuis
:class:`ConversionDefaults` et son nom est ajouté à
:attr:`~trajcenter.core.trajectory.TrajectoryMeta.autocompleted`.

Ce modèle est **indépendant de la cellule cible** : il décrit des noms
et valeurs RAPID génériques, pas une configuration physique.

Example:
    Utilisation avec les valeurs par défaut standard::

        from trajcenter.converter.defaults import ConversionDefaults

        d = ConversionDefaults()
        print(d.move_type)  # "MoveL"
        print(d.speed)      # "v500"

    Surcharge pour une trajectoire d'approche lente::

        d = ConversionDefaults(speed="v100", zone="fine", move_type="MoveJ")
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversionDefaults(BaseModel):
    """Valeurs par défaut appliquées aux colonnes absentes lors de la conversion.

    Tous les champs ont une valeur par défaut raisonnable.
    Ils peuvent être surchargés à l'instanciation du convertisseur
    ou passés en argument à la méthode de conversion.

    Attributes:
        move_type: Type de mouvement RAPID par défaut.
                   Valeurs acceptées : ``"MoveL"``, ``"MoveJ"``, ``"MoveC"``.
        speed:     Vitesse RAPID par défaut (ex. ``"v500"``).
                   Doit être un identifiant RAPID valide (``speeddata``).
        zone:      Zone RAPID par défaut (ex. ``"z10"``).
                   Doit être un identifiant RAPID valide (``zonedata``).
        tool:      Nom du tool RAPID par défaut (ex. ``"tool0"``).
                   Utilisé pour construire ``tools[0]`` si aucun tool
                   n'est présent dans la source.
        wobj:      Nom du wobj RAPID par défaut (ex. ``"wobj0"``).
                   Utilisé pour construire ``wobjs[0]`` si aucun wobj
                   n'est présent dans la source.
        cf_value:  Valeur entière appliquée aux quatre colonnes confdata
                   (``cf1``, ``cf4``, ``cf6``, ``cfx``) si absentes.
                   ``0`` correspond à la configuration ``[0,0,0,0]``
                   (conf off — robot en configuration non contrainte).

    Example:
        ::

            from trajcenter.converter.defaults import ConversionDefaults

            # Valeurs standard
            d = ConversionDefaults()

            # Surcharge pour trajectoire de finition
            d_finish = ConversionDefaults(speed="v200", zone="fine")
    """

    move_type: str = Field(
        "MoveJ",
        description="Type de mouvement RAPID par défaut : 'MoveL', 'MoveJ' ou 'MoveC'.",
    )
    speed: str = Field(
        "v10",
        description="Vitesse RAPID par défaut (speeddata). Ex. : 'v500', 'v1000'.",
    )
    zone: str = Field(
        "z10",
        description="Zone RAPID par défaut (zonedata). Ex. : 'z0', 'z10', 'fine'.",
    )
    tool: str = Field(
        "tool0",
        description="Nom du tool RAPID par défaut. Utilisé si aucun tool trouvé dans la source.",
    )
    wobj: str = Field(
        "wobj0",
        description="Nom du wobj RAPID par défaut. Utilisé si aucun wobj trouvé dans la source.",
    )
    cf_value: int = Field(
        0,
        description=(
            "Valeur confdata par défaut appliquée à cf1, cf4, cf6, cfx. "
            "0 = configuration non contrainte (conf off)."
        ),
    )
