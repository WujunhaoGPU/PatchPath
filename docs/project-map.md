# Project Map

## Project Summary

PatchPath helps human contributors understand open source issues and produce small, well-scoped contribution plans.

## Runtime Entry

CLI:

```bash
patchpath analyze --repo <local-repo-path> --issue <github-issue-url-or-owner/repo#number>
```

## Main Modules

- `src/patchpath/cli.py`: M1 CLI, issue intake, `rg + heuristics` retrieval,
  brief rendering, and JSONL trace writing.
- `tests/test_m1_cli.py`: minimal M1 behavior checks.

## Common Commands

```bash
./scripts/check-docs.sh
pytest
patchpath analyze --repo <local-repo-path> --issue <owner/repo#number>
```

## Test And Acceptance Commands

Current:

```bash
./scripts/check-docs.sh
pytest
```

Manual CLI smoke:

```bash
patchpath analyze --repo ../click --issue pallets/click#3502
```

## Known Risks

- Building an auto-PR bot too early would move the product into a crowded and harder-to-verify space.
- LLM output without citations would be hard for contributors to trust.
- Eval must start with real issue samples, not synthetic examples.

## Next Handoff

Run the five issues in `docs/eval-set-v0.md` against a local `pallets/click`
checkout and confirm at least 4/5 gold source files appear in Top-5.
