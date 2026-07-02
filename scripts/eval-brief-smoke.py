#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from patchpath.cli import analyze, load_env_file  # noqa: E402


CASES: list[dict[str, Any]] = [
    {
        "repo": "click",
        "issue": "pallets/click#3502",
        "gold": ["src/click/shell_completion.py", "tests/test_shell_completion.py"],
        "expect_not_suitable": True,
    },
    {
        "repo": "fastify",
        "issue": "fastify/fastify#6124",
        "gold": [
            "docs/Reference/Errors.md",
            "docs/Reference/Routes.md",
            "lib/errors.js",
            "lib/route.js",
            "test/internals/errors.test.js",
            "test/logger/options.test.js",
            "types/errors.d.ts",
        ],
        "expect_not_suitable": True,
    },
    {
        "repo": "flask",
        "issue": "pallets/flask#5825",
        "gold": ["docs/patterns/javascript.rst"],
        "expect_not_suitable": True,
    },
    {
        "repo": "pytest",
        "issue": "pytest-dev/pytest#14442",
        "gold": [
            "src/_pytest/config/__init__.py",
            "testing/test_config.py",
            "testing/test_mark.py",
        ],
        "expect_not_suitable": True,
    },
    {
        "repo": "pytest",
        "issue": "pytest-dev/pytest#14603",
        "gold": [],
        "expect_not_suitable": True,
        "expect_no_change_points": True,
    },
]

REQUIRED_TRACE_NODES = {
    "issue_intake",
    "tool_execution:rg",
    "tool_execution:codegraph",
    "llm_frame",
    "evidence_ranking",
}


def main() -> int:
    load_env_file()
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--repo", action="append", default=[], help="name=/path/to/repo")
    parser.add_argument("--output-root", type=Path, default=Path.cwd() / ".patchpath" / "eval-smoke")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    repos = parse_repo_args(args.repo)
    results = []
    for case in CASES:
        repo_path = repos.get(case["repo"])
        if repo_path is None and args.repo_root:
            repo_path = args.repo_root / case["repo"]
        if repo_path is None:
            results.append({**case, "error": f"missing repo path for {case['repo']}"})
            continue
        try:
            run = analyze(
                repo=repo_path,
                issue=case["issue"],
                output_root=args.output_root,
                offline=args.offline,
            )
            results.append(evaluate_run(case, Path(run["run_dir"])))
        except Exception as exc:
            results.append({**case, "error": str(exc)})

    report = {"status": status_for(results), "cases": results, "summary": summarize(results)}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


def parse_repo_args(values: list[str]) -> dict[str, Path]:
    repos = {}
    for value in values:
        name, sep, path = value.partition("=")
        if not sep:
            raise SystemExit(f"--repo must be name=/path, got: {value}")
        repos[name] = Path(path)
    return repos


def evaluate_run(case: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    brief = (run_dir / "brief.md").read_text(encoding="utf-8")
    trace = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    top = extract_top_paths(brief)
    gold = sorted(case.get("gold", []))
    hit = bool(set(gold) & set(top)) if gold else None
    result = {
        "issue": case["issue"],
        "repo": case.get("repo"),
        "brief_path": str(run_dir / "brief.md"),
        "trace_path": str(run_dir / "trace.jsonl"),
        "top_paths": top,
        "hit_at_5": hit,
        "gold_missing": sorted(set(gold) - set(top)),
        "refs_outside_top": sorted(extract_path_refs(brief) - set(top)),
        "closed_not_suitable": suitability_ok(brief) if case.get("expect_not_suitable") else None,
        "has_trace_nodes": trace_nodes_ok(trace),
        "missing_trace_nodes": sorted(REQUIRED_TRACE_NODES - trace_node_keys(trace)),
        "negative_change_points_ok": negative_change_points_ok(brief)
        if case.get("expect_no_change_points")
        else None,
    }
    result["hit@5"] = result["hit_at_5"]
    return result


def extract_top_paths(brief: str) -> list[str]:
    return re.findall(r"^- `([^`]+)`", section(brief, "相关文件 Top-K"), re.M)[:5]


def extract_path_refs(brief: str) -> set[str]:
    text = "\n".join(
        [
            section(brief, "推荐阅读顺序"),
            section(brief, "可能修改点"),
            section(brief, "澄清/复盘点"),
        ]
    )
    return {
        match.strip("`.,;:，。；：)）")
        for match in re.findall(
            r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9_+-]+",
            text,
        )
    }


def section(brief: str, name: str) -> str:
    match = re.search(rf"^## {re.escape(name)}\n(.*?)(?=\n## |\Z)", brief, re.S | re.M)
    return match.group(1).strip() if match else ""


def suitability_ok(brief: str) -> bool:
    text = section(brief, "是否适合尝试").lower()
    return any(term in text for term in ("not recommended", "不适合", "已关闭", "needs information"))


def negative_change_points_ok(brief: str) -> bool:
    return "## 可能修改点" not in brief and "## 澄清/复盘点" in brief


def trace_node_keys(trace: list[dict[str, Any]]) -> set[str]:
    keys = set()
    for entry in trace:
        node = entry.get("node")
        provider = entry.get("provider")
        keys.add(node)
        if node == "tool_execution" and provider in {"rg", "codegraph"}:
            keys.add(f"{node}:{provider}")
    return keys


def trace_nodes_ok(trace: list[dict[str, Any]]) -> bool:
    return not (REQUIRED_TRACE_NODES - trace_node_keys(trace))


def status_for(results: list[dict[str, Any]]) -> str:
    for result in results:
        if result.get("error"):
            return "fail"
        if result.get("hit_at_5") is False:
            return "fail"
        if result.get("refs_outside_top"):
            return "fail"
        if result.get("closed_not_suitable") is False:
            return "fail"
        if result.get("has_trace_nodes") is False:
            return "fail"
        if result.get("negative_change_points_ok") is False:
            return "fail"
    return "pass"


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cases": len(results),
        "hit_at_5": sum(1 for item in results if item.get("hit_at_5") is True),
        "errors": sum(1 for item in results if item.get("error")),
    }


if __name__ == "__main__":
    raise SystemExit(main())
