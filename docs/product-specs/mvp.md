# MVP Product Spec

## Goal

Help a human contributor move from “I found an issue” to “I know whether and how to contribute safely.”

## Users

- Developers learning through open source contribution.
- Contributors who need help understanding unfamiliar repositories.
- People who want to grow engineering judgment, not just submit generated code.

## Problem

New contributors often fail before writing code:

- They pick issues that are unclear, stale, or too large.
- They cannot identify the relevant files.
- They do not know how to reproduce or validate the issue.
- They cannot explain a proposed change in a way maintainers trust.

## Scope

The MVP produces a contribution brief from a repo and issue.

Required sections:

- project summary
- issue summary
- clarity assessment
- contribution suitability
- related files
- reading order
- likely change area
- validation command or missing validation information
- risks
- maintainer communication draft
- trace

## Non-Goals

- Automatic patch generation.
- Automatic PR creation.
- Full IDE integration.
- Complex multi-agent runtime.
- Vector database requirement before text retrieval proves insufficient.

## Core User Path

1. User provides repo and issue.
2. Tool fetches issue context.
3. Tool inspects repository files.
4. Tool returns a contribution brief with cited evidence.
5. User decides whether to proceed, ask a clarifying question, or skip the issue.

## Acceptance Criteria

- For 5 real issues, the brief identifies at least one useful related file or explains why code location is uncertain.
- Output includes trace and evidence, not only a summary.
- The tool can mark issues as not worth attempting when context is missing or scope is too large.
- A human can use the brief as a starting point for reading code or writing a maintainer comment.

## Related Plans

- `docs/exec-plans/active/day-01-bootstrap.md`
