# TRAJCENTER v2.0 — Protocole RWS PC ↔ Robot

> **Version :** 2.4 draft  
> **Date :** 2026-07-18  
> **RobotWare :** 6.x  
> **Transport :** ABB Robot Web Services uniquement  
> **TCP custom / watchdog / polling nominal :** supprimés  

---

## 1. Modules RAPID

| Module | Rôle |
|---|---|
| `TRAJCENTER_Types` | Constantes, codes, `RECORD` communs |
| `TRAJCENTER_ProcessConfig` | Catalogue process robot |
| `TRAJCENTER_CellConfig` | Config cellule persistante : tools, wobjs |
| `TRAJCENTER_WebServices` | Variables RWS PC ↔ robot |

Ordre de chargement :

```text
1. TRAJCENTER_Types
2. TRAJCENTER_ProcessConfig
3. TRAJCENTER_CellConfig
4. TRAJCENTER_WebServices
```

Politique :

| Cas | Déclaration |
|---|---|
| Flags abonnés RWS | `PERS` |
| Tools / wobjs cellule | `PERS` |
| Maintenance tools / wobjs | `PERS` |
| Runtime, metadata, trajectoire, defaults | `VAR` |
| Tailles fixes, codes | `CONST` |

---

## 2. Flux

| Flux | Déclencheur | Direction | Mécanisme |
|---|---|---|---|
| Refresh metadata | `refreshMetaRequest = TRUE` | Robot → PC | RWS subscription |
| Envoi trajectoire | `sendTrajRequest = TRUE` | Robot → PC | RWS subscription |
| Écriture données | PC | PC → Robot | RWS write + Mastership |
| Lecture contexte | PC | Robot → PC | RWS read |

Règles :

```text
PC subscribe:
- TRAJCENTER_WebServices/sendTrajRequest
- TRAJCENTER_WebServices/refreshMetaRequest

Seuls les events TRUE déclenchent une action.
Les events FALSE sont ignorés.
Le PC remet la requête traitée à FALSE, succès comme erreur.
Au démarrage/reconnexion, relire les deux flags pour traiter une demande pendante.
Toute écriture RWS est faite sous Mastership avec release garanti.
```

---

## 3. Constantes

Module : `TRAJCENTER_Types`

```rapid
CONST num maxTrajCount := 256;
CONST num maxTrajPointCount := 100000;
CONST num maxProcessParamSetCount := 256;
CONST num maxProcessParamPerSet := 10;

CONST num processNone := 0;
CONST num processAcf := 1;
CONST num processAak := 2;
CONST num processPushcorp := 3;

CONST num moveTypeL := 0;
CONST num moveTypeJ := 1;
CONST num moveTypeC := 2;

CONST num statusOk := 200000;
CONST num statusMetadataRefreshed := 200001;
CONST num statusTrajectoryTransferred := 200002;
```

---

## 4. Types RAPID

### 4.1 `trajCenterPointData`

```rapid
RECORD trajCenterPointData
    num moveType;
    robtarget point;
    num tcpSpeed;
    num zoneType;
    bool readConfs;
    num toolIndex;
    num wobjIndex;
    num processParamIndex;
ENDRECORD
```

| Champ | Convention |
|---|---|
| `moveType` | `0=MoveL`, `1=MoveJ`, `2=MoveC` |
| `point` | `robtarget` ABB |
| `tcpSpeed` | mm/s, `> 0` |
| `zoneType` | zone autorisée, `255=fine` |
| `readConfs` | prise en compte `confdata` |
| `toolIndex` | base 1 dans `trajTools`, `0=undefined` |
| `wobjIndex` | base 1 dans `trajWobjs`, `0=undefined` |
| `processParamIndex` | base 1 dans `processParams`, `0=aucun` |

---

### 4.2 `trajCenterTrajMeta`

```rapid
RECORD trajCenterTrajMeta
    string name;
    num pointCount;
    num processType;
ENDRECORD
```

| Champ | Convention |
|---|---|
| `name` | nom affichable |
| `pointCount` | nombre de points |
| `processType` | `0=NONE`, `1=ACF`, `2=AAK`, `3=PUSHCORP`, `4..255=RESERVED` |

---

### 4.3 Tools / wobjs

```rapid
RECORD trajCenterTool
    string name;
    tooldata value;
ENDRECORD

RECORD trajCenterWobj
    string name;
    wobjdata value;
ENDRECORD
```

Mapping PC :

```text
tool_name -> trajTools{i}.name -> toolIndex = i
wobj_name -> trajWobjs{i}.name -> wobjIndex = i
```

---

### 4.4 Process

```rapid
RECORD trajCenterProcessParameter
    string name;
    num value;
ENDRECORD

RECORD trajCenterProcessType
    num id;
    string name;
ENDRECORD
```

Convention :

```text
processParams{i,j}.name = "" => slot inutilisé
processParams{i,j}.value     => numérique uniquement
```

---

## 5. Catalogue process

Module : `TRAJCENTER_ProcessConfig`

```rapid
CONST num processTypeCount := 4;

VAR trajCenterProcessType processTypes{processTypeCount}:=[
    [0, "NONE"],
    [1, "ACF"],
    [2, "AAK"],
    [3, "PUSHCORP"]
];
```

| ID | Nom |
|---:|---|
| `0` | `NONE` |
| `1` | `ACF` |
| `2` | `AAK` |
| `3` | `PUSHCORP` |
| `4..255` | `RESERVED` |

---

## 6. Configuration cellule

Module : `TRAJCENTER_CellConfig`

```rapid
PERS trajCenterTool trajTools{N};
PERS trajCenterWobj trajWobjs{M};

PERS tooldata tempTool;
PERS wobjdata tempWobj;
```

Règles :

```text
trajTools/trajWobjs sont cellule-dépendants.
Le PC lit .name.
Index RAPID envoyés en base 1.
0 = non défini.
```

---

## 7. Variables RWS

Module : `TRAJCENTER_WebServices`

### 7.1 Requêtes

```rapid
PERS bool sendTrajRequest := FALSE;
PERS bool refreshMetaRequest := FALSE;
VAR num selectedTrajIndex := 0;
```

```text
selectedTrajIndex = 0                 : aucune sélection
selectedTrajIndex = 1..nbTrajAvailable: trajectoire valide
```

---

### 7.2 État

```rapid
VAR bool trajReady := FALSE;
VAR bool transferError := FALSE;
VAR num lastErrorCode := 200000;
VAR string lastError := "";
VAR num transferProgress := 0;
```

| Variable | Rôle |
|---|---|
| `trajReady` | trajectoire complète et exécutable |
| `transferError` | dernier refresh/transfert en erreur |
| `lastErrorCode` | code état/erreur |
| `lastError` | message court |
| `transferProgress` | `0..100` |

---

### 7.3 Metadata store

```rapid
VAR num nbTrajAvailable := 0;
VAR trajCenterTrajMeta trajectories{256};
```

Entrées valides :

```text
trajectories{1..nbTrajAvailable}
```

---

### 7.4 Trajectoire chargée

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

Aucun process :

```text
trajData{i}.processParamIndex = 0
```

Process associé :

```text
trajData{i}.processParamIndex = p
=> processParams{p,1..10}
```

---

### 7.5 Defaults robot

```rapid
VAR bool hasDefaultTcpSpeed := FALSE;
VAR num defaultTcpSpeed := 0;

VAR bool hasDefaultZoneType := FALSE;
VAR num defaultZoneType := 255;

VAR bool hasDefaultToolName := FALSE;
VAR string defaultToolName := "";

VAR bool hasDefaultWobjName := FALSE;
VAR string defaultWobjName := "";

VAR num defaultMoveType := 0;
VAR bool defaultReadConfs := TRUE;
```

Règle :

```text
Le PC ne doit jamais inventer silencieusement tool, wobj, speed ou zone.
Fallback uniquement si hasDefault* = TRUE.
```

---

## 8. Format `.trajcenter`

Archive :

```text
meta.json
points.parquet
```

---

### 8.1 `meta.json`

Champs usuels :

| Champ | Type | Rôle |
|---|---|---|
| `name` | `str` | nom trajectoire |
| `version` | `str` | version format |
| `source_format` | `str` | format source |
| `robot_model` | `str \| null` | robot cible optionnel |
| `process_type` | `str \| int \| null` | process principal optionnel |
| `extra` | `dict` | metadata libre |

`process_type` :

```text
absent/null/"NONE"/0 -> 0
"ACF"/1              -> 1
"AAK"/2              -> 2
"PUSHCORP"/3         -> 3
autre                -> validation contre processTypes robot
```

---

### 8.2 Colonnes `points.parquet`

| Colonne | Exportable | Envoyable | Résolution |
|---|---:|---:|---|
| `x` | oui | oui | obligatoire |
| `y` | oui | oui | obligatoire |
| `z` | oui | oui | obligatoire |
| `q1` | oui | oui | quaternion ABB `w` |
| `q2` | oui | oui | quaternion ABB `x` |
| `q3` | oui | oui | quaternion ABB `y` |
| `q4` | oui | oui | quaternion ABB `z` |
| `cf1` | non | oui | `0` si absent |
| `cf4` | non | oui | `0` si absent |
| `cf6` | non | oui | `0` si absent |
| `cfx` | non | oui | `0` si absent |
| `eax_a..eax_f` | non | oui | absent/NaN = `9E+9` à l’écriture RWS uniquement |
| `tcp_speed` | non | oui | erreur sauf default robot |
| `zone_type` | non | oui | erreur sauf default robot |
| `move_type` | non | oui | default robot si absent |
| `tool_name` | non | oui | erreur sauf default robot validé |
| `wobj_name` | non | oui | erreur sauf default robot validé |
| `readconfs` | non | oui | règle ci-dessous |
| `process_type` | non | oui | optionnel, sinon `meta.process_type`, sinon `NONE` |
| `process_params` | non | oui | optionnel |
| `process_param_index` | non | non | généré PC, non fiable si stocké |

Règle `readconfs` si absent :

```text
si cf1/cf4/cf6/cfx présents : readConfs = TRUE
sinon                       : readConfs = FALSE
```

Règle process :

```text
process_type absent partout -> processType = 0 = NONE
process_params vide/absent  -> processParamIndex = 0
process_param_index stocké  -> ignoré et recalculé
```

---

### 8.3 `process_params`

Formats acceptés :

```python
{"force": 120.0, "feed": 5.0}
```

ou JSON string :

```json
{"force": 120.0, "feed": 5.0}
```

Valeurs vides :

```text
None, NaN, "", {} => aucun paramètre
```

Contraintes :

```text
sets distincts <= 256
paramètres par set <= 10
noms non vides
valeurs numériques uniquement
sets identiques dédupliqués
ordre paramètres = tri alphabétique par nom
```

Exemple :

```text
P1 {"force":100,"feed":5}
P2 {"force":100,"feed":5}
P3 {"force":150,"feed":5}
P4 {}
```

Produit :

```text
processParams{1,1} = ["feed",5]
processParams{1,2} = ["force",100]
processParams{1,3..10} = ["",0]

processParams{2,1} = ["feed",5]
processParams{2,2} = ["force",150]
processParams{2,3..10} = ["",0]

trajData{1}.processParamIndex = 1
trajData{2}.processParamIndex = 1
trajData{3}.processParamIndex = 2
trajData{4}.processParamIndex = 0
```

---

### 8.4 Exportable vs envoyable

| Niveau | Définition |
|---|---|
| Exportable | `x,y,z,q1,q2,q3,q4` présents |
| Envoyable | champs robot résolus + tools/wobjs/process/defaults valides |

Une trajectoire exportable peut être listée mais refusée à l’envoi.

---

## 9. Conventions

### 9.1 Indexation

| Élément | Convention |
|---|---|
| Tableaux RAPID | base 1 |
| `selectedTrajIndex` | base 1, `0=aucune sélection` |
| `toolIndex`, `wobjIndex` | base 1, `0=undefined` |
| `processParamIndex` | base 1, `0=aucun` |
| Points `.trajcenter` | ordre fichier -> RAPID `{1..N}` |

---

### 9.2 RWS symbol URLs

RAPID array :

```rapid
trajData{1}
```

RWS symbolurl :

```text
RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B1%7D
```

Record complet recommandé :

```text
trajData{1} = [moveType, robtarget, tcpSpeed, zoneType, readConfs, toolIndex, wobjIndex, processParamIndex]
```

---

### 9.3 Robtarget

Format RWS :

```text
[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,eax_b,eax_c,eax_d,eax_e,eax_f]]
```

Règles :

```text
[q1,q2,q3,q4] = [w,x,y,z]
axes externes absents/NaN -> 9E+9 à l’écriture RWS uniquement
9E+9 jamais stocké dans .trajcenter
```

---

### 9.4 Zones

Autorisées :

```text
0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 255
```

```text
0   = z0
255 = fine
```

---

### 9.5 Vitesses

```text
tcp_speed -> trajData{i}.tcpSpeed
numérique, mm/s, > 0
```

---

### 9.6 Mouvements

| RAPID | Mouvement | Alias acceptés |
|---:|---|---|
| `0` | `MoveL` | `"L"`, `"MoveL"`, `0` |
| `1` | `MoveJ` | `"J"`, `"MoveJ"`, `1` |
| `2` | `MoveC` | `"C"`, `"MoveC"`, `2` |

---

### 9.7 MoveC

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

## 10. Pipelines

### 10.1 Démarrage PC

```text
1. Ouvrir session RWS.
2. S’abonner à sendTrajRequest et refreshMetaRequest.
3. Lire l’état courant des deux requêtes.
4. Lire defaults robot.
5. Lire trajTools et trajWobjs.
6. Lire processTypes.
7. Scanner trajectory_store/.
8. Écrire nbTrajAvailable et trajectories.
9. Traiter requête pendante si TRUE.
```

---

### 10.2 Refresh metadata

Déclencheur :

```rapid
refreshMetaRequest := TRUE;
```

PC :

```text
1. Reçoit refreshMetaRequest = TRUE.
2. Scanne trajectory_store/.
3. Liste les .trajcenter exportables.
4. Détermine name, pointCount, processType.
5. Écrit nbTrajAvailable.
6. Écrit trajectories{1..nbTrajAvailable}.
7. Écrit transferError = FALSE.
8. Écrit lastErrorCode = 200001.
9. Écrit lastError = "".
10. Écrit refreshMetaRequest = FALSE.
```

`trajectories{i}` :

```text
[name, pointCount, processType]
```

Résolution `processType` metadata :

```text
1. meta.process_type si présent
2. sinon process_type points si unique non-NONE
3. sinon premier process non-NONE
4. sinon 0 = NONE
```

---

### 10.3 Envoi trajectoire

Déclencheur :

```rapid
selectedTrajIndex := k;
sendTrajRequest := TRUE;
```

PC :

```text
1. Reçoit sendTrajRequest = TRUE.
2. Lit selectedTrajIndex.
3. Charge le .trajcenter.
4. Lit defaults, trajTools, trajWobjs, processTypes.
5. Résout toolIndex, wobjIndex, processType, processParams.
6. Valide limites et contraintes.
7. Écrit trajReady = FALSE.
8. Écrit transferError = FALSE.
9. Écrit transferProgress = 0.
10. Écrit nbLoadedTrajPoints.
11. Écrit processParams si nécessaire.
12. Écrit trajData{1..nbLoadedTrajPoints}.
13. Met à jour transferProgress par blocs.
14. Écrit transferProgress = 100.
15. Écrit lastErrorCode = 200002.
16. Écrit lastError = "".
17. Écrit trajReady = TRUE.
18. Écrit sendTrajRequest = FALSE.
```

En erreur :

```text
trajReady = FALSE
transferError = TRUE
lastErrorCode = code
lastError = message court
transferProgress = valeur courante ou 0
sendTrajRequest = FALSE
refreshMetaRequest = FALSE si erreur refresh
```

---

## 11. Validation avant envoi

Refus si :

| Cas | Code |
|---|---:|
| `selectedTrajIndex` hors bornes | `400001` |
| fichier absent | `400002` |
| format `.trajcenter` invalide | `400003` |
| `pointCount > maxTrajPointCount` | `400004` |
| `zone_type` invalide | `400005` |
| `move_type` invalide | `400006` |
| paire `MoveC` invalide | `400007` |
| `tcp_speed` absent sans default | `400008` |
| `zone_type` absent sans default | `400009` |
| `tool_name` absent sans default | `400010` |
| `wobj_name` absent sans default | `400011` |
| `tool_name` introuvable | `400012` |
| `wobj_name` introuvable | `400013` |
| `tcp_speed <= 0` | `400014` |
| `readconfs` invalide | `400015` |
| robtarget non sérialisable | `400016` |
| process inconnu | `400017` |
| trop de sets process | `400018` |
| process params invalides | `400019` |

Process params invalides :

```text
JSON invalide
nom vide
valeur non numérique
plus de 10 paramètres par set
plus de 256 sets distincts
```

---

## 12. Codes d’état et d’erreur

| Code | Signification |
|---:|---|
| `200000` | OK |
| `200001` | Metadata refreshed |
| `200002` | Trajectory transferred |
| `400001` | `selectedTrajIndex` hors bornes |
| `400002` | Fichier trajectoire introuvable |
| `400003` | Format `.trajcenter` invalide |
| `400004` | Trop de points |
| `400005` | `zone_type` invalide |
| `400006` | `move_type` invalide |
| `400007` | Paire `MoveC` invalide |
| `400008` | `tcp_speed` manquant sans default |
| `400009` | `zone_type` manquant sans default |
| `400010` | `tool_name` manquant sans default |
| `400011` | `wobj_name` manquant sans default |
| `400012` | `tool_name` introuvable côté robot |
| `400013` | `wobj_name` introuvable côté robot |
| `400014` | Vitesse invalide |
| `400015` | `readConfs` invalide |
| `400016` | Robtarget invalide |
| `400017` | Process inconnu |
| `400018` | Trop de sets process |
| `400019` | Paramètres process invalides |
| `401001` | Authentification RWS refusée |
| `403001` | Mastership refusé |
| `403002` | Écriture RWS interdite |
| `404001` | Symbole RAPID introuvable |
| `404002` | `trajTools` introuvable |
| `404003` | `trajWobjs` introuvable |
| `404004` | Store trajectoire introuvable |
| `404005` | Default robot introuvable |
| `404006` | `processTypes` introuvable |
| `408001` | Timeout requête RWS |
| `408002` | Timeout transfert |
| `409001` | Transfert déjà en cours |
| `409002` | État robot incompatible |
| `500001` | Erreur interne client |
| `500002` | Erreur de sérialisation |
| `500003` | Erreur de conversion trajectoire |
| `502001` | Réponse RWS invalide |
| `503001` | Contrôleur indisponible |
| `504001` | Timeout contrôleur |