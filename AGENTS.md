# AGENTS.md

## Project Goal

Build a production-oriented GitHub Issue Contribution Assistant for humans who want to contribute to open source projects and grow engineering ability.

The product should help users understand issues, locate relevant code, decide whether an issue is worth attempting, plan validation, and communicate with maintainers.

## Task Routes

- Product scope and user workflow: read `docs/product-specs/mvp.md`.
- Architecture or module boundary: read `ARCHITECTURE.md` and `docs/design-docs/index.md`.
- Current execution work: read `docs/exec-plans/active/`.
- Code navigation and commands: read `docs/project-map.md`.

## Key Directories

- `src/`: product code.
- `tests/`: runnable checks.
- `docs/`: specs, design notes, plans, decisions, reviews.
- `scripts/`: repeatable local commands.

## Verification

Run:

```bash
./scripts/check-docs.sh
pytest
patchpath analyze --repo <local-repo-path> --issue <owner/repo#number>
```

Use `--offline` only when GitHub issue fetching is unavailable and the issue is
covered by a real fixture from `docs/eval-set-v0.md`.

## Rules

- Do not make auto-PR generation the default MVP path.
- Do not add an agent framework before a simple traceable CLI proves the workflow.
- Keep outputs evidence-backed: file paths, issue text, commands, and trace.
- Prefer small contribution plans over large speculative patches.
- Treat LLM output as an untrusted boundary: normalize harmless shape drift
  once at the schema boundary, reject missing/unsafe/ungrounded content with a
  clear error, and add regression tests for whole classes of drift rather than
  one-off field fixes.
