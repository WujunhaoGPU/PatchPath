# Tool Execution Retrieval Experiment

Status: accepted for V1 Tool Execution
Date: 2026-07-01
Related eval set: `docs/eval-set-v0.md`

## Question

Can CodeGraph improve Tool Execution search quality for PatchPath without
becoming a mandatory MVP dependency?

## Setup

- Repository: `pallets/click`
- Temp checkout: `/tmp/patchpath-codegraph-exp.VSVyTj/click`
- CodeGraph: `0.9.9`
- CodeGraph index: 72 files, 2,583 nodes, 4,815 edges
- Gold: merged PR changed source and test files from `docs/eval-set-v0.md`

## Strategies

| Strategy | Method |
| --- | --- |
| `rg only` | Run fixed-string `rg` over the Search Planning terms and rank files by raw match count. |
| `rg + heuristics` | Use the same `rg` matches, then weight code-like terms, source paths, test paths, path/name matches, and penalize changelog/docs noise. |
| `rg + CodeGraph` | Start with `rg + heuristics`, then use CodeGraph symbol queries plus limited callers/callees/impact expansion for symbol-like terms. |

## Summary

| Strategy | Source Top-5 | Any Gold Top-5 | Average Source Rank |
| --- | ---: | ---: | ---: |
| `rg only` | 4/5 | 5/5 | 8.0 |
| `rg + heuristics` | 5/5 | 5/5 | 3.2 |
| `rg + CodeGraph` | 5/5 | 5/5 | 1.4 |

## Per-Issue Result

| Issue | Gold Source | `rg only` Source Rank | `rg + heuristics` Source Rank | `rg + CodeGraph` Source Rank |
| --- | --- | ---: | ---: | ---: |
| `pallets/click#3502` | `src/click/shell_completion.py` | 1 | 1 | 1 |
| `pallets/click#3487` | `src/click/utils.py` | 30 | 5 | 2 |
| `pallets/click#3458` | `src/click/core.py` | 2 | 2 | 1 |
| `pallets/click#3403` | `src/click/core.py` | 3 | 4 | 2 |
| `pallets/click#3360` | `src/click/formatting.py` | 4 | 4 | 1 |

## PatchPath Output Shape

These are the output-facing artifacts the best run could produce for the brief.

| Issue | Related File Top-K Signal | Candidate Snippet | Test Command |
| --- | --- | --- | --- |
| `pallets/click#3502` | `src/click/shell_completion.py`, `tests/test_shell_completion.py` | `FishComplete` and `format_completion` in `src/click/shell_completion.py` | `pytest tests/test_shell_completion.py` |
| `pallets/click#3487` | `src/click/utils.py`, `tests/test_utils.py` | `echo` in `src/click/utils.py` | `pytest tests/test_utils.py` |
| `pallets/click#3458` | `src/click/core.py`, `tests/test_defaults.py`, `tests/test_options.py` | `Context.get_parameter_source` in `src/click/core.py` | `pytest tests/test_defaults.py tests/test_options.py` |
| `pallets/click#3403` | `src/click/core.py`, `tests/test_options.py` | `Option` and option value handling in `src/click/core.py` | `pytest tests/test_options.py` |
| `pallets/click#3360` | `src/click/formatting.py`, `tests/test_formatting.py` | `HelpFormatter.write_usage` in `src/click/formatting.py` | `pytest tests/test_formatting.py` |

## Findings

- `rg only` is a useful fallback, but raw match count over-ranks tests,
  changelog, and broad modules. In `pallets/click#3487`, the actual source file
  `src/click/utils.py` was rank 30 because `echo` and stream terms matched many
  tests and runner helpers.
- `rg + heuristics` is the right MVP baseline. It got every source file into
  Top-5 with no external index.
- `rg + CodeGraph` improved ranking when the issue contained symbol-like terms:
  `HelpFormatter`, `write_usage`, `get_parameter_source`, `FishComplete`, and
  `echo`.
- CodeGraph did not replace `rg`. It needed Search Planning seed terms and was
  most useful as a structural boost over already-collected text evidence.

## Recommendation

Implement Tool Execution V1 with two active states:

- Default state: `rg + heuristics`.
- Enhanced state: `rg + CodeGraph`, enabled when CodeGraph is available for the
  target repo.

```text
rg text evidence
-> heuristic ranking
-> optional CodeGraph symbol expansion
-> merged candidate files and snippets
-> trace with provider, query, result count, selected paths, warnings
```

Do not make CodeGraph mandatory for MVP. It is part of the V1 design as an
optional enhancement, not a hard dependency. Fall back cleanly to
`rg + heuristics` when it is missing, stale, or unsupported for the target
language.

## Trace Fields To Keep

- `provider`: `rg`, `heuristics`, or `codegraph`
- `query`
- `command`
- `result_count`
- `selected_paths`
- `evidence_ids`
- `fallback_reason`
- `warnings`
- `duration_ms`
- `exit_code`

## Next Validation

Add five cross-repo issues before making CodeGraph mandatory or changing the
runtime shape. The minimum useful spread is one Python CLI repo, one
JavaScript/TypeScript repo, one docs issue, one test-only issue, and one issue
with no explicit file path.
