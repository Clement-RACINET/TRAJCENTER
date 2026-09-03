
# TrajCenter v2 Reorganization Plan

Project: TrajCenter
Target version: v2.x modular architecture
Current branch baseline: dev renamed to v2
Working branch: v2/modular-architecture
Main goal: split conversion, robot communication, CLI/TUI, and RAPID assets cleanly while keeping one repository.

---

## 0. Guiding principles

- Keep one repository for now.
- Separate APIs by responsibility:
  - core data model and validation;
  - file conversion;
  - file export;
  - robot communication;
  - CLI/TUI applications;
  - RAPID controller-side code.
- Keep conversion usable without robot dependencies.
- Make robot/RWS support optional.
- Keep RAPID files versioned with the Python robot client.
- Keep changes incremental and testable.
- Avoid breaking existing behavior without a compatibility layer.
- Prefer small commits per step.
- Keep all RAPID files ASCII only.
- Keep RAPID identifiers below 30 characters.

---

## 1. Branch strategy

### 1.1 Rename current branch

Current branch:

```bash
dev
```

Target branch:

```bash
v2
```

Command:

```bash
git branch -m dev v2
```

If the branch already exists remotely, update remote references carefully.

Suggested sequence:

```bash
git status
git branch --show-current
git branch -m dev v2
git push origin v2
git push origin --delete dev
git branch --set-upstream-to=origin/v2 v2
```

Only delete remote `dev` after confirming that `v2` exists remotely.

### 1.2 Create work branch

From `v2`:

```bash
git checkout v2
git pull
git checkout -b v2/modular-architecture
```

Push it:

```bash
git push -u origin v2/modular-architecture
```

---

## 2. Target product layers

TrajCenter will be organized around the following layers.

### 2.1 Core layer

Responsibility:

- trajectory data model;
- common validation;
- common serialization;
- `.trajcenter` format;
- shared messages and logging.

Target package:

```text
trajcenter/core
```

Must not import:

```text
trajcenter.convert
trajcenter.export
trajcenter.robot
trajcenter.cli
```

### 2.2 Convert layer

Responsibility:

- import from source files;
- Excel to trajectory;
- CSV to trajectory;
- MOD to trajectory;
- APT to trajectory;
- tabular conversion;
- column mapping;
- conversion defaults.

Target package:

```text
trajcenter/convert
```

Must not import:

```text
trajcenter.robot
```

### 2.3 Export layer

Responsibility:

- export trajectory to Excel;
- export trajectory to CSV;
- export tabular representations.

Target package:

```text
trajcenter/export
```

Must not import:

```text
trajcenter.robot
```

### 2.4 Robot layer

Responsibility:

- robot communication;
- ABB RWS implementation;
- RAPID variable reader/writer;
- trajectory resolution against robot tools/wobjs/defaults;
- RWS supervisor;
- robot-specific errors.

Target package:

```text
trajcenter/robot/abb
```

Temporary compatibility package:

```text
trajcenter/rws
```

The old `trajcenter/rws` package may remain during migration, but new code should target `trajcenter.robot.abb`.

### 2.5 CLI layer

Responsibility:

- terminal commands;
- conversion commands;
- store inspection;
- robot supervisor commands;
- optional launch of TUI.

Target package:

```text
trajcenter/cli
```

Command entry point:

```bash
trajcenter
```

### 2.6 TUI layer

Responsibility:

- optional terminal user interface;
- rich/textual-based UI;
- interactive store browser;
- interactive robot operations.

Target package:

```text
trajcenter/ui
```

Optional dependency group:

```text
tui
```

### 2.7 RAPID layer

Responsibility:

- ABB RAPID modules;
- system module;
- demo modules;
- FlexPendant GUI demo;
- RAPID README and loading instructions.

Target directory:

```text
rapid
```

Rules:

- ASCII only;
- identifier length below 30 characters;
- keep synchronized with robot ABB Python client.

---

## 3. Target repository structure

Long-term target:

```text
trajcenter
├── docs
│   ├── architecture
│   │   └── TRAJCENTER_V2_REORG_PLAN.md
│   ├── manual
│   ├── validation
│   │   └── TRAJCENTER_VALIDATION_MATRIX.md
│   └── api
│
├── rapid
│   ├── TRAJCENTER.sys
│   ├── TRAJCENTER_DEMO.mod
│   ├── TRAJCENTER_DEMO.pgf
│   ├── TRAJCENTER_GUI_DEMO.mod
│   ├── TRAJCENTER_GUI_DEMO.pgf
│   └── README.md
│
├── scripts
│   ├── examples
│   ├── doc
│   └── maintenance
│
├── tests
│   ├── core
│   ├── convert
│   ├── export
│   ├── robot
│   │   └── abb
│   ├── cli
│   └── integration
│
├── trajcenter
│   ├── __init__.py
│   │
│   ├── core
│   │   ├── __init__.py
│   │   ├── trajectory.py
│   │   ├── validation.py
│   │   ├── schema.py
│   │   ├── defaults.py
│   │   ├── messages.py
│   │   └── logger.py
│   │
│   ├── convert
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── apt.py
│   │   ├── csv.py
│   │   ├── excel.py
│   │   ├── mod.py
│   │   ├── tabular.py
│   │   └── column_mapper.py
│   │
│   ├── export
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── csv.py
│   │   ├── excel.py
│   │   ├── tabular.py
│   │   └── options.py
│   │
│   ├── robot
│   │   ├── __init__.py
│   │   └── abb
│   │       ├── __init__.py
│   │       ├── constants.py
│   │       ├── models.py
│   │       ├── reader.py
│   │       ├── writer.py
│   │       ├── resolver.py
│   │       ├── service.py
│   │       ├── store.py
│   │       ├── supervisor.py
│   │       ├── _utils.py
│   │       └── errors
│   │           ├── __init__.py
│   │           ├── base.py
│   │           ├── codes.py
│   │           └── translate.py
│   │
│   ├── rws
│   │   └── compatibility wrappers during migration
│   │
│   ├── cli
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── convert_cmd.py
│   │   ├── export_cmd.py
│   │   ├── store_cmd.py
│   │   ├── robot_cmd.py
│   │   └── tui_cmd.py
│   │
│   └── ui
│       ├── __init__.py
│       ├── terminal.py
│       └── widgets.py
│
├── trajectory_files
├── trajectory_store
├── trajectory_exports
├── mkdocs.yml
├── pyproject.toml
├── README.md
└── pixi.toml
```

---

## 4. Dependency strategy

### 4.1 Base install

Base install should support:

- trajectory model;
- validation;
- conversion;
- export;
- store read/write;
- no robot communication.

Example:

```bash
pip install trajcenter
```

or during development:

```bash
pip install -e .
```

Base dependencies should not include ABB/RWS-specific libraries if avoidable.

### 4.2 Optional robot install

Robot/RWS features:

```bash
pip install "trajcenter[robot]"
```

Contains dependencies for:

- HTTP client;
- WebSocket/subscription handling;
- robot communication helpers.

### 4.3 Optional CLI/TUI install

CLI:

```bash
pip install "trajcenter[cli]"
```

TUI:

```bash
pip install "trajcenter[tui]"
```

Full install:

```bash
pip install "trajcenter[all]"
```

### 4.4 pyproject target

Add or update:

```toml
[project.optional-dependencies]
robot = []
cli = []
tui = []
docs = []
dev = []
all = []

[project.scripts]
trajcenter = "trajcenter.cli.main:app"
```

Exact dependencies will be defined during implementation.

---

## 5. CLI target commands

Initial CLI commands:

```bash
trajcenter --help
trajcenter version
trajcenter store list
trajcenter store inspect NAME
trajcenter store validate NAME
trajcenter convert INPUT --out OUTPUT
trajcenter export INPUT --out OUTPUT
trajcenter robot check
trajcenter robot supervise
trajcenter tui
```

Priority order:

1. `trajcenter version`
2. `trajcenter store list`
3. `trajcenter store inspect`
4. `trajcenter convert`
5. `trajcenter robot check`
6. `trajcenter robot supervise`
7. `trajcenter tui`

---

## 6. Robot configuration file

Target config file example:

```toml
# trajcenter.robot.toml

[robot]
host = "192.168.125.1"
username = "Default User"
password_env = "TRAJCENTER_ROBOT_PASSWORD"
rw_version = "6"

[store]
path = "trajectory_store"

[rapid]
task = "T_ROB1"
module = "TRAJCENTER"

[supervisor]
request_timeout_sec = 30
transfer_timeout_sec = 120
poll_interval_sec = 0.1
```

Do not commit real passwords.

---

## 7. Migration steps

### STEP 00 - Prepare branch

Goal:

- rename `dev` to `v2`;
- create `v2/modular-architecture`.

Tasks:

- check clean git status;
- rename branch;
- push branch;
- create work branch.

Validation:

```bash
git branch --show-current
```

Expected:

```text
v2/modular-architecture
```

---

### STEP 01 - Add this plan file

Goal:

- store the reorganization plan in the repository.

Tasks:

- create `doc_manual/TRAJCENTER_V2_REORG_PLAN.md`;
- commit it.

Commit message:

```text
docs: add v2 reorganization plan
```

---

### STEP 02 - Fix documentation folders

Goal:

- prepare a clearer docs structure.

Tasks:

- create `docs/architecture`;
- create `docs/validation`;
- move validation matrix;
- eventually move this plan file.

From:

```text
doc_manual/TRAJCENTER_VALIDATION_MATRIX.md.md
```

To:

```text
docs/validation/TRAJCENTER_VALIDATION_MATRIX.md
```

From:

```text
doc_manual/TRAJCENTER_V2_REORG_PLAN.md
```

To:

```text
docs/architecture/TRAJCENTER_V2_REORG_PLAN.md
```

Validation:

- files open correctly;
- links will be updated later.

Commit message:

```text
docs: reorganize architecture and validation docs
```

---

### STEP 03 - Add package boundaries without moving logic

Goal:

- create new package folders;
- do not move existing code yet.

Tasks:

Create:

```text
trajcenter/convert
trajcenter/export
trajcenter/robot
trajcenter/robot/abb
trajcenter/cli
trajcenter/ui
```

Add minimal `__init__.py` files.

Validation:

```bash
python -c "import trajcenter; print('ok')"
python -c "import trajcenter.convert; print('ok')"
python -c "import trajcenter.export; print('ok')"
python -c "import trajcenter.robot.abb; print('ok')"
python -c "import trajcenter.cli; print('ok')"
```

Commit message:

```text
refactor: add modular package boundaries
```

---

### STEP 04 - Add pyproject optional dependencies

Goal:

- define install profiles.

Tasks:

- add or update optional dependencies:
  - robot;
  - cli;
  - tui;
  - docs;
  - dev;
  - all.
- add script entry point `trajcenter`.

Validation:

```bash
pip install -e ".[cli]"
trajcenter --help
```

At this step, CLI may only show a minimal help/version command.

Commit message:

```text
build: add optional dependency groups
```

---

### STEP 05 - Add minimal CLI

Goal:

- provide first terminal entry point.

Tasks:

Create:

```text
trajcenter/cli/main.py
```

Implement:

```bash
trajcenter --help
trajcenter version
```

Preferred libraries:

- Typer for CLI;
- Rich for nicer output.

Validation:

```bash
trajcenter --help
trajcenter version
```

Commit message:

```text
feat(cli): add initial command line interface
```

---

### STEP 06 - Add store CLI commands

Goal:

- inspect trajectory store from terminal.

Tasks:

Create:

```text
trajcenter/cli/store_cmd.py
```

Implement:

```bash
trajcenter store list
trajcenter store inspect NAME
```

Validation:

```bash
trajcenter store list --store trajectory_store
trajcenter store inspect 000_trajectory_demo --store trajectory_store
```

Commit message:

```text
feat(cli): add trajectory store commands
```

---

### STEP 07 - Create conversion API facade

Goal:

- expose a stable conversion API without changing internals too much.

Tasks:

- add `trajcenter/convert/__init__.py`;
- re-export existing converter classes/functions from `trajcenter.converter`;
- avoid importing robot/RWS modules.

Temporary compatibility:

```python
from trajcenter.converter.excel_converter import ExcelConverter
```

Validation:

```bash
python -c "from trajcenter.convert import ExcelConverter; print(ExcelConverter)"
```

Commit message:

```text
refactor(convert): add conversion API facade
```

---

### STEP 08 - Create export API facade

Goal:

- expose stable export API.

Tasks:

- add `trajcenter/export/__init__.py`;
- re-export existing exporter classes/functions from `trajcenter.exporter`;
- avoid importing robot/RWS modules.

Validation:

```bash
python -c "from trajcenter.export import ExcelExporter; print(ExcelExporter)"
```

Commit message:

```text
refactor(export): add export API facade
```

---

### STEP 09 - Add convert CLI command

Goal:

- convert files from terminal.

Tasks:

Create:

```text
trajcenter/cli/convert_cmd.py
```

Implement:

```bash
trajcenter convert INPUT --out OUTPUT
```

Initial supported formats:

- Excel;
- CSV if already supported;
- MOD if already supported;
- APT if already supported.

Validation:

```bash
trajcenter convert trajectory_files/test_basic.xlsx --out trajectory_store/test_cli.trajcenter
```

Commit message:

```text
feat(cli): add file conversion command
```

---

### STEP 10 - Add robot ABB facade

Goal:

- start moving from `trajcenter.rws` to `trajcenter.robot.abb`.

Tasks:

- add re-export wrappers in `trajcenter/robot/abb`;
- keep `trajcenter/rws` working;
- no behavior change.

Validation:

```bash
python -c "import trajcenter.robot.abb.service; print('ok')"
python -c "import trajcenter.rws.service; print('ok')"
```

Commit message:

```text
refactor(robot): add ABB robot API facade
```

---

### STEP 11 - Add robot CLI commands

Goal:

- expose robot operations from terminal.

Tasks:

Create:

```text
trajcenter/cli/robot_cmd.py
```

Implement initially:

```bash
trajcenter robot check
trajcenter robot supervise
```

Use config file:

```text
trajcenter.robot.toml
```

Validation:

```bash
trajcenter robot check --config trajcenter.robot.toml
```

Commit message:

```text
feat(cli): add robot command group
```

---

### STEP 12 - Move RWS implementation

Goal:

- move code physically from `trajcenter/rws` to `trajcenter/robot/abb`.

Tasks:

- move files;
- update imports;
- keep compatibility wrappers in `trajcenter/rws`;
- update tests.

Validation:

```bash
pytest tests/rws
pytest tests/robot
```

Commit message:

```text
refactor(robot): move RWS implementation under robot abb
```

---

### STEP 13 - Rename tests directories

Goal:

- align tests with new package names.

Tasks:

Move:

```text
tests/converter -> tests/convert
tests/exporter -> tests/export
tests/rws -> tests/robot/abb
```

Update imports as needed.

Validation:

```bash
pytest
```

Commit message:

```text
test: align test layout with modular packages
```

---

### STEP 14 - Add TUI skeleton

Goal:

- add terminal UI entry point.

Tasks:

Create:

```text
trajcenter/ui/terminal.py
trajcenter/cli/tui_cmd.py
```

Implement:

```bash
trajcenter tui
```

Initial behavior:

- show title;
- show store path;
- list trajectories;
- exit cleanly.

Validation:

```bash
trajcenter tui
```

Commit message:

```text
feat(tui): add initial terminal interface
```

---

### STEP 15 - Update docs

Goal:

- document new architecture and usage.

Tasks:

- update README;
- add architecture doc;
- add CLI usage doc;
- add robot config doc;
- update validation matrix location.

Validation:

```bash
mkdocs build
```

Commit message:

```text
docs: document modular architecture and CLI usage
```

---

### STEP 16 - Clean imports and enforce boundaries

Goal:

- ensure conversion does not depend on robot code.

Tasks:

- inspect imports;
- optionally add import-linter later;
- ensure base install works without robot optional dependencies.

Validation:

```bash
pip install -e .
python -c "import trajcenter.convert; print('convert ok')"
python -c "import trajcenter.export; print('export ok')"
```

Then:

```bash
pip install -e ".[robot,cli,tui]"
pytest
```

Commit message:

```text
refactor: enforce package dependency boundaries
```

---

### STEP 17 - Final integration test

Goal:

- verify all major features.

Tasks:

- run all tests;
- run CLI smoke tests;
- run conversion smoke test;
- run store list;
- run robot supervisor in test/sim environment if available;
- verify RAPID files still compile/load.

Validation:

```bash
pytest
trajcenter --help
trajcenter version
trajcenter store list
trajcenter convert trajectory_files/test_basic.xlsx --out trajectory_store/test_cli.trajcenter
```

Commit message:

```text
test: validate modular v2 architecture
```

---

## 8. Commit discipline

Preferred commit style:

```text
docs: ...
build: ...
refactor: ...
feat(cli): ...
feat(robot): ...
test: ...
fix: ...
```

Keep commits small.

Recommended rhythm:

- one step = one commit;
- do not mix large moves with behavior changes;
- keep compatibility wrappers until final cleanup.

---

## 9. Risks

| Risk                                       | Mitigation                                         |
| ------------------------------------------ | -------------------------------------------------- |
| Breaking existing imports                  | Add compatibility facades/wrappers                 |
| Robot optional deps imported by conversion | Avoid imports in`__init__.py`; test base install |
| Too large refactor                         | Small commits, step-by-step                        |
| CLI grows before API is stable             | Start with small commands only                     |
| RWS move breaks tests                      | Keep`trajcenter.rws` wrappers temporarily        |
| RAPID names too long                       | Keep identifiers below 30 chars                    |
| Encoding issues in RAPID                   | ASCII only                                         |

---

## 10. Current next action

Next action after saving this file:

1. Commit current work if needed.
2. Rename branch `dev` to `v2`.
3. Create branch `v2/modular-architecture`.
4. Commit this plan file on the new branch if not already committed.
