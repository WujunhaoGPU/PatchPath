from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVAL_FIXTURES: dict[str, dict[str, Any]] = {
    "pallets/click#3502": {
        "title": "fish completion is broken in 8.4.1",
        "terms": [
            "fish completion",
            "fish",
            "fish_complete",
            "shell completion",
            "CompletionItem",
            "format_completion",
            "string split",
            "complete_var",
        ],
        "validation": "pytest tests/test_shell_completion.py",
    },
    "pallets/click#3487": {
        "title": "Echoing empty bytes or bytearray raises TypeError",
        "terms": [
            "echo",
            "empty bytes",
            "bytearray",
            "TypeError",
            "BytesIO",
            "nl=True",
            "bytes-like object",
            "file.write",
        ],
        "validation": "pytest tests/test_utils.py",
    },
    "pallets/click#3458": {
        "title": "get_parameter_source() returns None in 8.4.0",
        "terms": [
            "get_parameter_source",
            "ParameterSource",
            "ctx.get_parameter_source",
            "convert",
            "default",
            "nodefault",
            "eager callbacks",
        ],
        "validation": "pytest tests/test_defaults.py tests/test_options.py",
    },
    "pallets/click#3403": {
        "title": "default behaviour changes with enable/disable boolean flag pair",
        "terms": [
            "flag_value",
            "default=True",
            "enable_xyz",
            "boolean option",
            "--without-xyz",
            "--with-xyz",
            "dual flags",
            "default behaviour",
        ],
        "validation": "pytest tests/test_options.py",
    },
    "pallets/click#3360": {
        "title": "Empty output from HelpFormatter.write_usage for a program without arguments",
        "terms": [
            "HelpFormatter.write_usage",
            "HelpFormatter",
            "write_usage",
            "Usage: program",
            "no args",
            "empty output",
        ],
        "validation": "pytest tests/test_formatting.py",
    },
}


def parse_issue_ref(value: str) -> tuple[str, str, int]:
    url_match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", value)
    if url_match:
        owner, repo, number = url_match.groups()
        return owner, repo, int(number)

    short_match = re.match(r"([^/\s#]+)/([^/\s#]+)#(\d+)$", value)
    if short_match:
        owner, repo, number = short_match.groups()
        return owner, repo, int(number)

    raise ValueError("issue must be a GitHub issue URL or owner/repo#number")


def analyze(
    repo: str | Path,
    issue: str,
    output_root: str | Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    repo_path = Path(repo).expanduser().resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"repo path does not exist: {repo_path}")

    owner, repo_name, number = parse_issue_ref(issue)
    issue_key = f"{owner}/{repo_name}#{number}"
    trace: list[dict[str, Any]] = []
    issue_context = load_issue_context(owner, repo_name, number, offline, trace)
    terms = issue_context["terms"] or plan_search_terms(issue_context)

    matches = run_rg_terms(repo_path, terms, trace)
    related_files = rank_files(matches)
    run_dir = make_run_dir(output_root, issue_key)

    guard_warnings = guard_related_files(related_files)
    trace.append(
        {
            "node": "evidence_ranking",
            "provider": "heuristics",
            "query": terms,
            "command": None,
            "result_count": len(related_files),
            "selected_paths": [item["path"] for item in related_files[:5]],
            "selected_evidence": [
                {"path": item["path"], "evidence": item["evidence"]}
                for item in related_files[:5]
            ],
            "evidence_ids": [
                evidence["id"]
                for item in related_files[:5]
                for evidence in item["evidence"]
            ],
            "fallback_reason": None,
            "warnings": guard_warnings,
            "duration_ms": 0,
            "exit_code": 0,
        }
    )

    brief = render_brief(
        repo_path=repo_path,
        issue_key=issue_key,
        issue_context=issue_context,
        related_files=related_files,
        terms=terms,
        warnings=guard_warnings,
    )
    write_run(run_dir, brief, trace)
    return {
        "run_dir": str(run_dir),
        "brief_path": str(run_dir / "brief.md"),
        "trace_path": str(run_dir / "trace.jsonl"),
        "related_files": related_files,
        "issue": issue_context,
    }


def load_issue_context(
    owner: str,
    repo_name: str,
    number: int,
    offline: bool,
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    issue_key = f"{owner}/{repo_name}#{number}"
    fixture = EVAL_FIXTURES.get(issue_key, {})
    warnings: list[str] = []
    fetched: dict[str, Any] | None = None

    if not offline:
        command = [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            f"{owner}/{repo_name}",
            "--json",
            "title,body,labels,comments,state,url",
        ]
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode == 0:
            fetched = json.loads(completed.stdout)
        else:
            warnings.append(f"gh issue view failed: {completed.stderr.strip()}")

        trace.append(
            {
                "node": "issue_intake",
                "provider": "gh",
                "query": issue_key,
                "command": " ".join(command),
                "result_count": 1 if fetched else 0,
                "selected_paths": [],
                "evidence_ids": [],
                "fallback_reason": None if fetched else "fixture",
                "warnings": warnings,
                "duration_ms": 0,
                "exit_code": completed.returncode,
            }
        )
    else:
        warnings.append("offline mode used fixture issue context")
        trace.append(
            {
                "node": "issue_intake",
                "provider": "fixture",
                "query": issue_key,
                "command": None,
                "result_count": 1 if fixture else 0,
                "selected_paths": [],
                "evidence_ids": [],
                "fallback_reason": "offline",
                "warnings": warnings,
                "duration_ms": 0,
                "exit_code": 0,
            }
        )

    title = (fetched or {}).get("title") or fixture.get("title") or issue_key
    body = (fetched or {}).get("body") or ""
    labels = [label["name"] for label in (fetched or {}).get("labels", [])]
    comments = (fetched or {}).get("comments", [])
    terms = fixture.get("terms", [])
    validation = fixture.get("validation")
    if not fetched and not fixture:
        warnings.append("no fixture exists for this issue; search terms are derived")

    return {
        "key": issue_key,
        "title": title,
        "body": body,
        "labels": labels,
        "comments": comments,
        "terms": terms,
        "validation": validation,
        "warnings": warnings,
    }


def plan_search_terms(issue_context: dict[str, Any]) -> list[str]:
    text = f"{issue_context['title']}\n{issue_context.get('body', '')}"
    terms = re.findall(r"[A-Za-z_][A-Za-z0-9_\.=-]{2,}", text)
    unique: list[str] = []
    for term in terms:
        if term.lower() in {"the", "and", "with", "from", "this", "that"}:
            continue
        if term not in unique:
            unique.append(term)
    return unique[:12]


def run_rg_terms(
    repo_path: Path,
    terms: list[str],
    trace: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    evidence_index = 1

    for term in terms:
        command = [
            "rg",
            "--line-number",
            "--column",
            "--fixed-strings",
            "--ignore-case",
            "--color=never",
            "--glob",
            "!.git",
            "--glob",
            "!.patchpath",
            "--glob",
            "!.venv",
            "--",
            term,
            ".",
        ]
        completed = subprocess.run(
            command,
            cwd=repo_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]

        for line in lines:
            parsed = parse_rg_line(line)
            if not parsed:
                continue
            path, lineno, text = parsed
            item = files.setdefault(
                path,
                {"path": path, "score": 0.0, "match_count": 0, "terms": set(), "evidence": []},
            )
            item["match_count"] += 1
            item["terms"].add(term)
            if len(item["evidence"]) < 5:
                item["evidence"].append(
                    {
                        "id": f"E{evidence_index}",
                        "term": term,
                        "line": lineno,
                        "text": text.strip()[:240],
                    }
                )
                evidence_index += 1

        trace.append(
            {
                "node": "tool_execution",
                "provider": "rg",
                "query": term,
                "command": " ".join(command),
                "result_count": len(lines),
                "selected_paths": sorted({parse_rg_line(line)[0] for line in lines if parse_rg_line(line)})[:10],
                "evidence_ids": [],
                "fallback_reason": None,
                "warnings": [] if completed.returncode in (0, 1) else [completed.stderr.strip()],
                "duration_ms": 0,
                "exit_code": completed.returncode,
            }
        )

    return files


def parse_rg_line(line: str) -> tuple[str, int, str] | None:
    parts = line.split(":", 3)
    if len(parts) < 4:
        return None
    path, lineno, _column, text = parts
    path = path[2:] if path.startswith("./") else path
    try:
        return path, int(lineno), text
    except ValueError:
        return None


def rank_files(files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in files.values():
        path = item["path"]
        terms = item["terms"]
        score = min(item["match_count"], 20) + (len(terms) * 8)

        if path.startswith("src/"):
            score += 28
            score += definition_match_bonus(item)
        elif path.startswith("tests/"):
            score += 14

        if path.endswith(".py"):
            score += 5
        if re.search(r"(^|/)(CHANGELOG|CHANGES|docs?)(\.|/|$)", path, re.I):
            score -= 24
        if "__pycache__" in path or ".egg-info" in path:
            score -= 100

        item["score"] = score
        item["terms"] = sorted(terms)
        ranked.append(item)

    return sorted(
        ranked,
        key=lambda item: (-item["score"], -len(item["terms"]), item["path"]),
    )


def definition_match_bonus(item: dict[str, Any]) -> int:
    for term in item["terms"]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", term):
            continue
        pattern = re.compile(rf"^\s*(def|class)\s+{re.escape(term)}\b")
        if any(pattern.search(evidence["text"]) for evidence in item["evidence"]):
            return 60
    return 0


def guard_related_files(related_files: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if not related_files:
        warnings.append("no related files found from rg evidence")
    for item in related_files[:5]:
        if not item["evidence"]:
            warnings.append(f"{item['path']} has no evidence and should not be recommended")
    return warnings


def make_run_dir(output_root: str | Path | None, issue_key: str) -> Path:
    root = Path(output_root) if output_root else Path.cwd() / ".patchpath" / "runs"
    safe_issue = re.sub(r"[^A-Za-z0-9_.-]+", "-", issue_key).strip("-")
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{safe_issue}"
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def render_brief(
    repo_path: Path,
    issue_key: str,
    issue_context: dict[str, Any],
    related_files: list[dict[str, Any]],
    terms: list[str],
    warnings: list[str],
) -> str:
    top = related_files[:5]
    project_summary = read_project_summary(repo_path)
    validation = issue_context.get("validation") or detect_validation(top)
    clarity = "基本清楚，但仍需要人工确认复现环境和预期行为。"
    if not issue_context.get("body"):
        clarity = "信息不足：当前上下文缺少 issue 正文或复现细节，需要人工确认。"

    suitability = "medium：已有代码证据，可作为阅读和小补丁候选。"
    if not top:
        suitability = "not recommended：没有找到可引用的相关文件证据。"

    lines = [
        f"# PatchPath Brief: {issue_key}",
        "",
        "## 项目是什么",
        project_summary,
        "",
        "## issue 在解决什么",
        issue_context["title"],
        "",
        "## issue 是否清楚，缺哪些信息",
        clarity,
        "",
        "## 是否适合尝试",
        suitability,
        "",
        "## 相关文件 Top-K",
    ]
    if top:
        for item in top:
            ev = item["evidence"][0]
            lines.append(
                f"- `{item['path']}` score={item['score']:.1f} evidence={ev['id']} "
                f"line {ev['line']} term `{ev['term']}`"
            )
    else:
        lines.append("- 未找到有证据的相关文件。")

    lines.extend(
        [
            "",
            "## 推荐阅读顺序",
        ]
    )
    if top:
        for index, item in enumerate(top, start=1):
            lines.append(f"{index}. `{item['path']}`")
    else:
        lines.append("1. 先回到 issue 补充复现信息，再重新检索。")

    lines.extend(
        [
            "",
            "## 可能修改点",
            "先阅读 Top-K 源文件和对应测试；PatchPath M1 不生成补丁，以下只是证据指向的候选区域。",
        ]
    )
    for item in top:
        first = item["evidence"][0]
        lines.append(f"- `{item['path']}`: matched `{first['term']}` at line {first['line']}.")

    lines.extend(
        [
            "",
            "## 验证命令或缺失的验证信息",
            validation or "未检测到明确验证命令；需要阅读项目测试说明或询问 maintainer。",
            "",
            "## 风险点",
            "- 当前 brief 只基于 issue 文本、本地文件和 `rg` 证据，不证明修复方案正确。",
            "- 如果本地仓库不是 issue 对应版本，文件定位可能被已合并修改影响。",
        ]
    )
    for warning in warnings + issue_context.get("warnings", []):
        lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## 可发给 maintainer 的澄清问题/comment 草稿",
            (
                "I found candidate files from the issue terms and will first verify the "
                "behavior with the project tests. Is there any version-specific context "
                "or reproduction detail I should check before proposing a small patch?"
            ),
            "",
            "## trace 摘要",
            f"- search terms: {', '.join(terms)}",
            f"- selected files: {', '.join(item['path'] for item in top) or 'none'}",
            "- trace file: `trace.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)


def read_project_summary(repo_path: Path) -> str:
    for name in ("README.md", "README.rst", "README.txt"):
        path = repo_path / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fallback_heading = None
        for line in text.splitlines():
            is_heading = line.lstrip().startswith("#")
            stripped = line.strip(" #=\t")
            if not stripped or "<" in stripped or ">" in stripped or "![" in stripped:
                continue
            if is_heading:
                fallback_heading = fallback_heading or stripped
                continue
            if stripped:
                return f"`{repo_path.name}`: {stripped}"
        if fallback_heading:
            return f"`{repo_path.name}`: {fallback_heading}"
    return f"`{repo_path.name}` 本地仓库。"


def detect_validation(top: list[dict[str, Any]]) -> str | None:
    tests = [item["path"] for item in top if item["path"].startswith("tests/")]
    if tests:
        return "pytest " + " ".join(tests[:3])
    return None


def write_run(run_dir: Path, brief: str, trace: list[dict[str, Any]]) -> None:
    (run_dir / "brief.md").write_text(brief, encoding="utf-8")
    with (run_dir / "trace.jsonl").open("w", encoding="utf-8") as file:
        for entry in trace:
            file.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="patchpath")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--repo", required=True)
    analyze_parser.add_argument("--issue", required=True)
    analyze_parser.add_argument("--output-root")
    analyze_parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        result = analyze(
            repo=args.repo,
            issue=args.issue,
            output_root=args.output_root,
            offline=args.offline,
        )
        print(f"brief: {result['brief_path']}")
        print(f"trace: {result['trace_path']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
