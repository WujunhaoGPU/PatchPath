# Project Map

## Project Summary

PatchPath helps developers grow engineering ability through guided participation in real GitHub issues. It combines automatic repository and issue analysis with coach-style guidance for reading, reasoning, validation, and maintainer communication.

## Runtime Entry

CLI:

```bash
patchpath analyze --repo <local-repo-path> --issue <github-issue-url-or-owner/repo#number>
```

Local web:

```bash
patchpath serve --port 8765
```

## Main Modules

- `src/patchpath/cli.py`: M1 CLI, issue intake, default `rg + CodeGraph +
  heuristics` retrieval, required DeepSeek analysis and coach guidance, brief
  rendering, and JSONL trace writing.
- `src/patchpath/web.py`: local stdlib HTTP server for the web prototype;
  serves `docs/prototypes/patchpath-web-demo.html`, exposes `POST /api/analyze`,
  and exposes test-environment planning/preparation endpoints.
- `tests/test_m1_cli.py`: minimal M1 behavior checks.
- `tests/test_web.py`: local web response and CLI serve dispatch checks.

## Common Commands

```bash
./scripts/check-docs.sh
uv run pytest
./scripts/eval-v0.sh
patchpath serve --port 8765
patchpath analyze --repo <local-repo-path> --issue <owner/repo#number>
```

Web behavior:

- The page takes a GitHub issue URL as the main input.
- The backend clones or reuses repositories under `~/.patchpath/repos/<owner>/<repo>/`.
- Set `PATCHPATH_REPOS_DIR` to override the repository cache root.
- The test environment button first previews the detected dependency command,
  then runs it only after explicit confirmation.

LLM config:

```bash
cp .env.example .env
```

Then edit `.env` and set `DEEPSEEK_API_KEY`.

## Test And Acceptance Commands

Current:

```bash
./scripts/check-docs.sh
uv run pytest
./scripts/eval-v0.sh
```

Manual CLI smoke:

```bash
patchpath analyze --repo ../click --issue pallets/click#3502
```

## Known Risks

- Building an auto-PR bot too early would move the product into a crowded and harder-to-verify space.
- LLM output without citations would be hard for contributors to trust.
- LLM analysis and coach guidance must not recommend files that are absent from trace evidence.
- CodeGraph may create `.codegraph/` in the analyzed target repository; do not commit it.
- Eval must start with real issue samples, not synthetic examples.

## Next Handoff

Run `./scripts/eval-v0.sh` against a local `pallets/click` checkout, then add
cross-repo eval cases before expanding beyond CLI.
