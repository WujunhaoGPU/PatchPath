#!/usr/bin/env bash
set -euo pipefail

repo="${PATCHPATH_EVAL_REPO:-../click}"

if [ ! -d "$repo" ]; then
  echo "missing eval repo: $repo" >&2
  echo "set PATCHPATH_EVAL_REPO=/path/to/click" >&2
  exit 1
fi

uv run python - "$repo" <<'PY'
import sys
from pathlib import Path

from patchpath.cli import analyze

repo = Path(sys.argv[1]).resolve()
cases = [
    ("pallets/click#3502", "src/click/shell_completion.py"),
    ("pallets/click#3487", "src/click/utils.py"),
    ("pallets/click#3458", "src/click/core.py"),
    ("pallets/click#3403", "src/click/core.py"),
    ("pallets/click#3360", "src/click/formatting.py"),
]
required_sections = [
    "## 项目结构",
    "## issue 拆解",
    "## 修改影响和风险",
    "## 测试结果怎么看",
    "## 本次训练的工程能力",
]


def eval_frame(payload):
    first = payload["related_files"][0]
    path = first["path"]
    evidence_id = first["evidence"][0]["id"]
    return {
        "project_summary": payload["project_summary"],
        "issue_summary": payload["issue_title"],
        "issue_breakdown": "先把现象、预期、复现条件和证据文件分开看。",
        "clarity": "需要结合 issue 文本和文件证据判断是否足够清楚。",
        "suitability": "适合作为 Guided Session V0 的证据定位评测样本。",
        "maintainer_draft": f"我会先根据 {evidence_id} 阅读 `{path}`，再补充验证结果。",
        "structure_map": payload["project_structure"],
        "reading_order": [f"先看 `{path}`，因为这里包含最直接的证据 {evidence_id}。"],
        "change_points": [f"`{path}` 是首要修改假设位置，需要继续读相邻测试。"],
        "impact_risks": [f"修改 `{path}` 前要确认相邻行为和兼容性风险。"],
        "validation_plan": ["运行相关测试并保留失败/通过输出。"],
        "test_result_interpretation": ["测试通过只说明已有断言未坏；失败要回到 evidence 重新定位。"],
        "ability_takeaways": ["训练项目阅读、issue 拆解、证据定位、影响分析和验证判断。"],
    }


failed = False
for issue, gold in cases:
    result = analyze(
        repo=repo,
        issue=issue,
        output_root=Path(".patchpath/eval-v0"),
        offline=True,
        llm_client=eval_frame,
    )
    top_paths = [item["path"] for item in result["related_files"][:5]]
    brief_path = Path(result["brief_path"])
    trace_path = Path(result["trace_path"])
    brief = brief_path.read_text(encoding="utf-8")
    missing_sections = [section for section in required_sections if section not in brief]
    ok = (
        brief_path.exists()
        and trace_path.exists()
        and gold in top_paths
        and not missing_sections
    )
    status = "PASS" if ok else "FAIL"
    print(f"{status} {issue} gold={gold} top5={top_paths}")
    if missing_sections:
        print(f"  missing sections: {', '.join(missing_sections)}")
    failed = failed or not ok

if failed:
    raise SystemExit(1)
PY
