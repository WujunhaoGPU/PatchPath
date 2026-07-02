from __future__ import annotations

import argparse
import json
import os
import re
import sys
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TEXT_FRAME_FIELDS = (
    "project_summary",
    "issue_summary",
    "issue_breakdown",
    "clarity",
    "suitability",
    "maintainer_draft",
)
LIST_FRAME_FIELDS = (
    "structure_map",
    "reading_order",
    "change_points",
    "impact_risks",
    "validation_plan",
    "test_result_interpretation",
    "ability_takeaways",
)
GROUNDED_FRAME_FIELDS = (
    "reading_order",
    "change_points",
    "impact_risks",
    "validation_plan",
    "test_result_interpretation",
    "maintainer_draft",
)


EVAL_FIXTURES: dict[str, dict[str, Any]] = {
    "pallets/click#3502": {
        "title": "fish completion is broken in 8.4.1",
        "state": "closed",
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
        "state": "closed",
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
        "state": "closed",
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
        "state": "closed",
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
        "state": "closed",
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
    llm_client: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    codegraph_runner: Callable[[Path, list[str]], list[dict[str, Any]]] | None = None,
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
    apply_codegraph_terms(repo_path, terms, matches, trace, codegraph_runner)
    related_files = rank_files(matches)
    run_dir = make_run_dir(output_root, issue_key)
    brief_frame = build_brief_frame(
        repo_path=repo_path,
        issue_context=issue_context,
        related_files=related_files,
        trace=trace,
        llm_client=llm_client,
    )

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
        brief_frame=brief_frame,
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


def build_brief_frame(
    repo_path: Path,
    issue_context: dict[str, Any],
    related_files: list[dict[str, Any]],
    trace: list[dict[str, Any]],
    llm_client: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fallback = template_brief_frame(repo_path, issue_context, related_files)
    project_structure = build_project_structure(repo_path)
    payload = {
        "project_summary": fallback["project_summary"],
        "project_structure": project_structure,
        "issue_title": issue_context["title"],
        "issue_state": issue_context.get("state", "unknown"),
        "issue_body": issue_context.get("body", "")[:4000],
        "labels": issue_context.get("labels", []),
        "comments": issue_context.get("comments", [])[:3],
        "related_files": [
            {"path": item["path"], "terms": item["terms"], "evidence": item["evidence"][:3]}
            for item in related_files[:5]
        ],
    }

    if llm_client:
        try:
            frame = normalize_brief_frame(llm_client(payload))
            validate_brief_frame_grounding(frame, related_files)
            trace_llm_frame(trace, "llm", payload, frame, None, [])
            return frame
        except Exception as exc:  # pragma: no cover - defensive error path
            trace_llm_frame(trace, "llm", payload, fallback, "llm_client_error", [str(exc)])
            raise RuntimeError(f"LLM framing failed: {exc}") from exc

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        trace_llm_frame(trace, "template", payload, fallback, "missing_deepseek_api_key", [])
        raise RuntimeError(
            "DEEPSEEK_API_KEY is required. Put it in .env or export it before running patchpath."
        )

    model = os.environ.get("PATCHPATH_LLM_MODEL", "deepseek-v4-flash")
    try:
        frame = normalize_brief_frame(call_deepseek_frame(api_key, model, payload))
        validate_brief_frame_grounding(frame, related_files)
        trace_llm_frame(trace, "deepseek", payload, frame, None, [])
        return frame
    except Exception as exc:
        trace_llm_frame(trace, "deepseek", payload, fallback, "deepseek_error", [str(exc)])
        raise RuntimeError(f"DeepSeek framing failed: {exc}") from exc


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def template_brief_frame(
    repo_path: Path,
    issue_context: dict[str, Any],
    related_files: list[dict[str, Any]],
) -> dict[str, Any]:
    clarity = "基本清楚，但仍需要人工确认复现环境和预期行为。"
    if not issue_context.get("body"):
        clarity = "信息不足：当前上下文缺少 issue 正文或复现细节，需要人工确认。"

    suitability = "medium：已有代码证据，可作为阅读和小补丁候选。"
    if issue_context.get("state") == "closed":
        suitability = "not recommended：issue 已关闭，更适合作为练习或回归样本，不适合作为当前贡献。"
    if not related_files:
        suitability = "not recommended：没有找到可引用的相关文件证据。"

    return {
        "project_summary": read_project_summary(repo_path),
        "issue_summary": issue_context["title"],
        "issue_breakdown": "先确认 issue 现象、预期行为、复现条件和已有证据，再决定是否值得继续。",
        "clarity": clarity,
        "suitability": suitability,
        "maintainer_draft": (
            "我会先按当前 evidence 阅读相关文件并验证复现路径；如果缺少版本、环境或预期行为，"
            "会先向 maintainer 补问这些信息。"
        ),
        "structure_map": build_project_structure(repo_path),
        "reading_order": [item["path"] for item in related_files[:5]],
        "change_points": [
            f"{item['path']}: {item['evidence'][0]['term']}" for item in related_files[:5]
        ],
        "impact_risks": [
            "修改前先检查 Top-K 文件的调用关系、相邻测试和兼容性边界。"
        ],
        "validation_plan": [
            issue_context.get("validation")
            or "先运行相关测试；如果没有明确测试，先阅读项目测试说明并补最小复现。"
        ],
        "test_result_interpretation": [
            "测试通过只说明当前断言覆盖的行为没有坏；测试失败要回到 evidence 判断是定位错、复现错还是边界没覆盖。"
        ],
        "ability_takeaways": [
            "训练陌生项目阅读、issue 拆解、证据定位、影响分析、验证设计和维护者沟通。"
        ],
    }


def normalize_brief_frame(frame: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in TEXT_FRAME_FIELDS if not str(frame.get(key, "")).strip()]
    missing.extend(
        key
        for key in LIST_FRAME_FIELDS
        if key not in frame or not normalize_text_list(frame[key], key)
    )
    if missing:
        raise ValueError(f"LLM frame missing fields: {', '.join(missing)}")

    normalized: dict[str, Any] = {}
    for key in TEXT_FRAME_FIELDS:
        value = str(frame.get(key, "")).strip()
        normalized[key] = compact_text(value)
    for key in LIST_FRAME_FIELDS:
        normalized[key] = normalize_text_list(frame[key], key)
    return normalized


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_text_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"LLM frame field must be a list: {key}")
    items = [compact_text(str(item)) for item in value if compact_text(str(item))]
    if not items:
        raise ValueError(f"LLM frame missing fields: {key}")
    return items


def validate_brief_frame_grounding(
    frame: dict[str, Any],
    related_files: list[dict[str, Any]],
) -> None:
    top = related_files[:5]
    allowed_paths = {item["path"] for item in top}
    allowed_evidence_ids = {
        evidence["id"] for item in top for evidence in item["evidence"][:3]
    }
    generated_parts: list[str] = []
    for key in GROUNDED_FRAME_FIELDS:
        value = frame[key]
        if isinstance(value, list):
            generated_parts.extend(value)
        else:
            generated_parts.append(str(value))
    generated_text = "\n".join(generated_parts)
    referenced_paths = extract_path_references(generated_text)
    unknown_paths = sorted(referenced_paths - allowed_paths)
    if unknown_paths:
        raise ValueError(
            "LLM frame references files outside Top-K: " + ", ".join(unknown_paths)
        )

    referenced_evidence_ids = set(re.findall(r"\bE\d+\b", generated_text))
    unknown_evidence_ids = sorted(referenced_evidence_ids - allowed_evidence_ids)
    if unknown_evidence_ids:
        raise ValueError(
            "LLM frame references unknown evidence ids: "
            + ", ".join(unknown_evidence_ids)
        )


def extract_path_references(text: str) -> set[str]:
    candidates = set(
        re.findall(
            r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9_+-]+",
            text,
        )
    )
    return {normalize_repo_path(path.strip("`'\"，,。；;:：）)")) for path in candidates}


def call_deepseek_frame(
    api_key: str,
    model: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "请基于真实 issue、项目结构和文件证据，生成一份 guided contribution training session。"
        "要求：通俗易懂，不冗余；用教练口吻解释为什么这么读、怎么判断、怎么验证；"
        "不要编造文件、复现步骤或修复方案；"
        "如果 issue_state 是 closed，要说明它不适合作为当前贡献，只适合学习、复盘或回归验证；"
        "凡是推荐阅读、修改、风险、验证和沟通中出现的代码文件，只能来自 related_files；"
        "如需引用证据，只能使用 related_files 中已有 evidence id。"
        "text 字段最多两句话，list 字段各输出 2-5 条。"
        "只输出 JSON，text 字段为 project_summary, issue_summary, issue_breakdown, "
        "clarity, suitability, maintainer_draft；list 字段为 structure_map, reading_order, "
        "change_points, impact_risks, validation_plan, test_result_interpretation, "
        "ability_takeaways。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write concise Chinese guided contribution training sessions "
                        "grounded in repository and issue evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def trace_llm_frame(
    trace: list[dict[str, Any]],
    provider: str,
    payload: dict[str, Any],
    frame: dict[str, Any],
    fallback_reason: str | None,
    warnings: list[str],
) -> None:
    trace.append(
        {
            "node": "llm_frame",
            "provider": provider,
            "query": payload["issue_title"],
            "command": None,
            "result_count": 1,
            "selected_paths": [item["path"] for item in payload["related_files"]],
            "evidence_ids": [
                evidence["id"]
                for item in payload["related_files"]
                for evidence in item["evidence"]
            ],
            "frame_keys": sorted(frame),
            "fallback_reason": fallback_reason,
            "warnings": warnings,
            "duration_ms": 0,
            "exit_code": 0,
        }
    )


def apply_codegraph_terms(
    repo_path: Path,
    terms: list[str],
    files: dict[str, dict[str, Any]],
    trace: list[dict[str, Any]],
    runner: Callable[[Path, list[str]], list[dict[str, Any]]] | None = None,
) -> None:
    command = "codegraph status -j <repo>; codegraph query -p <repo> -j -l 5 <term>"
    fallback_reason = None
    warnings: list[str] = []
    try:
        signals = runner(repo_path, terms) if runner else query_codegraph(repo_path, terms)
    except Exception as exc:
        signals = []
        fallback_reason = "codegraph_unavailable"
        warnings.append(str(exc))

    next_id = next_evidence_id(files)
    for signal in signals:
        path = normalize_repo_path(str(signal.get("path", "")))
        if not path:
            continue
        symbol = str(signal.get("symbol") or signal.get("name") or signal.get("term") or "symbol")
        item = files.setdefault(
            path,
            {"path": path, "score": 0.0, "match_count": 0, "terms": set(), "evidence": []},
        )
        item["codegraph_match_count"] = item.get("codegraph_match_count", 0) + 1
        item["terms"].add(str(signal.get("term") or symbol))
        if len(item["evidence"]) < 5:
            item["evidence"].append(
                {
                    "id": f"E{next_id}",
                    "term": f"codegraph:{symbol}",
                    "line": int(signal.get("line") or 0),
                    "text": f"CodeGraph {signal.get('kind', 'symbol')} {symbol}",
                }
            )
            next_id += 1

    trace.append(
        {
            "node": "tool_execution",
            "provider": "codegraph",
            "query": codegraph_terms(terms),
            "command": command,
            "result_count": len(signals),
            "selected_paths": sorted({normalize_repo_path(str(signal.get("path", ""))) for signal in signals if signal.get("path")}),
            "evidence_ids": [],
            "fallback_reason": fallback_reason,
            "warnings": warnings,
            "duration_ms": 0,
            "exit_code": 0 if fallback_reason is None else 1,
        }
    )


def query_codegraph(repo_path: Path, terms: list[str]) -> list[dict[str, Any]]:
    status = subprocess.run(
        ["codegraph", "status", "-j", str(repo_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "codegraph status failed")
    data = json.loads(status.stdout or "{}")
    if not data.get("initialized"):
        init = subprocess.run(
            ["codegraph", "init", str(repo_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if init.returncode != 0:
            raise RuntimeError(init.stderr.strip() or "codegraph init failed")

    signals: list[dict[str, Any]] = []
    for term in codegraph_terms(terms):
        query = subprocess.run(
            ["codegraph", "query", "-p", str(repo_path), "-j", "-l", "5", term],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if query.returncode != 0:
            continue
        for result in json.loads(query.stdout or "[]"):
            node = result.get("node", {})
            path = node.get("filePath")
            if not path:
                continue
            signals.append(
                {
                    "path": path,
                    "symbol": node.get("name"),
                    "kind": node.get("kind"),
                    "line": node.get("startLine"),
                    "term": term,
                }
            )
    return signals


def codegraph_terms(terms: list[str]) -> list[str]:
    selected = []
    for term in terms:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", term):
            continue
        if "_" in term or "." in term or any(ch.isupper() for ch in term):
            selected.append(term)
    return selected[:10]


def normalize_repo_path(path: str) -> str:
    path = path[2:] if path.startswith("./") else path
    return path.strip()


def next_evidence_id(files: dict[str, dict[str, Any]]) -> int:
    current = 0
    for item in files.values():
        for evidence in item["evidence"]:
            match = re.fullmatch(r"E(\d+)", evidence["id"])
            if match:
                current = max(current, int(match.group(1)))
    return current + 1


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
    state = ((fetched or {}).get("state") or fixture.get("state") or "unknown").lower()
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
        "state": state,
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
        score += item.get("codegraph_match_count", 0) * 50

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
    brief_frame: dict[str, Any],
    terms: list[str],
    warnings: list[str],
) -> str:
    top = related_files[:5]
    validation = issue_context.get("validation") or detect_validation(top)

    lines = [
        f"# PatchPath 开源贡献训练单: {issue_key}",
        "",
        "## 项目结构",
        brief_frame["project_summary"],
        "",
    ]
    for item in brief_frame["structure_map"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## issue 拆解",
        ]
    )
    lines.extend(
        [
            brief_frame["issue_summary"],
            "",
            brief_frame["issue_breakdown"],
            "",
            "## issue 是否清楚，缺哪些信息",
            brief_frame["clarity"],
            "",
            "## 是否适合尝试",
            brief_frame["suitability"],
            "",
            "## 相关文件 Top-K",
        ]
    )
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
            "## 推荐阅读顺序和理由",
        ]
    )
    if top:
        for index, item in enumerate(brief_frame["reading_order"], start=1):
            lines.append(f"{index}. {item}")
    else:
        lines.append("1. 先回到 issue 补充复现信息，再重新检索。")

    lines.extend(
        [
            "",
            "## 可能修改点",
        ]
    )
    for item in brief_frame["change_points"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 修改影响和风险",
        ]
    )
    for item in brief_frame["impact_risks"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 验证计划",
        ]
    )
    if validation:
        lines.append(f"- 建议命令：`{validation}`")
    for item in brief_frame["validation_plan"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 测试结果怎么看",
        ]
    )
    for item in brief_frame["test_result_interpretation"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 固定风险提示",
            "- 当前 brief 只基于 issue 文本、本地文件、`rg` 和 CodeGraph 证据，不证明修复方案正确。",
            "- 如果本地仓库不是 issue 对应版本，文件定位可能被已合并修改影响。",
        ]
    )
    for warning in warnings + issue_context.get("warnings", []):
        lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## maintainer 沟通草稿",
            brief_frame["maintainer_draft"],
            "",
            "## 本次训练的工程能力",
        ]
    )
    for item in brief_frame["ability_takeaways"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## trace 摘要",
            f"- search terms: {', '.join(terms)}",
            f"- selected files: {', '.join(item['path'] for item in top) or 'none'}",
            "- trace file: `trace.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)


def build_project_structure(repo_path: Path) -> list[str]:
    known_files = {
        "pyproject.toml": "Python package configuration",
        "setup.py": "Python package setup",
        "setup.cfg": "Python package configuration",
        "requirements.txt": "Python dependencies",
        "package.json": "Node.js package configuration",
        "Cargo.toml": "Rust package configuration",
        "go.mod": "Go module configuration",
        "README.md": "project README",
        "README.rst": "project README",
    }
    known_dirs = {
        "src": "source code",
        "tests": "test suite",
        "test": "test suite",
        "docs": "documentation",
        "examples": "examples",
        "scripts": "repeatable scripts",
    }
    structure = [
        f"{name}: {description}"
        for name, description in known_files.items()
        if (repo_path / name).is_file()
    ]
    structure.extend(
        f"{name}/: {description}"
        for name, description in known_dirs.items()
        if (repo_path / name).is_dir()
    )
    if not structure:
        return [f"{repo_path.name}/: local repository root"]
    return structure


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
    load_env_file()
    parser = argparse.ArgumentParser(prog="patchpath")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--repo", required=True)
    analyze_parser.add_argument("--issue", required=True)
    analyze_parser.add_argument("--output-root")
    analyze_parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            result = analyze(
                repo=args.repo,
                issue=args.issue,
                output_root=args.output_root,
                offline=args.offline,
            )
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"brief: {result['brief_path']}")
        print(f"trace: {result['trace_path']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
