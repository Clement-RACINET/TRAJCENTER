
# TrajCenter

TrajCenter is a Python/RAPID toolchain used to convert, store, resolve and
transfer industrial trajectories to ABB RobotWare 6.x robots through
**ABB Robot Web Services**.

> Developed at LCFC — ENSAM
> Main authors: Josselin SCHUMAKER & Clément RACINET
> Target robot: ABB RobotWare 6.x
> Transport layer: ABB Robot Web Services only
> Version: 2.0

---

## Overview

TrajCenter v2 replaces the legacy TCP-based protocol used in TrajCenter v1 with
an event-driven architecture based on ABB Robot Web Services.

The project provides:

- conversion from industrial trajectory files to a local `.trajcenter` format;
- storage of trajectories as local `.trajcenter` archives;
- export from `.trajcenter` archives to tabular formats;
- a command-line interface;
- a keyboard-driven terminal user interface;
- an ABB RWS supervisor;
- transfer of resolved trajectories to a RAPID system module.

---

## Current status

TrajCenter v2 is based on:

- local `.trajcenter` archives;
- a single RAPID system module named `TRAJCENTER`;
- RWS reads;
- RWS writes protected by Mastership;
- RWS subscriptions on RAPID flags;
- an event-driven Python supervisor;
- an optional Textual-based terminal user interface.

TrajCenter v2 no longer uses:

- a Python TCP server;
- custom TCP ports such as `50000`;
- TCP watchdog logic;
- nominal PC-side polling;
- the v1 text protocol commands such as `nbtraj`, `nomtraj`, `loadtraj`, `robt`.

---

## Repository layout

```text
trajcenter_v2/
├── doc_manual/
├── icons/
├── rapid/
│   ├── TRAJCENTER.sys
│   ├── TRAJCENTER_DEMO.mod
│   ├── TRAJCENTER_DEMO.pgf
│   ├── TRAJCENTER_GUI_DEMO.mod
│   └── TRAJCENTER_GUI_DEMO.pgf
├── scripts/
│   ├── examples/
│   ├── run_best_tui.py
│   └── run_trajcenter_supervisor.py
├── tests/
│   ├── cli/
│   ├── convert/
│   ├── core/
│   ├── export/
│   ├── robot/
│   ├── store/
│   └── ui/
├── trajcenter/
│   ├── cli/
│   ├── convert/
│   ├── core/
│   ├── export/
│   ├── robot/
│   ├── store/
│   └── ui/
├── trajectory_exports/
├── trajectory_files/
├── trajectory_store/
├── mkdocs.yml
├── pixi.lock
├── pixi.toml
├── pyproject.toml
└── README.md
```

---

## Main Python packages

| Package                | Purpose                                          |
| ---------------------- | ------------------------------------------------ |
| `trajcenter.cli`     | Command-line interface                           |
| `trajcenter.convert` | Conversion to`.trajcenter` archives            |
| `trajcenter.core`    | Core`Trajectory` model                         |
| `trajcenter.export`  | CSV / Excel export                               |
| `trajcenter.robot`   | ABB RWS reader, resolver, writer and supervisor  |
| `trajcenter.store`   | Local`.trajcenter` store scanning and metadata |
| `trajcenter.ui`      | Textual terminal user interface                  |

---

## Pixi environments

The project is managed with **Pixi**.

No direct `pip install` command is required for normal repository usage.

| Environment | Purpose                                       |
| ----------- | --------------------------------------------- |
| `default` | Minimal base environment                      |
| `tui`     | Textual terminal user interface               |
| `robot`   | ABB robot / RWS dependencies                  |
| `full`    | TUI + ABB robot supervision                   |
| `dev`     | Development, tests, linting and documentation |

### Install the TUI environment

```powershell
pixi install -e tui
```

### Install the full robot environment

```powershell
pixi install -e full
```

### Install the development environment

```powershell
pixi install -e dev
```

---

## Quick start

### Launch the terminal UI

Recommended command:

```powershell
pixi run trajcenter-tui
```

This command selects the best already-installed Pixi environment:

1. `full` if available;
2. otherwise `tui` if available;
3. otherwise `default` if compatible.

It does **not** automatically install the `full` environment.

Example for TUI-only usage:

```powershell
pixi clean
pixi install -e tui
pixi run trajcenter-tui
```

Example with robot supervision:

```powershell
pixi clean
pixi install -e full
pixi run trajcenter-tui
```

### Run the robot supervisor directly

```powershell
pixi run -e full python scripts/run_trajcenter_supervisor.py --store trajectory_store
```

With common options:

```powershell
pixi run -e full python scripts/run_trajcenter_supervisor.py `
  --store trajectory_store `
  --task T_ROB1 `
  --module TRAJCENTER `
  --mastership-retries 3 `
  --log-level INFO
```

---

## Terminal user interface

TrajCenter provides a keyboard-driven terminal user interface based on Textual.

Launch it with:

```powershell
pixi run trajcenter-tui
```

Main keyboard shortcuts:

| Key                 | Action                                       |
| ------------------- | -------------------------------------------- |
| `↑` / `↓`     | Navigate in menus                            |
| `Enter`           | Select action                                |
| `B` or `Escape` | Go back, depending on context                |
| `R`               | Refresh, when available                      |
| `S`               | Return to splash screen from home            |
| `Q`               | Quit                                         |
| `X`               | Stop robot supervision from the robot screen |

When the home screen opens, the main menu automatically receives keyboard focus.

### Available TUI actions

| Action            | Purpose                                                          |
| ----------------- | ---------------------------------------------------------------- |
| Convert           | Convert CSV, Excel, APT/APTSOURCE or MOD files to`.trajcenter` |
| Export            | Export`.trajcenter` archives to CSV or Excel                   |
| Store             | Inspect local`.trajcenter` archives                            |
| Robot supervision | Start or stop the ABB RWS supervisor                             |
| Settings          | Display current TUI configuration                                |

Robot supervision is only available in an environment containing the robot
feature, typically `full` or `dev`.

---

## Command-line interface

The CLI is implemented in:

```text
trajcenter/cli/main.py
```

It can be used through Pixi:

```powershell
pixi run -e dev python -m trajcenter.cli.main --help
```

Main commands:

```text
version
convert
export
tui
store
robot
```

### Version

```powershell
pixi run -e dev python -m trajcenter.cli.main version
```

### Convert a trajectory

```powershell
pixi run -e dev python -m trajcenter.cli.main convert `
  trajectory_files/test_basic.xlsx `
  trajectory_store `
  --format xlsx
```

Supported input formats:

```text
csv
excel / xlsx
apt / aptsource
rapid / mod
```

### Export a trajectory

```powershell
pixi run -e dev python -m trajcenter.cli.main export `
  trajectory_store/test_basic.trajcenter `
  trajectory_exports `
  --format excel
```

Supported export formats:

```text
csv
excel / xlsx
```

### Inspect the local store

List available archives:

```powershell
pixi run -e dev python -m trajcenter.cli.main store list --store trajectory_store
```

Inspect one archive:

```powershell
pixi run -e dev python -m trajcenter.cli.main store inspect test_basic --store trajectory_store
```

### Launch the TUI through the CLI

```powershell
pixi run -e full python -m trajcenter.cli.main tui --store trajectory_store
```

For everyday use, prefer:

```powershell
pixi run trajcenter-tui
```

### Robot commands

Check whether the robot API is available:

```powershell
pixi run -e full python -m trajcenter.cli.main robot check
```

Run the robot supervisor:

```powershell
pixi run -e full python -m trajcenter.cli.main robot supervise --store trajectory_store
```

Useful options:

```text
--store PATH
--env-file PATH
--env-override
--host HOST
--port PORT
--username USERNAME
--password PASSWORD
--password-env ENV_VAR
--timeout SECONDS
--task TASK
--module MODULE
--mastership-retries N
--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL
```

---

## Robot supervision

The ABB supervisor listens to the following RAPID flags:

```text
TRAJCENTER/refreshMetaRequest
TRAJCENTER/sendTrajRequest
```

Only `TRUE` events trigger an action.

| RAPID request                  | Effect                                     |
| ------------------------------ | ------------------------------------------ |
| `refreshMetaRequest := TRUE` | Refresh the list of available trajectories |
| `sendTrajRequest := TRUE`    | Transfer the selected trajectory to RAPID  |

At startup or after reconnection, the supervisor must read the current flag
values to process a request that may already be pending.

The TUI robot screen starts the supervisor as a subprocess through:

```text
scripts/run_trajcenter_supervisor.py
```

This keeps the same runtime behavior as the direct terminal launcher while
displaying supervisor logs inside the Textual interface.

---

## Communication architecture

```text
ABB RAPID robot
    |
    | RWS subscription events
    v
Python TrajCenter supervisor
    |
    | scan / load / resolve
    v
trajectory_store/*.trajcenter
    |
    | RWS writes under Mastership
    v
TRAJCENTER RAPID system module
```

Main flows:

| Flow               | RAPID trigger                  | Direction   | Mechanism              |
| ------------------ | ------------------------------ | ----------- | ---------------------- |
| Refresh metadata   | `refreshMetaRequest := TRUE` | Robot → PC | RWS subscription       |
| Send trajectory    | `sendTrajRequest := TRUE`    | Robot → PC | RWS subscription       |
| Read robot context | PC                             | Robot → PC | RWS read               |
| Write trajectory   | PC                             | PC → Robot | RWS write + Mastership |

---

## RAPID module

The robot-side protocol is defined in a single RAPID system module:

```rapid
MODULE TRAJCENTER(SYSMODULE)
```

Main file:

```text
rapid/TRAJCENTER.sys
```

The repository also contains demonstration RAPID modules:

```text
rapid/TRAJCENTER_DEMO.mod
rapid/TRAJCENTER_GUI_DEMO.mod
```

### Main RAPID variables

Requests:

```rapid
PERS bool sendTrajRequest := FALSE;
PERS bool refreshMetaRequest := FALSE;
VAR num selectedTrajIndex := 0;
```

Transfer state:

```rapid
VAR bool trajReady := FALSE;
VAR bool transferError := FALSE;
VAR num lastErrorCode := statusOk;
VAR string lastError := "";
VAR num transferProgress := 0;
```

Store metadata:

```rapid
VAR num nbTrajAvailable := 0;
VAR trajCenterTrajMeta trajectories{256};
```

Loaded trajectory:

```rapid
VAR num nbLoadedTrajPoints := 0;
VAR trajCenterPointData trajData{100000};
VAR trajCenterProcessParameter processParams{256,10};
```

Index convention:

```text
selectedTrajIndex = 0                  no selection
selectedTrajIndex = 1..nbTrajAvailable valid trajectory
```

---

## `.trajcenter` archive format

A `.trajcenter` archive is a ZIP file containing at least:

```text
meta.json
points.parquet
```

### Required geometric columns

| Column | Purpose          |
| ------ | ---------------- |
| `x`  | ABB X position   |
| `y`  | ABB Y position   |
| `z`  | ABB Z position   |
| `q1` | ABB quaternion w |
| `q2` | ABB quaternion x |
| `q3` | ABB quaternion y |
| `q4` | ABB quaternion z |

### Robot-related columns

| Column                             | Purpose                                       |
| ---------------------------------- | --------------------------------------------- |
| `cf1`, `cf4`, `cf6`, `cfx` | ABB confdata                                  |
| `eax_a..eax_f`                   | Optional external axes                        |
| `tcp_speed`                      | TCP speed in mm/s                             |
| `zone_type`                      | ABB zone                                      |
| `move_type`                      | `MoveL`, `MoveJ`, `MoveC`               |
| `tool_name`                      | Tool name resolved against`trajTools`       |
| `wobj_name`                      | Workobject name resolved against`trajWobjs` |
| `readconfs`                      | Whether confdata should be used               |
| `process_type`                   | Optional process type                         |
| `process_params`                 | Optional process parameters                   |
| `process_param_index`            | Ignored on send, recomputed by the PC         |

Important rule:

```text
9E+9 must never be stored inside .trajcenter archives.
```

Missing or NaN external axes are represented locally as missing values and are
serialized as `9E+9` only when writing to RAPID through RWS.

---

## Robot-side resolution

Before a transfer, TrajCenter reads the robot context:

- robot defaults;
- available tools;
- available workobjects;
- process catalogue.

The resolver then builds a fully resolved trajectory:

| Local value              | RAPID output                         |
| ------------------------ | ------------------------------------ |
| `tool_name`            | base-1`toolIndex`                  |
| `wobj_name`            | base-1`wobjIndex`                  |
| `move_type`            | `0`, `1`, `2`                  |
| `zone_type`            | validated ABB zone                   |
| `tcp_speed`            | `tcpSpeed`                         |
| local process parameters | base-1`processParamIndex` or `0` |

The PC must not silently invent:

- tool;
- workobject;
- speed;
- zone.

Missing values may only be filled when the corresponding RAPID default is
explicitly enabled.

---

## Supported zones

```text
0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 255
```

Convention:

```text
0   = z0
255 = fine
```

---

## Supported movements

|  Code | Movement  | Accepted aliases        |
| ----: | --------- | ----------------------- |
| `0` | `MoveL` | `L`, `MoveL`, `0` |
| `1` | `MoveJ` | `J`, `MoveJ`, `1` |
| `2` | `MoveC` | `C`, `MoveC`, `2` |

### MoveC encoding

```text
MoveC = two consecutive C,C points
C,C,C,C is valid
C,C,C is invalid
```

For each `C,C` pair, the following values must be identical:

```text
tcpSpeed
toolIndex
wobjIndex
zoneType
readConfs
processParamIndex
```

---

## Metadata refresh pipeline

RAPID trigger:

```rapid
refreshMetaRequest := TRUE;
```

PC-side processing:

```text
1. Receive refreshMetaRequest = TRUE through RWS subscription.
2. Scan trajectory_store/.
3. Load .trajcenter archives.
4. Extract metadata: name, point count, process type.
5. Write nbTrajAvailable.
6. Write trajectories{1..nbTrajAvailable}.
7. Write OK state.
8. Reset refreshMetaRequest to FALSE.
```

Archives are sorted in a stable order on the PC side. The order written to
`trajectories` must remain identical to the order later used to resolve
`selectedTrajIndex`.

---

## Trajectory transfer pipeline

RAPID trigger:

```rapid
selectedTrajIndex := k;
sendTrajRequest := TRUE;
```

PC-side processing:

```text
1. Receive sendTrajRequest = TRUE through RWS subscription.
2. Read selectedTrajIndex.
3. Map base-1 RAPID index to local archive.
4. Load the selected .trajcenter archive.
5. Read robot context.
6. Resolve trajectory.
7. Acquire Mastership.
8. Write initial state: trajReady FALSE, transferError FALSE, progress 0.
9. Write nbLoadedTrajPoints.
10. Write processParams if needed.
11. Write trajData{1..nbLoadedTrajPoints}.
12. Update transferProgress.
13. Write final state: progress 100, lastErrorCode 200002, trajReady TRUE.
14. Reset sendTrajRequest to FALSE.
15. Release Mastership.
```

On error:

```text
trajReady = FALSE
transferError = TRUE
lastErrorCode = error code
lastError = short message
sendTrajRequest = FALSE
refreshMetaRequest = FALSE if the error occurred during refresh
```

All RWS writes must be performed under Mastership with guaranteed release.

---

## Development workflow

### Format generated package files

```powershell
pixi run -e dev pyinit-write
```

### Lint

```powershell
pixi run -e dev ruff check .
```

### Type-check

```powershell
pixi run -e dev typecheck
```

### Run tests

```powershell
pixi run -e dev tests
```

Recommended validation before commit:

```powershell
pixi run -e dev pyinit-write
pixi run -e dev ruff check .
pixi run -e dev typecheck
pixi run -e dev tests
```

Latest known local validation:

```text
ruff check .                  OK
mypy trajcenter/              OK
pytest tests/                 866 passed
global coverage               78%
```

The global coverage includes Textual UI screens and long-running robot paths
that are not fully exercised by automated tests.

---

## Test coverage

The test suite covers:

- CLI;
- APT, CSV, Excel and MOD conversion;
- column mapping;
- core `Trajectory` model;
- CSV / Excel export;
- local `.trajcenter` store;
- robot context parsing;
- robot trajectory resolution;
- RWS reader with mocks;
- RWS writer with mocks;
- robot service;
- robot supervisor;
- robot error mapping;
- main TUI screens.

---

## Robot integration test checklist

The following tests require a real ABB RobotWare 6.x controller or a RobotStudio
virtual controller.

### Controller preparation

- Load the RAPID system module:

```rapid
MODULE TRAJCENTER(SYSMODULE)
```

- Compile the module.
- Check that the RWS target module is:

```text
TRAJCENTER
```

- Verify that the expected RWS symbols exist:
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

### Connection and Mastership

Check:

- RWS login;
- simple symbol read;
- clean error on invalid credentials;
- clean timeout on unreachable controller;
- Mastership acquisition;
- simple write under Mastership;
- guaranteed Mastership release;
- retry behavior when Mastership is temporarily refused.

### RWS subscriptions

Check:

- subscription creation on `refreshMetaRequest`;
- subscription creation on `sendTrajRequest`;
- reception of `TRUE` events;
- ignored `FALSE` events;
- clean subscription deletion on shutdown;
- supervisor restart after interruption.

### Metadata refresh

Procedure:

```rapid
refreshMetaRequest := TRUE;
```

Expected result:

```text
refreshMetaRequest = FALSE
transferError = FALSE
lastErrorCode = 200001
lastError = ""
nbTrajAvailable > 0
trajectories{1..nbTrajAvailable} matches trajectory_store/
```

### Nominal trajectory transfer

Procedure:

```rapid
selectedTrajIndex := 1;
sendTrajRequest := TRUE;
```

Expected result:

```text
sendTrajRequest = FALSE
trajReady = TRUE
transferError = FALSE
lastErrorCode = 200002
lastError = ""
transferProgress = 100
nbLoadedTrajPoints = expected point count
trajData{1..nbLoadedTrajPoints} populated
```

### TUI robot supervision

Check:

- `Start supervision` button starts the subprocess;
- logs are visible in the TUI console;
- button changes to `Stop supervision`;
- stop via button;
- stop via `X`;
- ABB subscription is cleaned up;
- supervisor can be started again.

### Robustness

Test cases:

- PC stop during metadata refresh;
- PC stop during trajectory transfer;
- network loss;
- supervisor restart;
- request already set to `TRUE` before supervisor startup;
- temporary Mastership refusal;
- controller restart.

Expected behavior:

- no durable orphan subscription;
- no blocked Mastership;
- flags return to a coherent state;
- pending requests are detected on restart when still `TRUE`.

---

## Status and error codes

|       Code | Meaning                              |
| ---------: | ------------------------------------ |
| `200000` | OK                                   |
| `200001` | Metadata refreshed                   |
| `200002` | Trajectory transferred               |
| `400001` | `selectedTrajIndex` out of range   |
| `400002` | Trajectory file not found            |
| `400003` | Invalid`.trajcenter` format        |
| `400004` | Too many points                      |
| `400005` | Invalid`zone_type`                 |
| `400006` | Invalid`move_type`                 |
| `400007` | Invalid`MoveC` pair                |
| `400008` | Missing`tcp_speed` without default |
| `400009` | Missing`zone_type` without default |
| `400010` | Missing`tool_name` without default |
| `400011` | Missing`wobj_name` without default |
| `400012` | Unknown robot tool                   |
| `400013` | Unknown robot workobject             |
| `400014` | Invalid speed                        |
| `400015` | Invalid`readConfs`                 |
| `400016` | Invalid robtarget                    |
| `400017` | Unknown process                      |
| `400018` | Too many process sets                |
| `400019` | Invalid process parameters           |
| `401001` | RWS authentication refused           |
| `403001` | Mastership refused                   |
| `403002` | RWS write forbidden                  |
| `404001` | RAPID symbol not found               |
| `404002` | `trajTools` not found              |
| `404003` | `trajWobjs` not found              |
| `404004` | Trajectory store not found           |
| `404005` | Robot default not found              |
| `404006` | `processTypes` not found           |
| `408001` | RWS request timeout                  |
| `408002` | Transfer timeout                     |
| `409001` | Transfer already running             |
| `409002` | Incompatible robot state             |
| `500001` | Internal client error                |
| `500002` | Serialization error                  |
| `500003` | Trajectory conversion error          |
| `502001` | Invalid RWS response                 |
| `503001` | Controller unavailable               |
| `504001` | Controller timeout                   |

---

## Contribution rules

Main rules:

- Python >= 3.11;
- Pixi-managed environments only;
- typed code;
- no Ruff warning;
- no mypy error;
- tests required;
- HTTP mocks for automated RWS tests;
- logging through the project logging system;
- no RAPID write outside Mastership;
- no return to the TrajCenter v1 TCP protocol.

Before committing:

```powershell
pixi run -e dev pyinit-write
pixi run -e dev ruff check .
pixi run -e dev typecheck
pixi run -e dev tests
```

---

## History

### v1

Legacy TCP/IP version where the ABB robot acted as a TCP client.

This version is obsolete.

### v2

Current version based exclusively on ABB Robot Web Services:

- single RAPID system module `TRAJCENTER`;
- RWS subscriptions;
- RWS reads;
- RWS writes;
- Mastership;
- `.trajcenter` archives;
- CLI;
- Textual TUI;
- event-driven PC pipeline.
