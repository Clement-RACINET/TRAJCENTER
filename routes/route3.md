# TRAJCENTER v2.0 — Protocole RWS PC ↔ Robot

> **Version :** 2.3 draft  
> **Date :** 2026-07-17  
> **RobotWare :** 6.x  
> **Transport :** ABB Robot Web Services uniquement  
> **TCP custom / watchdog / polling nominal :** supprimés  

---

## 1. Modules RAPID

Découpage cible :

| Module | Rôle |
|---|---|
| `TRAJCENTER_Types` | Constantes globales, codes, `RECORD` communs |
| `TRAJCENTER_ProcessConfig` | Catalogue process robot |
| `TRAJCENTER_CellConfig` | Configuration cellule persistante : tools, wobjs, maintenance |
| `TRAJCENTER_WebServices` | Variables RWS de communication PC ↔ robot |

Ordre de chargement recommandé :

```text
1. TRAJCENTER_Types
2. TRAJCENTER_ProcessConfig
3. TRAJCENTER_CellConfig
4. TRAJCENTER_WebServices
```

Politique `PERS` :

| Cas | Déclaration |
|---|---|
| Variables abonnées RWS | `PERS` |
| Tools / wobjs propres à la cellule | `PERS` |
| Variables de maintenance tools / wobjs | `PERS` |
| État runtime, metadata, trajectoire, defaults | `VAR` |
| Tailles fixes, codes protocole | `CONST` |

---

## 2. Flux général

| Flux | Déclencheur | Direction | Mécanisme | Résultat |
|---|---|---|---|---|
| Refresh metadata | `refreshMetaRequest = TRUE` | Robot → PC | RWS subscription | Le PC rescane le store et écrit les metadata |
| Envoi trajectoire | `sendTrajRequest = TRUE` | Robot → PC | RWS subscription | Le PC lit `selectedTrajIndex` et écrit la trajectoire |
| Écriture données | Action PC | PC → Robot | RWS write + Mastership | Variables RAPID mises à jour |
| Lecture contexte robot | Action PC | Robot → PC | RWS read | Defaults, tools, wobjs, process, état courant |
| État / erreur | Action PC | PC → Robot | RWS write + Mastership | `trajReady`, `transferError`, `lastErrorCode`, etc. |

Règles :

- le PC s’abonne au démarrage à :
  - `TRAJCENTER_WebServices/sendTrajRequest`;
  - `TRAJCENTER_WebServices/refreshMetaRequest`;
- seuls les événements `TRUE` déclenchent une action ;
- les événements `FALSE` sont ignorés ;
- le PC remet la requête traitée à `FALSE`, succès comme erreur ;
- au démarrage ou après reconnexion, le PC relit les deux requêtes pour traiter une demande pendante ;
- toute écriture RWS est faite sous Mastership, avec libération garantie.

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

Module : `TRAJCENTER_Types`

### 4.1 Point trajectoire

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

| Champ | Type | Convention |
|---|---|---|
| `moveType` | `num` | `0 = MoveL`, `1 = MoveJ`, `2 = MoveC` |
| `point` | `robtarget` | Point ABB complet |
| `tcpSpeed` | `num` | TCP mm/s, strictement positif |
| `zoneType` | `num` | Zone numérique autorisée |
| `readConfs` | `bool` | Prise en compte de `confdata` |
| `toolIndex` | `num` | Index base 1 dans `trajTools`, `0 = undefined` |
| `wobjIndex` | `num` | Index base 1 dans `trajWobjs`, `0 = undefined` |
| `processParamIndex` | `num` | `0 = aucun`, sinon ligne base 1 dans `processParams` |

---

### 4.2 Metadata trajectoire

```rapid
RECORD trajCenterTrajMeta
    string name;
    num pointCount;
    num processType;
ENDRECORD
```

| Champ | Type | Convention |
|---|---|---|
| `name` | `string` | Nom affichable |
| `pointCount` | `num` | Nombre de points |
| `processType` | `num` | `0 = NONE`, `1 = ACF`, `2 = AAK`, `3 = PUSHCORP`, `4..255 = RESERVED` |

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
tool_name (.trajcenter) -> trajTools{i}.name -> toolIndex = i
wobj_name (.trajcenter) -> trajWobjs{i}.name -> wobjIndex = i
```

---

### 4.4 Paramètre process

```rapid
RECORD trajCenterProcessParameter
    string name;
    num value;
ENDRECORD
```

Convention :

```text
processParams{i,j}.name = "" => slot inutilisé
processParams{i,j}.value      => valeur numérique uniquement
```

---

### 4.5 Type process

```rapid
RECORD trajCenterProcessType
    num id;
    string name;
ENDRECORD
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

Convention :

| ID | Nom |
|---:|---|
| `0` | `NONE` |
| `1` | `ACF` |
| `2` | `AAK` |
| `3` | `PUSHCORP` |
| `4..255` | `RESERVED` |

Ajout d’un process :

```text
1. Incrémenter processTypeCount.
2. Ajouter l’entrée à processTypes.
3. Conserver l’ID stable.
```

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

- `trajTools` et `trajWobjs` sont cellule-dépendants ;
- leurs tailles sont adaptées par l’intégrateur robot ;
- le PC lit le champ `.name` ;
- les index RAPID envoyés dans `trajData` sont en base 1 ;
- `0` signifie non défini.

---

## 7. Variables RWS

Module : `TRAJCENTER_WebServices`

### 7.1 Requêtes robot → PC

```rapid
PERS bool sendTrajRequest := FALSE;
PERS bool refreshMetaRequest := FALSE;
VAR num selectedTrajIndex := 0;
```

| Variable | Déclaration | Défaut | Rôle |
|---|---|---|---|
| `sendTrajRequest` | `PERS bool` | `FALSE` | Demande d’envoi de trajectoire |
| `refreshMetaRequest` | `PERS bool` | `FALSE` | Demande de refresh metadata |
| `selectedTrajIndex` | `VAR num` | `0` | Index de trajectoire sélectionnée |

Convention :

```text
selectedTrajIndex = 0 : aucune sélection
selectedTrajIndex = 1..nbTrajAvailable : trajectoire valide
```

---

### 7.2 État PC → robot

```rapid
VAR bool trajReady := FALSE;
VAR bool transferError := FALSE;
VAR num lastErrorCode := 200000;
VAR string lastError := "";
VAR num transferProgress := 0;
```

| Variable | Type | Défaut | Rôle |
|---|---|---|---|
| `trajReady` | `VAR bool` | `FALSE` | Trajectoire complète et exécutable |
| `transferError` | `VAR bool` | `FALSE` | Dernier refresh/transfert en erreur |
| `lastErrorCode` | `VAR num` | `200000` | Code état/erreur |
| `lastError` | `VAR string` | `""` | Message court |
| `transferProgress` | `VAR num` | `0` | Progression `0..100` |

---

### 7.3 Metadata store

```rapid
VAR num nbTrajAvailable := 0;
VAR trajCenterTrajMeta trajectories{256};
```

| Variable | Type | Taille | Rôle |
|---|---|---:|---|
| `nbTrajAvailable` | `VAR num` | 1 | Nombre d’entrées valides |
| `trajectories` | `VAR trajCenterTrajMeta[]` | 256 | Metadata trajectoires disponibles |

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

| Variable | Type | Taille | Rôle |
|---|---|---:|---|
| `nbLoadedTrajPoints` | `VAR num` | 1 | Nombre de points valides |
| `trajData` | `VAR trajCenterPointData[]` | 100000 | Points trajectoire |
| `processParams` | `VAR trajCenterProcessParameter[,]` | 256 x 10 | Paramètres process runtime |

Entrées valides :

```text
trajData{1..nbLoadedTrajPoints}
processParams{1..256,1..10}
```

Aucun process sur un point :

```text
trajData{i}.processParamIndex = 0
```

Process params associés :

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

| Variable | Type | Rôle |
|---|---|---|
| `hasDefaultTcpSpeed` | `VAR bool` | Autorise fallback vitesse |
| `defaultTcpSpeed` | `VAR num` | Vitesse TCP par défaut |
| `hasDefaultZoneType` | `VAR bool` | Autorise fallback zone |
| `defaultZoneType` | `VAR num` | Zone par défaut |
| `hasDefaultToolName` | `VAR bool` | Autorise fallback tool |
| `defaultToolName` | `VAR string` | Tool par défaut |
| `hasDefaultWobjName` | `VAR bool` | Autorise fallback wobj |
| `defaultWobjName` | `VAR string` | Wobj par défaut |
| `defaultMoveType` | `VAR num` | `0 = MoveL`, `1 = MoveJ`, `2 = MoveC` |
| `defaultReadConfs` | `VAR bool` | Valeur par défaut |

Règle :

```text
Le PC ne doit jamais inventer silencieusement tool, wobj, speed ou zone.
Tout fallback doit être explicitement activé côté robot.
```

---

## 8. Format `.trajcenter`

Archive contenant au minimum :

```text
meta.json
points.parquet
```

---

### 8.1 Colonnes `points.parquet`

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
| `eax_a..eax_f` | non | non | absent = axe inactif |
| `tcp_speed` | non | oui | erreur sauf default robot |
| `zone_type` | non | oui | erreur sauf default robot |
| `move_type` | non | oui | default robot, recommandé `MoveL` |
| `tool_name` | non | oui | erreur sauf default robot validé |
| `wobj_name` | non | oui | erreur sauf default robot validé |
| `readconfs` | non | oui | règle ci-dessous |
| `process_params` | non | non | selon process |
| `process_param_index` | non | non | généré PC si besoin |

Règle `readconfs` si absent :

```text
si cf1/cf4/cf6/cfx présents : readConfs = TRUE
sinon : readConfs = FALSE
```

---

### 8.2 Exportable vs envoyable

| Niveau | Définition |
|---|---|
| Exportable | Contient au minimum `x,y,z,q1,q2,q3,q4` |
| Envoyable | Tous les champs robot sont présents ou résolus via defaults valides |

Une trajectoire exportable peut être listée, mais refusée à l’envoi.

---

## 9. Conventions

### 9.1 Indexation

| Élément | Convention |
|---|---|
| Tableaux RAPID | base 1 |
| `selectedTrajIndex` | base 1, `0 = aucune sélection` |
| `toolIndex`, `wobjIndex` | base 1, `0 = undefined` |
| `processParamIndex` | base 1, `0 = aucun paramètre` |
| Points `.trajcenter` | ordre fichier, converti vers RAPID `{1..N}` |

---

### 9.2 Robtarget

Format RWS :

```text
[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,eax_b,eax_c,eax_d,eax_e,eax_f]]
```

Règles :

- quaternion ABB : `[q1,q2,q3,q4] = [w,x,y,z]` ;
- axes externes absents : sérialisés `9E+9` uniquement à l’écriture RWS ;
- `9E+9` n’est jamais stocké dans `.trajcenter`.

---

### 9.3 Zones

Valeurs autorisées :

```text
0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 255
```

Convention :

```text
0   = z0
255 = fine
```

---

### 9.4 Vitesses

```text
tcp_speed -> trajData{i}.tcpSpeed
```

Règles :

- numérique ;
- mm/s ;
- strictement positif.

---

### 9.5 Types de mouvement

| Encodage RAPID | Mouvement | Alias acceptés à l’import |
|:---|---|---|
| `0` | `MoveL` | `"L"`, `"MoveL"`, `0` |
| `1` | `MoveJ` | `"J"`, `"MoveJ"`, `1` |
| `2` | `MoveC` | `"C"`, `"MoveC"`, `2` |

---

### 9.6 MoveC

Un `MoveC` est encodé par deux points consécutifs non chevauchants : `C, C`

Valide : `C,C,C,C` = deux MoveC successifs. Interdit : `C,C,C`.

Pour une paire `C,C`, les champs suivants doivent être identiques :

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
9. Traiter une requête pendante si une requête vaut TRUE.
```

---

### 10.2 Refresh metadata

Déclencheur RAPID :

```rapid
refreshMetaRequest := TRUE;
```

PC :

```text
1. Reçoit refreshMetaRequest = TRUE.
2. Scanne trajectory_store/.
3. Liste les .trajcenter exportables.
4. Écrit trajReady = FALSE si metadata incohérente avec trajectoire chargée.
5. Écrit nbTrajAvailable.
6. Écrit trajectories{1..nbTrajAvailable}.
7. Écrit transferError = FALSE.
8. Écrit lastErrorCode = 200001.
9. Écrit lastError = "".
10. Écrit refreshMetaRequest = FALSE.
```

---

### 10.3 Envoi trajectoire

Déclencheur RAPID :

```rapid
selectedTrajIndex := k;
sendTrajRequest := TRUE;
```

PC :

```text
1. Reçoit sendTrajRequest = TRUE.
2. Lit selectedTrajIndex.
3. Charge le .trajcenter correspondant.
4. Lit defaults, trajTools, trajWobjs, processTypes.
5. Résout la trajectoire pour le robot connecté.
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

Le PC refuse l’envoi si :

| Cas | Erreur |
|---|---|
| `selectedTrajIndex` hors bornes | oui |
| fichier absent | oui |
| format `.trajcenter` invalide | oui |
| `pointCount > maxTrajPointCount` | oui |
| `tcp_speed` absent sans default | oui |
| `tcp_speed <= 0` | oui |
| `zone_type` absent sans default | oui |
| `zone_type` hors liste autorisée | oui |
| `move_type` non normalisable | oui |
| `tool_name` absent sans default | oui |
| `tool_name` introuvable dans `trajTools` | oui |
| `wobj_name` absent sans default | oui |
| `wobj_name` introuvable dans `trajWobjs` | oui |
| process inconnu dans `processTypes` | oui |
| trop de sets process | oui |
| trop de paramètres par set process | oui |
| séquence `MoveC` invalide | oui |
| robtarget non sérialisable | oui |

---

## 12. Codes d’état et d’erreur

Format : `XXXYYY` où `XXX` reprend une famille HTTP.


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
| `400019` | Trop de paramètres process |
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
