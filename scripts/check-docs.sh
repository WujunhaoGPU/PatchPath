#!/usr/bin/env bash
set -euo pipefail

required=(
  "README.md"
  "AGENTS.md"
  "ARCHITECTURE.md"
  ".env.example"
  "pyproject.toml"
  "uv.lock"
  "docs/index.md"
  "docs/project-map.md"
  "docs/product-specs/mvp.md"
  "docs/eval-set-v0.md"
  "docs/design-docs/index.md"
  "docs/design-docs/agent-runtime-choice.md"
  "docs/design-docs/tool-execution-retrieval-experiment.md"
  "docs/exec-plans/active/day-01-bootstrap.md"
  "docs/exec-plans/tech-debt-tracker.md"
  "docs/core-beliefs.md"
  "docs/quality-scorecard.md"
  "docs/reviews/m1-click-3502-brief.md"
  "docs/prototypes/patchpath-web-demo.html"
  "scripts/eval-v0.sh"
  "src/patchpath/cli.py"
  "src/patchpath/web.py"
  "tests/test_m1_cli.py"
  "tests/test_web.py"
)

for path in "${required[@]}"; do
  test -s "$path" || {
    echo "missing or empty: $path" >&2
    exit 1
  }
done

echo "docs ok"
