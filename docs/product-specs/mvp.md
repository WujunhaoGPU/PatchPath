# MVP Product Spec

## Goal

Help a developer move from “I found a real GitHub issue” to “I understand the project, the issue, the likely code area, the validation path, and what engineering ability this contribution trains.”

## Users

- Developers learning through real open source contribution.
- Contributors who need automatic help understanding unfamiliar repositories and issues.
- People who want coaching that explains the analysis path, not just generated code or a final answer.

## Problem

New contributors often fail before writing code:

- They cannot quickly understand the repository structure, runtime entry points, or test habits.
- They pick issues that are unclear, stale, or too large.
- They cannot identify the relevant files.
- They do not know how to reproduce or validate the issue.
- They cannot explain a proposed change in a way maintainers trust.
- They complete a task without understanding what engineering judgment was trained.

## Scope

The MVP produces a guided contribution training session from a repo and issue.

The session combines:

- automatic analysis: project structure, issue breakdown, related files, evidence, likely change area, validation hints, and trace.
- coach guidance: why these files matter, how to read them, how to reason about impact, how to interpret tests, and how to communicate with maintainers.

Required sections:

- project summary and structure map
- issue summary and breakdown
- clarity assessment
- contribution suitability
- related files with evidence
- reading order with coaching rationale
- likely change area
- likely impact and risks
- validation command or missing validation information
- test result interpretation guidance
- maintainer communication draft
- engineering ability takeaways
- trace

## Non-Goals

- Default automatic patch generation.
- Automatic PR creation.
- Full IDE integration.
- Complex multi-agent runtime.
- Vector database requirement before text retrieval proves insufficient.

## Core User Path

1. User provides repo and issue.
2. Tool fetches issue context.
3. Tool inspects repository structure and files.
4. Tool returns an evidence-backed analysis plus coach guidance.
5. User decides whether to read, reproduce, ask a clarifying question, attempt a small change, or skip the issue.
6. User keeps the session as a learning record for what engineering ability was practiced.

## Acceptance Criteria

- For 5 real issues, the session identifies at least one useful related file or explains why code location is uncertain.
- Output includes trace and evidence, not only a summary.
- The tool can mark issues as not worth attempting when context is missing or scope is too large.
- A human can use the session as a starting point for reading code, planning validation, and writing a maintainer comment.
- The output includes at least one coach-style explanation of why the suggested reading or validation path matters.

## Related Plans

- `docs/exec-plans/active/day-01-bootstrap.md`
