# Day 01 Bootstrap Plan

## Goal

Create the repository skeleton and lock the product positioning before implementation.

## Files

- `README.md`
- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/project-map.md`
- `docs/product-specs/mvp.md`
- `docs/eval-set-v0.md`
- `docs/design-docs/agent-runtime-choice.md`
- `docs/design-docs/tool-execution-retrieval-experiment.md`
- `scripts/check-docs.sh`

## Tasks

- [x] Define product positioning.
- [x] Document MVP scope and non-goals.
- [x] Add project map and repository rules.
- [x] Accept the first Agent runtime architecture.
- [x] Create `docs/eval-set-v0.md` with 5 real issues.
- [x] Accept Tool Execution V1 retrieval strategy: default `rg + heuristics`, optional `rg + CodeGraph`.
- [x] Build the first CLI proof for one issue.
- [x] Create lightweight review notes from the first generated brief.

## Verification

```bash
./scripts/check-docs.sh
pytest
patchpath analyze --repo ../click --issue pallets/click#3502
```

## Current Status

Bootstrap, retrieval-design docs, and the first CLI vertical slice are complete.
Next work is cross-repo eval expansion before changing the runtime shape.
