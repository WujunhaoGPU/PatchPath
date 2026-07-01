# Architecture

## System In One Sentence

Given a GitHub repo and issue, produce an evidence-backed contribution brief for a human contributor.

## Planned Layers

- `ingestion`: fetch issue, comments, repo metadata, and local repository files.
- `retrieval`: find candidate files and snippets with `rg + heuristics`, then optionally boost with CodeGraph symbol evidence.
- `evidence`: store snippets, file paths, ranking reasons, and trace entries.
- `analysis`: summarize issue state, missing information, risks, and contribution path.
- `guard`: reject or warn on unsupported recommendations.
- `evaluation`: compare output against gold files and human-reviewed expectations.
- `presentation`: CLI output first; UI later only after the workflow proves useful.

## Agent Runtime

PatchPath uses an evidence-first workflow agent:

```text
Plan -> Retrieve -> Inspect -> Brief -> Guard
```

This is a fixed workflow, not a multi-agent crew. LLM calls are limited to problem framing, search planning, contribution brief writing, and optional guard review. File evidence must come from deterministic tools such as `rg`, filesystem reads, `git`, GitHub metadata, package metadata, and optional CodeGraph queries.

## Dependency Direction

```text
presentation -> analysis -> evidence -> retrieval -> ingestion
analysis -> guard
analysis -> evaluation
```

`analysis` may use LLMs, but must keep cited evidence and trace.

## Initial Data Flow

```text
repo + issue
-> fetch issue metadata
-> frame the problem
-> plan search
-> retrieve and inspect candidate files
-> rank evidence
-> build contribution brief
-> guard unsupported claims
-> record trace and brief
```

## Current Architecture Status

Status: runtime architecture accepted and M1 CLI implemented. V1 Tool Execution state is `rg + heuristics` as the default path, with `rg + CodeGraph` as an optional enhancement when a local CodeGraph index is available.

## First Validation

The smallest CLI runs real issues through `Plan -> Retrieve -> Inspect -> Brief -> Guard` and writes `brief.md` plus `trace.jsonl`. Current M1 validation on `pallets/click` puts 5/5 gold source files in Top-5.

Related design: `docs/design-docs/agent-runtime-choice.md`.
