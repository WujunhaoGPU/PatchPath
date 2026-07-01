# Architecture

## System In One Sentence

Given a GitHub repo and issue, produce an evidence-backed contribution brief for a human contributor.

## Planned Layers

- `ingestion`: fetch issue, comments, repo metadata, and local repository files.
- `retrieval`: find candidate files and snippets with simple searchable methods first.
- `analysis`: summarize issue state, missing information, risks, and contribution path.
- `evaluation`: compare output against gold files and human-reviewed expectations.
- `presentation`: CLI output first; UI later only after the workflow proves useful.

## Dependency Direction

```text
presentation -> analysis -> retrieval -> ingestion
analysis -> evaluation
```

`analysis` may use LLMs, but must keep cited evidence and trace.

## Initial Data Flow

```text
repo + issue
-> fetch issue metadata
-> inspect local checkout
-> retrieve candidate files
-> build contribution brief
-> record trace
-> compare with eval set
```

## Current Architecture Status

Status: design draft. No product code yet.

## First Validation

Create 5 manually labeled issue samples, then build the smallest CLI that produces the same brief format for one sample.
