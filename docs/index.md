# Docs Index

## Current Status

M1 CLI vertical slice verified. Product direction and V1 retrieval design are
defined; `patchpath analyze` generates `brief.md` and `trace.jsonl` for real
issues.

## Core Entry

- Product entry: `README.md`
- Agent entry: `AGENTS.md`
- Architecture entry: `ARCHITECTURE.md`
- Project map: `docs/project-map.md`

## Stable Product Specs

- `docs/product-specs/mvp.md`

## Design Docs

- `docs/design-docs/index.md`
- `docs/design-docs/tool-execution-retrieval-experiment.md`

## Evaluation

- `docs/eval-set-v0.md`

## Active Plans

- `docs/exec-plans/active/day-01-bootstrap.md`

## Decisions

- `docs/decisions/`

## Verification

```bash
uv sync --extra dev
source .venv/bin/activate
./scripts/check-docs.sh
pytest
patchpath analyze --repo ../click --issue pallets/click#3502
```
