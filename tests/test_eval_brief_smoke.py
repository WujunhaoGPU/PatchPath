import importlib.util
import json
from pathlib import Path


def load_eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval-brief-smoke.py"
    spec = importlib.util.spec_from_file_location("eval_brief_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_eval_run_reports_machine_readable_metrics(tmp_path):
    module = load_eval_module()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief.md").write_text(
        "# PatchPath Brief: demo/repo#1\n\n"
        "## 是否适合尝试\n"
        "not recommended: issue 已关闭，不适合作为当前贡献。\n\n"
        "## 相关文件 Top-K\n"
        "- `src/demo.py` score=1 evidence=E1 line 1 term `demo`\n\n"
        "## 推荐阅读顺序\n"
        "1. 先看 `src/demo.py`。\n\n"
        "## 澄清/复盘点\n"
        "- 补充复现环境。\n",
        encoding="utf-8",
    )
    (run_dir / "trace.jsonl").write_text(
        "\n".join(
            json.dumps(item)
            for item in [
                {"node": "issue_intake", "provider": "gh", "result_count": 1, "selected_paths": [], "fallback_reason": None},
                {"node": "tool_execution", "provider": "rg", "result_count": 1, "selected_paths": ["src/demo.py"], "fallback_reason": None},
                {"node": "tool_execution", "provider": "codegraph", "result_count": 0, "selected_paths": [], "fallback_reason": None},
                {"node": "llm_frame", "provider": "deepseek", "result_count": 1, "selected_paths": ["src/demo.py"], "fallback_reason": None},
                {"node": "evidence_ranking", "provider": "heuristics", "result_count": 1, "selected_paths": ["src/demo.py"], "fallback_reason": None},
            ]
        ),
        encoding="utf-8",
    )

    result = module.evaluate_run(
        {
            "issue": "demo/repo#1",
            "gold": ["src/demo.py", "tests/test_demo.py"],
            "expect_not_suitable": True,
            "expect_no_change_points": True,
        },
        run_dir,
    )

    assert result["hit_at_5"] is True
    assert result["gold_missing"] == ["tests/test_demo.py"]
    assert result["refs_outside_top"] == []
    assert result["closed_not_suitable"] is True
    assert result["has_trace_nodes"] is True
    assert result["negative_change_points_ok"] is True
