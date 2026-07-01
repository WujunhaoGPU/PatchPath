# Project Map

## Project Summary

PatchPath helps human contributors understand open source issues and produce small, well-scoped contribution plans.

## Runtime Entry

No runtime entry yet.

Planned CLI:

```bash
issue-agent analyze --repo <repo-url> --issue <issue-url>
```

## Main Modules

Planned:

- `src/ingestion/`
- `src/retrieval/`
- `src/analysis/`
- `src/evaluation/`
- `src/presentation/`

## Common Commands

```bash
./scripts/check-docs.sh
```

## Test And Acceptance Commands

Current:

```bash
./scripts/check-docs.sh
```

Future:

```bash
pytest
issue-agent analyze --repo <repo-url> --issue <issue-url>
```

## Known Risks

- Building an auto-PR bot too early would move the product into a crowded and harder-to-verify space.
- LLM output without citations would be hard for contributors to trust.
- Eval must start with real issue samples, not synthetic examples.

## Next Handoff

Read `docs/product-specs/mvp.md`, then fill `docs/eval-set-v0.md` with 5 real issues.
