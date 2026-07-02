# Architecture

## System In One Sentence

Given a GitHub repo and issue, automatically analyze the project and issue, then produce an evidence-backed coaching session that helps a developer understand, reason, validate, and communicate.

## Planned Layers

- `ingestion`: fetch issue, comments, repo metadata, and local repository files.
- `retrieval`: find candidate files and snippets with `rg`, boost symbol-like evidence with CodeGraph by default, then rank with heuristics.
- `evidence`: store snippets, file paths, ranking reasons, and trace entries.
- `analysis`: summarize issue state, missing information, likely code areas, risks, validation path, and contribution path.
- `coaching`: explain why the suggested reading path, change direction, validation, and communication steps matter.
- `guard`: reject or warn on unsupported recommendations.
- `evaluation`: compare output against gold files and human-reviewed expectations.
- `presentation`: CLI output first; UI later only after the workflow proves useful.

## Agent Runtime

PatchPath uses an evidence-first coaching workflow:

```text
Plan -> Retrieve -> Inspect -> Coach -> Guard
```

This is a fixed workflow, not a multi-agent crew. LLM calls are limited to problem framing, search planning, coach-facing explanation, and optional guard review. File evidence must come from deterministic tools such as `rg`, CodeGraph, filesystem reads, `git`, GitHub metadata, and package metadata.

## Dependency Direction

```text
presentation -> analysis -> evidence -> retrieval -> ingestion
analysis -> coaching
analysis -> guard
analysis -> evaluation
```

`analysis` may use LLMs, but must keep cited evidence and trace.

## Initial Data Flow

```text
repo + issue
-> fetch issue metadata
-> plan search
-> retrieve text evidence with rg
-> retrieve structure evidence with CodeGraph
-> rank evidence
-> frame analysis and coach guidance with DeepSeek
-> guard unsupported claims
-> record trace and guided session brief
```

## Current Architecture Status

Status: runtime architecture accepted and M1 CLI implemented. V1 Tool Execution state is `rg + CodeGraph + heuristics` as the default path. CodeGraph initializes and queries the target repo by default, then falls back to `rg + heuristics` if CodeGraph is unavailable. DeepSeek is required for concise analysis and coach guidance through `DEEPSEEK_API_KEY`; missing or failing LLM calls fail the run instead of generating a template brief.

## First Validation

The smallest CLI runs real issues through `Plan -> Retrieve -> Inspect -> Coach -> Guard` and writes `brief.md` plus `trace.jsonl`. The file remains named `brief.md`, but its product role is a guided contribution training session. Current M1 validation on `pallets/click` puts 5/5 gold source files in Top-5.

Related design: `docs/design-docs/agent-runtime-choice.md`.
