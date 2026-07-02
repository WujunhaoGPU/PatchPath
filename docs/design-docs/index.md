# Design Docs Index

| Document | Status | Verification | Notes |
| --- | --- | --- | --- |
| `agent-runtime-choice.md` | accepted | docs-verified | Use `Plan -> Retrieve -> Inspect -> Brief -> Guard`; no multi-agent crew for MVP. |
| `tool-execution-retrieval-experiment.md` | accepted, then promoted | ran on `pallets/click` gold set | V1 now uses `rg + CodeGraph + heuristics` by default, with fallback to `rg + heuristics` if CodeGraph is unavailable. |
| `retrieval-strategy.md` | not started | unverified | Start with simple text retrieval before vector search. |
| `eval-design.md` | not started | unverified | Define gold files, suitability labels, and trace quality. |
