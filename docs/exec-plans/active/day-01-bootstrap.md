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
- [ ] Build the first CLI proof for one issue.
- [ ] Create lightweight review notes from the first generated brief.

## Verification

```bash
./scripts/check-docs.sh
```

## Current Status

Bootstrap and retrieval-design docs are complete. Next work is the first vertical slice: run `patchpath analyze` against one real issue and generate `brief.md` plus `trace.jsonl`.
