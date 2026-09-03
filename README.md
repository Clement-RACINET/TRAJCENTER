# TRAJCENTER

TrajCenter est une chaîne Python/RAPID permettant de convertir, stocker,
résoudre et transférer des trajectoires industrielles vers un robot ABB
RobotWare 6.x via **Robot Web Services**.

> Projet développé au LCFC — ENSAM  
> Auteurs principaux : Josselin SCHUMAKER & Clément RACINET  
> Robot cible : ABB RobotWare 6.x  
> Transport : ABB Robot Web Services uniquement  
> Version : 2.0

---

## Statut

TrajCenter v2 remplace l’ancien protocole TCP de la v1.

Le flux v2 actuel repose sur :

- des archives locales `.trajcenter` ;
- un **module système RAPID unique** ;
- des lectures/écritures RWS ;
- des subscriptions RWS sur flags RAPID ;
- des écritures protégées par Mastership.

La v2 **n’utilise plus** :

- serveur TCP Python ;
- port custom type `50000` ;
- watchdog TCP ;
- polling nominal côté PC ;
- protocole texte `nbtraj`, `nomtraj`, `loadtraj`, `robt`, etc.

---

## Architecture générale

```text
Robot ABB RAPID
    |
    | RWS subscription events
    v
PC Python TrajCenter supervisor
    |
    | scan / load / resolve
    v
trajectory_store/*.trajcenter
    |
    | RWS writes under Mastership
    v
TRAJCENTER RAPID system module
```

Flux principaux :

| Flux                   | Déclencheur RAPID            | Direction  | Mécanisme              |
| ---------------------- | ---------------------------- | ---------- | ---------------------- |
| Refresh metadata       | `refreshMetaRequest := TRUE` | Robot → PC | RWS subscription       |
| Envoi trajectoire      | `sendTrajRequest := TRUE`    | Robot → PC | RWS subscription       |
| Lecture contexte robot | PC                           | Robot → PC | RWS read               |
| Écriture trajectoire   | PC                           | PC → Robot | RWS write + Mastership |

---

## Structure utile du dépôt

```text
trajcenter/
├── rapid/
│   └── TRAJCENTER.mod
├── scripts/
│   └── run_trajcenter_supervisor.py
├── tests/
│   ├── converter/
│   ├── core/
│   ├── exporter/
│   └── rws/
├── trajcenter/
│   ├── converter/
│   ├── core/
│   ├── exporter/
│   └── rws/
│       ├── reader.py
│       ├── resolver.py
│       ├── writer.py
│       ├── service.py
│       ├── store.py
│       └── supervisor.py
├── trajectory_files/
├── trajectory_store/
├── pyproject.toml
└── README.md
```

---

## Module RAPID v2

Le protocole robot est défini dans un **module système unique** :

```rapid
MODULE TRAJCENTER(SYSMODULE)
```

Fichier :

```text
rapid/TRAJCENTER.mod
```

Il n’y a plus plusieurs modules RAPID à charger dans un ordre particulier.

### Sections internes du module

Le module est organisé en sections de maintenance :

| Section   | Rôle                     | Politique                                                        |
| --------- | ------------------------ | ---------------------------------------------------------------- |
| Section 1 | Types `RECORD`           | Ne pas modifier sauf évolution protocole PC/RAPID                |
| Section 2 | Limites globales         | Ne pas modifier sauf changement volontaire des capacités         |
| Section 3 | Codes d’état et d’erreur | Ne pas modifier sans mettre à jour le PC et la documentation     |
| Section 4 | Types de mouvement       | Ne pas modifier sauf ajout officiel d’un type de mouvement       |
| Section 5 | Process                  | Modifier uniquement ici pour ajouter/retirer/renommer un process |
| Section 6 | Configuration cellule    | Section modifiable pour déclarer tools et wobjs                  |
| Section 7 | Variables RWS            | Ne pas modifier noms/types/dimensions sans mettre à jour le PC   |
| Section 8 | Defaults robot           | Section réglable à la mise en service                            |

### Politique de déclaration RAPID

| Élément                                  | Déclaration RAPID |
| ---------------------------------------- | ----------------- |
| Flags abonnés RWS                        | `PERS`            |
| Tools / wobjs cellule                    | `PERS`            |
| Maintenance tools / wobjs                | `PERS`            |
| Runtime, metadata, trajectoire, defaults | `VAR`             |
| Tailles fixes, codes                     | `CONST`           |

---

## Variables RAPID principales

Module RWS cible :

```text
TRAJCENTER
```

### Requêtes

```rapid
PERS bool sendTrajRequest := FALSE;
PERS bool refreshMetaRequest := FALSE;
VAR num selectedTrajIndex := 0;
```

Convention :

```text
selectedTrajIndex = 0                  aucune sélection
selectedTrajIndex = 1..nbTrajAvailable trajectoire valide
```

### État transfert

```rapid
VAR bool trajReady := FALSE;
VAR bool transferError := FALSE;
VAR num lastErrorCode := statusOk;
VAR string lastError := "";
VAR num transferProgress := 0;
```

| Variable           | Rôle                                          |
| ------------------ | --------------------------------------------- |
| `trajReady`        | trajectoire complète et utilisable côté RAPID |
| `transferError`    | dernier refresh/transfert en erreur           |
| `lastErrorCode`    | code état ou erreur                           |
| `lastError`        | message court                                 |
| `transferProgress` | progression `0..100`                          |

### Metadata store

```rapid
VAR num nbTrajAvailable := 0;
VAR trajCenterTrajMeta trajectories{256};
```

Entrées valides :

```text
trajectories{1..nbTrajAvailable}
```

### Trajectoire chargée

```rapid
VAR num nbLoadedTrajPoints := 0;
VAR trajCenterPointData trajData{100000};
VAR trajCenterProcessParameter processParams{256,10};
```

Entrées valides :

```text
trajData{1..nbLoadedTrajPoints}
processParams{1..256,1..10}
```

---

## Constantes principales

Les constantes protocole sont définies côté RAPID dans `TRAJCENTER`
et côté Python dans `trajcenter/rws/constants.py`.

| Constante                     |   Valeur | Rôle                               |
| ----------------------------- | -------: | ---------------------------------- |
| `maxTrajCount`                |    `256` | nombre max de trajectoires listées |
| `maxTrajPointCount`           | `100000` | nombre max de points transférables |
| `maxProcessParamSetCount`     |    `256` | nombre max de sets process         |
| `maxProcessParamPerSet`       |     `10` | nombre max de paramètres par set   |
| `processNone`                 |      `0` | aucun process                      |
| `processAcf`                  |      `1` | process ACF                        |
| `processAak`                  |      `2` | process AAK                        |
| `processPushcorp`             |      `3` | process PUSHCORP                   |
| `moveTypeL`                   |      `0` | MoveL                              |
| `moveTypeJ`                   |      `1` | MoveJ                              |
| `moveTypeC`                   |      `2` | MoveC                              |
| `statusOk`                    | `200000` | OK                                 |
| `statusMetadataRefreshed`     | `200001` | métadonnées rafraîchies            |
| `statusTrajectoryTransferred` | `200002` | trajectoire transférée             |

---

## Catalogue process

Le catalogue process est déclaré dans le module RAPID `TRAJCENTER`.

Exemple actuel :

```rapid
CONST num processNone := 0;
CONST num processAcf := 1;
CONST num processAak := 2;
CONST num processPushcorp := 3;

CONST num processTypeCount := 4;

VAR trajCenterProcessType processTypes{processTypeCount}:=[
    [processNone, "NONE"],
    [processAcf, "ACF"],
    [processAak, "AAK"],
    [processPushcorp, "PUSHCORP"]
];
```

Pour ajouter un process, modifier uniquement la section `PROCESS` du module RAPID :

1. ajouter une constante process ;
2. incrémenter `processTypeCount` ;
3. ajouter l’entrée dans `processTypes`.

---

## Configuration cellule tools / wobjs

Le module RAPID expose les outils et workobjects disponibles à TrajCenter :

```rapid
PERS trajCenterTool trajTools{N};
PERS trajCenterWobj trajWobjs{M};

PERS tooldata tempTool;
PERS wobjdata tempWobj;
```

Règles :

```text
trajTools/trajWobjs sont cellule-dépendants.
Le PC lit uniquement les champs .name pour résoudre tool_name et wobj_name.
Les index RAPID envoyés sont en base 1.
0 = non défini.
```

Les fichiers `.trajcenter` ne stockent pas de `tooldata` ou `wobjdata` complets.
Ils référencent seulement des noms logiques :

```text
tool_name
wobj_name
```

Le PC résout ensuite ces noms dans :

```text
trajTools
trajWobjs
```

---

## Defaults robot

Les valeurs par défaut sont lues par le PC avant transfert :

```rapid
VAR bool hasDefaultTcpSpeed := FALSE;
VAR num defaultTcpSpeed := 0;

VAR bool hasDefaultZoneType := FALSE;
VAR num defaultZoneType := 255;

VAR bool hasDefaultToolName := FALSE;
VAR string defaultToolName := "";

VAR bool hasDefaultWobjName := FALSE;
VAR string defaultWobjName := "";

VAR num defaultMoveType := moveTypeL;
VAR bool defaultReadConfs := TRUE;
```

Règle importante :

```text
Le PC ne doit jamais inventer silencieusement tool, wobj, speed ou zone.
Fallback uniquement si le hasDefault* correspondant vaut TRUE.
```

Pour `tool_name` et `wobj_name`, le fallback est un **nom** :

```text
defaultToolName -> résolution dans trajTools -> toolIndex
defaultWobjName -> résolution dans trajWobjs -> wobjIndex
```

Ce n’est pas un `tooldata` ou un `wobjdata` directement transféré depuis le fichier `.trajcenter`.

---

## Format `.trajcenter`

Une archive `.trajcenter` est un fichier ZIP contenant au minimum :

```text
meta.json
points.parquet
```

### Colonnes géométriques obligatoires

Pour être exportable et résoluble, une trajectoire doit contenir :

| Colonne | Rôle             |
| ------- | ---------------- |
| `x`     | position ABB X   |
| `y`     | position ABB Y   |
| `z`     | position ABB Z   |
| `q1`    | quaternion ABB w |
| `q2`    | quaternion ABB x |
| `q3`    | quaternion ABB y |
| `q4`    | quaternion ABB z |

### Colonnes envoyables vers le robot

| Colonne                    | Rôle                                       |
| -------------------------- | ------------------------------------------ |
| `cf1`, `cf4`, `cf6`, `cfx` | confdata ABB, valeur `0` si absente        |
| `eax_a..eax_f`             | axes externes optionnels                   |
| `tcp_speed`                | vitesse TCP en mm/s                        |
| `zone_type`                | zone ABB                                   |
| `move_type`                | mouvement `MoveL`, `MoveJ`, `MoveC`        |
| `tool_name`                | nom outil à résoudre dans `trajTools`      |
| `wobj_name`                | nom workobject à résoudre dans `trajWobjs` |
| `readconfs`                | prise en compte confdata                   |
| `process_type`             | process optionnel                          |
| `process_params`           | paramètres process optionnels              |
| `process_param_index`      | ignoré à l’envoi, recalculé côté PC        |

Important :

```text
9E+9 ne doit jamais être stocké dans les fichiers .trajcenter.
```

Les axes externes absents ou NaN sont représentés localement par une absence de
valeur, puis sérialisés en `9E+9` uniquement au moment de l’écriture RWS.

---

## Résolution robot

Avant transfert, TrajCenter lit le contexte robot :

- defaults robot ;
- tools disponibles ;
- wobjs disponibles ;
- catalogue process.

Le resolver produit ensuite une trajectoire complètement résolue :

| Entrée locale | Sortie RAPID                      |
| ------------- | --------------------------------- |
| `tool_name`   | `toolIndex` base 1                |
| `wobj_name`   | `wobjIndex` base 1                |
| `move_type`   | `0`, `1`, `2`                     |
| `zone_type`   | zone ABB autorisée                |
| `tcp_speed`   | `tcpSpeed`                        |
| process local | `processParamIndex` base 1 ou `0` |

Le PC ne doit pas inventer silencieusement :

- outil ;
- workobject ;
- vitesse ;
- zone.

Les valeurs manquantes ne peuvent être complétées que si les defaults robot
correspondants sont explicitement activés côté RAPID.

---

## Zones autorisées

```text
0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 255
```

Convention :

```text
0   = z0
255 = fine
```

---

## Mouvements supportés

| Code | Mouvement | Alias acceptés    |
| ---: | --------- | ----------------- |
|  `0` | `MoveL`   | `L`, `MoveL`, `0` |
|  `1` | `MoveJ`   | `J`, `MoveJ`, `1` |
|  `2` | `MoveC`   | `C`, `MoveC`, `2` |

### MoveC

Encodage :

```text
MoveC = deux points consécutifs C,C
C,C,C,C valide
C,C,C invalide
```

Pour chaque paire `C,C`, doivent être identiques :

```text
tcpSpeed
toolIndex
wobjIndex
zoneType
readConfs
processParamIndex
```

---

## Pipeline refresh metadata

Déclencheur côté RAPID :

```rapid
refreshMetaRequest := TRUE;
```

Traitement PC :

```text
1. Réception de refreshMetaRequest = TRUE par subscription RWS.
2. Scan de trajectory_store/.
3. Chargement des archives .trajcenter.
4. Extraction metadata : nom, nombre de points, type process.
5. Écriture de nbTrajAvailable.
6. Écriture de trajectories{1..nbTrajAvailable}.
7. Écriture état OK.
8. Remise de refreshMetaRequest à FALSE.
```

Les archives sont triées de manière stable côté PC. L’ordre écrit dans
`trajectories` doit rester identique à l’ordre utilisé ensuite pour résoudre
`selectedTrajIndex`.

---

## Pipeline envoi trajectoire

Déclencheur côté RAPID :

```rapid
selectedTrajIndex := k;
sendTrajRequest := TRUE;
```

Traitement PC :

```text
1. Réception de sendTrajRequest = TRUE par subscription RWS.
2. Lecture de selectedTrajIndex.
3. Mapping index RAPID base 1 vers archive locale.
4. Chargement de l’archive .trajcenter.
5. Lecture contexte robot.
6. Résolution trajectoire.
7. Acquisition Mastership.
8. Écriture état initial : trajReady FALSE, transferError FALSE, progress 0.
9. Écriture nbLoadedTrajPoints.
10. Écriture processParams si nécessaire.
11. Écriture trajData{1..nbLoadedTrajPoints}.
12. Mise à jour transferProgress.
13. Écriture état final : progress 100, lastErrorCode 200002, trajReady TRUE.
14. Remise de sendTrajRequest à FALSE.
15. Release Mastership.
```

En erreur :

```text
trajReady = FALSE
transferError = TRUE
lastErrorCode = code erreur
lastError = message court
sendTrajRequest = FALSE
refreshMetaRequest = FALSE si erreur refresh
```

Toute écriture RWS doit être faite sous Mastership avec release garanti.

---

## Supervisor RWS

Le supervisor v2 est dans :

```text
trajcenter/rws/supervisor.py
```

Le script de lancement est :

```text
scripts/run_trajcenter_supervisor.py
```

Il s’abonne aux flags RAPID :

```text
TRAJCENTER/refreshMetaRequest
TRAJCENTER/sendTrajRequest
```

Seuls les events `TRUE` déclenchent une action.

Les events `FALSE` sont ignorés.

Au démarrage ou après reconnexion, le PC doit relire l’état courant des flags
afin de traiter une demande qui serait déjà pendante.

---

## Lancement du supervisor

Depuis la racine du dépôt :

```powershell
python scripts/run_trajcenter_supervisor.py --store trajectory_store
```

Options principales :

```powershell
python scripts/run_trajcenter_supervisor.py `
  --store trajectory_store `
  --task T_ROB1 `
  --module TRAJCENTER `
  --mastership-retries 3 `
  --log-level INFO
```

La configuration de connexion RWS dépend de la librairie
`abb-rws-client-python-rw6` et de son chargement d’environnement.

Vérifier notamment :

- adresse contrôleur ;
- utilisateur ;
- mot de passe ;
- configuration réseau ;
- droits Mastership ;
- module système RAPID chargé ;
- module cible `TRAJCENTER`.

---

## Installation développeur

Le projet utilise `pixi`.

Commandes usuelles :

```powershell
pixi install
pixi run ruff check .
pixi run tests
```

Correction automatique si configurée :

```powershell
pixi run pyinit-write
```

---

## Validation locale actuelle

La base de tests couvre :

- conversion APT, CSV, Excel, MOD ;
- modèle cœur `Trajectory` ;
- export CSV/Excel ;
- parsing et résolution RWS ;
- writer RWS avec mocks ;
- reader RWS avec mocks ;
- service RWS ;
- supervisor RWS ;
- store local `.trajcenter` ;
- erreurs RWS.

Dernière validation locale connue :

```text
792 passed
coverage globale : 99%
```

---

## Tests à faire avec accès robot

Cette section liste les tests d’intégration réels à exécuter dès qu’un robot ABB
RobotWare 6.x ou RobotStudio contrôleur virtuel sera disponible.

### 1. Préparation contrôleur

- Installer/charger le module système RAPID :

```rapid
MODULE TRAJCENTER(SYSMODULE)
```

- Compiler le module.
- Vérifier que le module cible RWS est bien :

```text
TRAJCENTER
```

- Vérifier que les symboles RWS existent :
  - `sendTrajRequest`
  - `refreshMetaRequest`
  - `selectedTrajIndex`
  - `nbTrajAvailable`
  - `trajectories`
  - `trajReady`
  - `transferError`
  - `lastErrorCode`
  - `lastError`
  - `transferProgress`
  - `nbLoadedTrajPoints`
  - `trajData`
  - `processParams`
  - `hasDefaultTcpSpeed`
  - `defaultTcpSpeed`
  - `hasDefaultZoneType`
  - `defaultZoneType`
  - `hasDefaultToolName`
  - `defaultToolName`
  - `hasDefaultWobjName`
  - `defaultWobjName`
  - `defaultMoveType`
  - `defaultReadConfs`
  - `trajTools`
  - `trajWobjs`
  - `processTypes`

### 2. Test connexion RWS

Objectif : valider l’accès HTTP RWS.

À vérifier :

- login OK ;
- lecture d’un symbole simple ;
- erreur propre si identifiants invalides ;
- timeout propre si contrôleur indisponible ;
- traduction correcte des erreurs RWS.

### 3. Test Mastership

Objectif : valider les écritures protégées.

À vérifier :

- acquisition Mastership OK ;
- écriture d’une variable simple ;
- release Mastership même en cas d’exception ;
- comportement si Mastership refusé ;
- retry Mastership ;
- absence de Mastership résiduelle après arrêt brutal du script.

### 4. Test subscription RWS

Objectif : valider le fonctionnement événementiel.

À vérifier :

- création subscription sur `refreshMetaRequest` ;
- création subscription sur `sendTrajRequest` ;
- réception event `TRUE` ;
- event `FALSE` ignoré ;
- suppression propre du groupe subscription à l’arrêt ;
- reconnexion ou relance supervisor après interruption.

### 5. Test refresh metadata nominal

Objectif : remplir la liste robot des trajectoires disponibles.

Procédure :

```rapid
refreshMetaRequest := TRUE;
```

Résultat attendu :

```text
refreshMetaRequest = FALSE
transferError = FALSE
lastErrorCode = 200001
lastError = ""
nbTrajAvailable > 0
trajectories{1..nbTrajAvailable} cohérent avec trajectory_store/
```

À contrôler :

- ordre des trajectoires ;
- noms ;
- nombres de points ;
- process type ;
- comportement avec store vide ;
- comportement avec archive invalide.

### 6. Test transfert trajectoire sans process

Objectif : transférer une trajectoire simple.

Procédure :

```rapid
selectedTrajIndex := 1;
sendTrajRequest := TRUE;
```

Résultat attendu :

```text
sendTrajRequest = FALSE
trajReady = TRUE
transferError = FALSE
lastErrorCode = 200002
lastError = ""
transferProgress = 100
nbLoadedTrajPoints = pointCount attendu
trajData{1..nbLoadedTrajPoints} renseigné
trajData{i}.processParamIndex = 0
```

À contrôler :

- `moveType` ;
- robtarget ;
- confdata ;
- axes externes absents écrits en `9E+9` côté RWS ;
- `tcpSpeed` ;
- `zoneType` ;
- `readConfs` ;
- `toolIndex` ;
- `wobjIndex`.

### 7. Test transfert trajectoire avec process

Objectif : valider `processParams` et `processParamIndex`.

À contrôler :

- `processType` transféré ;
- sets process écrits en base 1 ;
- slots inutilisés écrits avec `name=""`, `value=0` ;
- déduplication des sets identiques ;
- points sans process avec `processParamIndex = 0` ;
- cohérence entre `trajData{i}.processParamIndex` et `processParams{p,*}`.

### 8. Test defaults robot

Objectif : valider les règles de fallback.

Cas à tester :

- `tcp_speed` absent avec `hasDefaultTcpSpeed = TRUE` ;
- `tcp_speed` absent avec `hasDefaultTcpSpeed = FALSE` ;
- `zone_type` absent avec/sans default ;
- `tool_name` absent avec/sans default ;
- `wobj_name` absent avec/sans default ;
- `move_type` absent ;
- `readconfs` absent.

Résultat attendu :

- fallback uniquement si `hasDefault* = TRUE` ;
- erreur sinon ;
- aucun outil ou wobj inventé silencieusement.

### 9. Test erreurs fonctionnelles

Cas à provoquer :

| Cas                             | Code attendu |
| ------------------------------- | -----------: |
| `selectedTrajIndex` hors bornes |     `400001` |
| archive absente                 |     `400002` |
| archive invalide                |     `400003` |
| trop de points                  |     `400004` |
| zone invalide                   |     `400005` |
| mouvement invalide              |     `400006` |
| paire `MoveC` invalide          |     `400007` |
| vitesse absente sans default    |     `400008` |
| zone absente sans default       |     `400009` |
| outil absent sans default       |     `400010` |
| wobj absent sans default        |     `400011` |
| outil inconnu robot             |     `400012` |
| wobj inconnu robot              |     `400013` |
| vitesse invalide                |     `400014` |
| readConfs invalide              |     `400015` |
| robtarget invalide              |     `400016` |
| process inconnu                 |     `400017` |
| trop de sets process            |     `400018` |
| paramètres process invalides    |     `400019` |

À vérifier pour chaque erreur :

```text
trajReady = FALSE
transferError = TRUE
lastErrorCode = code attendu
lastError non vide et court
sendTrajRequest = FALSE
refreshMetaRequest = FALSE si erreur refresh
```

### 10. Test performance transfert

Objectif : mesurer le temps réel d’écriture RWS.

Jeux à tester :

- 10 points ;
- 100 points ;
- 1 000 points ;
- 10 000 points ;
- trajectoire proche limite si raisonnable.

Mesures :

- durée totale ;
- temps acquisition Mastership ;
- temps écriture metadata ;
- temps écriture `processParams` ;
- temps écriture `trajData` ;
- évolution `transferProgress` ;
- comportement timeout.

### 11. Test robustesse interruption

Cas à tester :

- arrêt PC pendant refresh ;
- arrêt PC pendant transfert ;
- perte réseau ;
- redémarrage supervisor ;
- demande déjà TRUE avant lancement supervisor ;
- Mastership refusé temporairement ;
- contrôleur redémarré.

Résultat attendu :

- pas de subscription orpheline durable ;
- pas de Mastership bloquée ;
- flags remis dans un état cohérent ;
- demande pendante détectée au redémarrage si encore TRUE.

### 12. Test exécution RAPID après transfert

Objectif : vérifier que les données transférées sont réellement consommables.

À faire côté RAPID :

- parcourir `trajData{1..nbLoadedTrajPoints}` ;
- construire les instructions `MoveL`, `MoveJ`, `MoveC` correspondantes ;
- utiliser `trajTools{toolIndex}.value` ;
- utiliser `trajWobjs{wobjIndex}.value` ;
- appliquer ou ignorer confdata selon `readConfs` ;
- appliquer le process selon `processParamIndex`.

À vérifier :

- trajectoire simple sans process ;
- trajectoire avec process ;
- trajectoire avec axes externes absents ;
- trajectoire avec confdata ;
- trajectoire avec `fine`.

---

## Qualité et règles de contribution

Règles principales :

- Python >= 3.11 ;
- code typé ;
- `ruff` sans warning ;
- tests obligatoires ;
- mocks HTTP pour les appels RWS ;
- pas de print intempestif ;
- logging via le système projet ;
- aucune écriture RAPID hors Mastership ;
- aucun retour au protocole TCP v1.

Commandes avant commit :

```powershell
pixi run pyinit-write
pixi run ruff check .
pixi run tests
```

---

## Codes d’état et d’erreur

|     Code | Signification                      |
| -------: | ---------------------------------- |
| `200000` | OK                                 |
| `200001` | Metadata refreshed                 |
| `200002` | Trajectory transferred             |
| `400001` | `selectedTrajIndex` hors bornes    |
| `400002` | Fichier trajectoire introuvable    |
| `400003` | Format `.trajcenter` invalide      |
| `400004` | Trop de points                     |
| `400005` | `zone_type` invalide               |
| `400006` | `move_type` invalide               |
| `400007` | Paire `MoveC` invalide             |
| `400008` | `tcp_speed` manquant sans default  |
| `400009` | `zone_type` manquant sans default  |
| `400010` | `tool_name` manquant sans default  |
| `400011` | `wobj_name` manquant sans default  |
| `400012` | `tool_name` introuvable côté robot |
| `400013` | `wobj_name` introuvable côté robot |
| `400014` | Vitesse invalide                   |
| `400015` | `readConfs` invalide               |
| `400016` | Robtarget invalide                 |
| `400017` | Process inconnu                    |
| `400018` | Trop de sets process               |
| `400019` | Paramètres process invalides       |
| `401001` | Authentification RWS refusée       |
| `403001` | Mastership refusé                  |
| `403002` | Écriture RWS interdite             |
| `404001` | Symbole RAPID introuvable          |
| `404002` | `trajTools` introuvable            |
| `404003` | `trajWobjs` introuvable            |
| `404004` | Store trajectoire introuvable      |
| `404005` | Default robot introuvable          |
| `404006` | `processTypes` introuvable         |
| `408001` | Timeout requête RWS                |
| `408002` | Timeout transfert                  |
| `409001` | Transfert déjà en cours            |
| `409002` | État robot incompatible            |
| `500001` | Erreur interne client              |
| `500002` | Erreur de sérialisation            |
| `500003` | Erreur de conversion trajectoire   |
| `502001` | Réponse RWS invalide               |
| `503001` | Contrôleur indisponible            |
| `504001` | Timeout contrôleur                 |

---

## Historique

### v1

Ancienne version TCP/IP Python où le robot ABB jouait le rôle de client TCP.
Cette version est obsolète.

### v2

Version actuelle basée exclusivement sur ABB Robot Web Services :

- module système RAPID unique `TRAJCENTER` ;
- RWS subscriptions ;
- RWS reads ;
- RWS writes ;
- Mastership ;
- archives `.trajcenter` ;
- pipeline PC événementiel.
