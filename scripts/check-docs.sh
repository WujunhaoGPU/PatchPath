#!/usr/bin/env bash
set -euo pipefail

required=(
  "README.md"
  "AGENTS.md"
  "ARCHITECTURE.md"
  "docs/index.md"
  "docs/project-map.md"
  "docs/product-specs/mvp.md"
  "docs/design-docs/index.md"
  "docs/design-docs/agent-runtime-choice.md"
  "docs/exec-plans/active/day-01-bootstrap.md"
  "docs/exec-plans/tech-debt-tracker.md"
  "docs/core-beliefs.md"
  "docs/quality-scorecard.md"
)

for path in "${required[@]}"; do
  test -s "$path" || {
    echo "missing or empty: $path" >&2
    exit 1
  }
done

echo "docs ok"
