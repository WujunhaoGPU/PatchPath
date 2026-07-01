# Eval Set v0

Status: draft
Created: 2026-07-01

## Definition

This set uses closed GitHub issues with merged fixing PRs. Gold files are the
source and test files changed by the merged PR, excluding changelog-only and
docs-only files unless they are the target of the issue.

The first set intentionally uses one small repository, `pallets/click`, so
retrieval strategy can be compared without repo-size noise.

## Gold Issues

| Issue | Fix PR | Search Plan Terms | Gold Source | Gold Tests |
| --- | --- | --- | --- | --- |
| `pallets/click#3502` fish completion is broken in 8.4.1 | `pallets/click#3504` | `fish completion`, `fish`, `fish_complete`, `shell completion`, `CompletionItem`, `format_completion`, `string split`, `complete_var` | `src/click/shell_completion.py` | `tests/test_shell_completion.py` |
| `pallets/click#3487` Echoing empty bytes or bytearray raises TypeError | `pallets/click#3493` | `echo`, `empty bytes`, `bytearray`, `TypeError`, `BytesIO`, `nl=True`, `bytes-like object`, `file.write` | `src/click/utils.py` | `tests/test_utils.py` |
| `pallets/click#3458` `get_parameter_source()` returns `None` in 8.4.0 | `pallets/click#3484` | `get_parameter_source`, `ParameterSource`, `ctx.get_parameter_source`, `convert`, `default`, `nodefault`, `eager callbacks` | `src/click/core.py` | `tests/test_defaults.py`, `tests/test_options.py` |
| `pallets/click#3403` default behaviour changes with enable/disable boolean flag pair | `pallets/click#3404` | `flag_value`, `default=True`, `enable_xyz`, `boolean option`, `--without-xyz`, `--with-xyz`, `dual flags`, `default behaviour` | `src/click/core.py` | `tests/test_options.py` |
| `pallets/click#3360` Empty output from `HelpFormatter.write_usage` for a program without arguments | `pallets/click#3434` | `HelpFormatter.write_usage`, `HelpFormatter`, `write_usage`, `Usage: program`, `no args`, `empty output` | `src/click/formatting.py` | `tests/test_formatting.py` |

## Limits

- All five issues are from one repo. Add cross-repo cases before treating this
  as a product-wide benchmark.
- The experiment used the current default branch, not a pre-fix checkout.
  Changelog and newly added tests may make retrieval easier than a real
  pre-fix run.
- Search plan terms were hand-authored from issue text to simulate the output
  of the Search Planning node. This evaluates Tool Execution, not LLM search
  planning.
