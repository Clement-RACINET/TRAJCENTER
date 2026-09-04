# Ruff diagnostics

Return code: `1`

Issues: `1`

## Command

```text
C:\Users\ClementRACINET\git\gitlab_ensam\TRAJCENTER\trajcenter_v2\.pixi\envs\dev\python.exe -m ruff check src tests --output-format json --exclude .git --exclude .hg --exclude .mypy_cache --exclude .pytest_cache --exclude .ruff_cache --exclude .tox --exclude .venv --exclude venv --exclude .pixi --exclude __pycache__ --exclude build --exclude dist --exclude docs/build --exclude docs/src/api --exclude docs/src/examples --exclude docs/src/diagnostics --exclude docs/src/diagrams --exclude *.pyc --exclude *.pyo
```

## Parsed issues

| Code | File | Line | Message |
|---|---|---:|---|
| `E902` | `src` | 1 | Le fichier spécifié est introuvable. (os error 2) |

## Raw output

```text
[
  {
    "cell": null,
    "code": "E902",
    "end_location": {
      "column": 1,
      "row": 1
    },
    "filename": "C:\\Users\\ClementRACINET\\git\\gitlab_ensam\\TRAJCENTER\\trajcenter_v2\\src",
    "fix": null,
    "location": {
      "column": 1,
      "row": 1
    },
    "message": "Le fichier spécifié est introuvable. (os error 2)",
    "name": "io-error",
    "noqa_row": null,
    "severity": "error",
    "url": "https://docs.astral.sh/ruff/rules/io-error"
  }
]
```
