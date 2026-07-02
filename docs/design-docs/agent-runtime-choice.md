# Agent Runtime Choice

Status: accepted
Last updated: 2026-07-01
Related spec: `docs/product-specs/mvp.md`

## Decision

PatchPath uses an evidence-first workflow agent:

```text
Plan -> Retrieve -> Inspect -> Coach -> Guard
```

This is a fixed workflow with LLM judgment at narrow points, not a multi-agent crew.

## Problem

PatchPath helps developers who cannot yet quickly understand a real open source project and issue. The product must generate a guided contribution training session that combines automatic analysis with coach-style explanation:

- project background
- project structure and entry-point hints
- issue one-line explanation and breakdown
- suitability: beginner / medium / not recommended
- related files Top-K
- reading order with rationale
- likely change points
- likely impact and risk
- validation command
- test-result interpretation guidance
- maintainer clarification question or comment draft
- engineering ability takeaways

The hard part is not producing text. The hard part is proving that the analysis and coaching came from issue and repository evidence instead of model guesswork.

## Chosen Architecture

```text
Issue Intake
-> Problem Framing
-> Search Planning
-> Tool Execution
-> Evidence Ranking
-> Guided Session Brief
-> Session Guard
```

## Runtime Nodes

### Issue Intake

Type: deterministic

Input:

- repo URL or local path
- issue URL or issue number

Output:

- issue title
- issue body
- labels
- comments
- repo metadata

Tools:

- GitHub API or `gh`
- `git`

### Problem Framing

Type: required LLM judgment

Input:

- issue title
- issue body
- comments
- labels

Output:

- one-line issue explanation
- issue type: bug / docs / test / feature / triage / unclear
- missing information
- initial suitability

Rule: this node cannot mention repository files unless they appear in the issue text or traced retrieval evidence. M1 uses DeepSeek for concise project summary, issue summary, clarity, and suitability. `DEEPSEEK_API_KEY` must be provided through `.env` or the environment.

### Search Planning

Type: LLM judgment

Input:

- framed issue
- repo tree summary

Output:

- search keywords
- likely directories
- likely file types
- test/doc/config search hints

Rule: this node produces a search plan, not conclusions.

### Tool Execution

Type: deterministic

Input:

- search plan
- repo checkout

Output:

- `rg` matches
- default CodeGraph symbol results
- heuristic ranking signals
- candidate files
- candidate snippets
- detected test commands
- trace entries

Tools:

- `rg`
- CodeGraph CLI
- filesystem reads
- `git`
- package metadata inspection

Rule: this is the only node that claims file evidence.

V1 state:

- Default path: `rg + CodeGraph + heuristics`.
- Fallback: if CodeGraph is missing, stale, unsupported, or returns no useful result, continue with `rg + heuristics` and record the fallback reason in trace.
- Evidence rule: CodeGraph can boost or expand candidate files, but every Top-K recommendation still needs traceable evidence.

### Evidence Ranking

Type: deterministic first, optional LLM tie-break

Input:

- candidate files
- candidate snippets
- issue keywords

Output:

- related files Top-K
- evidence items
- why each file is relevant

Rule: every recommended file must cite a match, path signal, import signal, test name, or issue mention.

### Guided Session Brief

Type: required LLM writing over evidence

Input:

- framed issue
- ranked evidence
- detected validation commands

Output:

- project background
- project structure and entry-point hints
- issue explanation
- suitability
- related files Top-K
- reading order with coaching rationale
- likely change points
- likely impact and risks
- validation command
- test-result interpretation guidance
- maintainer comment draft
- engineering ability takeaways

Rule: recommendations must be grounded in evidence. Unknowns should stay unknown.

M1 implementation note: DeepSeek framing is narrow and required. It writes the
plain-language intro fields, reading order, likely change points, and coaching
rationale from retrieved Top-K evidence. Top-K files, validation commands, and
trace still come from deterministic retrieval and ranking.

### Session Guard

Type: deterministic checks plus small LLM review if needed

Input:

- guided session brief
- evidence list
- trace

Output:

- accepted session, or session with warnings

Checks:

- no recommended file without evidence
- suitability can be `not recommended`
- missing reproduction steps are called out
- speculative fix text is marked as speculative
- output includes trace

## State Shape

The first implementation should keep state as plain JSON:

```text
RunState
  repo
  issue
  issue_context
  problem_frame
  search_plan
  tool_results
  evidence
  guided_session_brief
  guard_result
  trace
```

No database is required for the first local CLI. Write trace as JSONL.

## Trace Contract

Every run should record:

- node name
- input summary
- tool command or model call
- output summary
- evidence paths
- warnings
- provider: `rg`, `heuristics`, or `codegraph`
- fallback reason when a provider such as CodeGraph is unavailable

Trace file:

```text
.patchpath/runs/<run-id>/trace.jsonl
```

Brief file:

```text
.patchpath/runs/<run-id>/brief.md
```

The filename stays `brief.md` for the first CLI, but the product meaning is a
guided contribution training session.

## Why Not Multi-Agent Crew

Multi-agent crew architecture adds coordination cost before PatchPath has proven the core loop. For this product, reliability comes from evidence and trace, not from agents debating each other.

Avoid for MVP:

- Manager Agent
- Coder Agent
- Reviewer Agent
- autonomous PR loop
- unconstrained tool-use loop

## Why Not LangGraph Or AutoGen First

They may become useful later, but the MVP workflow is still linear. A few Python functions are easier to inspect, test, and replace.

Adopt a framework only when at least one of these becomes true:

- runs need pause/resume
- there are real branching paths
- retries and recovery become hard to read
- multiple tools or models need durable orchestration
- JSONL trace is no longer enough to debug

## First Vertical Slice

Command:

```bash
patchpath analyze --repo ../Scrapling --issue <issue-url>
```

Acceptance:

- creates `brief.md`
- creates `trace.jsonl`
- brief includes automatic analysis and coach guidance sections
- every Top-K file has evidence
- retrieval uses `rg + CodeGraph + heuristics`, with a recorded fallback when CodeGraph is unavailable
- user can decide one next action after reading the brief

## Re-evaluation Conditions

Revisit this design when:

- five real issues produce useful guided sessions but the workflow needs branching
- tool execution needs long-running state
- users need a web UI with saved runs
- automatic patch generation becomes a product goal
