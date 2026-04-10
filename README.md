# TRAJCENTER

Serveur TCP/IP Python permettant d'envoyer des trajectoires robotiques à un robot ABB
sur requête. Le robot joue le rôle de client, Python celui de serveur.

> Projet développé au LCFC (Laboratoire de Conception Fabrication Commande) — ENSAM  

> Auteurs : **Josselin SCHUMACKER** & **Clément RACINET**

> Version : **1.0** — Avril 2024

---

## Description

TRAJCENTER est un serveur TCP/IP écrit en Python qui expose des trajectoires
(points de passage robot) à un client distant qui est un robot ABB programmé en RAPID.

Le serveur lit des fichiers de trajectoires dans différents formats, les charge en mémoire
sous forme de DataFrame, puis les transmet point par point sur requête du robot.
La communication repose sur un protocole de requêtes textuelles simples de la forme :

## Structure du projet 

```bash
TRAJCENTER/
├── server.py                  # Code principal du serveur
├── trajectory_files/          # Dossier contenant les fichiers de trajectoires
│   ├── exemple.xlsx
│   ├── exemple.mod
│   └── ...
└── README.md
```
---

## Fonctionnalités

- Serveur TCP/IP multi-clients avec gestion par threads
- Chargement de trajectoires depuis plusieurs formats de fichiers
- Protocole de requêtes léger et extensible
- Envoi des robtargets encodés en bytes (little-endian, int32)
- Gestion du timeout d'inactivité
- Logs structurés avec niveaux (message / warning / error)

---

## Formats de fichiers supportés

| Extension    | Description                                              |
|--------------|----------------------------------------------------------|
| `.txt`       | Liste de points structurés ligne par ligne (ast.literal_eval) |
| `.xlsx`      | Fichier Excel avec colonnes x, y, z                      |
| `.mod`       | Fichier RAPID ABB contenant des robtargets               |
| `.aptsource` | Fichier APT-CL (GOTO x,y,z,i,j,k)                       |

Les fichiers de trajectoires doivent être placés dans le dossier `trajectory_files/`
situé à la racine du projet.

---

## Protocole de communication

### Requêtes techniques

| Requête              | Arguments        | Réponse                                      |
|----------------------|------------------|----------------------------------------------|
| `nbtraj`             | aucun            | Nombre de trajectoires disponibles (int32)   |
| `nomtraj[n]`         | index (1-based)  | Nom du fichier de la trajectoire n (string)  |
| `loadtraj[n]`        | index (1-based)  | `"loaded"` ou `"error"` (string)             |
| `dimtraj`            | aucun            | Nombre de points de la trajectoire (int32)   |
| `robt[ref;nb]`       | ligne de départ, nombre de points | Paquet de robtargets encodés en bytes |

### Requêtes de service

| Requête              | Effet                                         |
|----------------------|-----------------------------------------------|
| `stop`               | Arrête le serveur proprement                  |
| `closesocket`        | Ferme la connexion du client courant          |
| `closseallsockets`   | Ferme toutes les connexions actives           |


## Prérequis pour installation

- Python 3.8+
- Bibliothèques : 
    - pandas
    - numpy
    - openpyxl
