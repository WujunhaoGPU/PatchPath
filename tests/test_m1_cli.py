import json
from pathlib import Path

import pytest

from patchpath.cli import (
    analyze,
    build_deepseek_prompt,
    build_project_structure,
    call_deepseek_frame,
    load_env_file,
    main,
    normalize_brief_frame,
    parse_issue_ref,
    read_project_summary,
)


@pytest.fixture(autouse=True)
def no_deepseek_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def fake_frame(payload):
    path = payload["related_files"][0]["path"]
    evidence_id = payload["related_files"][0]["evidence"][0]["id"]
    return {
        "project_summary": "Click 是命令行工具库。",
        "issue_summary": "这是一个真实 issue。",
        "issue_breakdown": "用户遇到的现象需要先回到代码证据确认边界。",
        "clarity": "问题描述需要结合证据阅读。",
        "suitability": "适合作为证据定位练习。",
        "maintainer_draft": f"我会先根据 {evidence_id} 阅读 `{path}`，再补充验证结果。",
        "structure_map": payload["project_structure"],
        "reading_order": [
            f"先看 `{path}`，这里是证据最集中的入口。",
            "再看测试文件，确认行为边界。",
        ],
        "change_points": [
            f"`{path}` 可能是主要修改点，因为 evidence 指向相关逻辑。"
        ],
        "impact_risks": [
            f"修改 `{path}` 可能影响相邻调用，先用 {evidence_id} 限定范围。"
        ],
        "validation_plan": ["先运行相关测试，再补充最小复现。"],
        "test_result_interpretation": ["测试失败说明定位假设还需要回到 evidence 复核。"],
        "ability_takeaways": ["训练项目阅读、证据定位、影响分析和维护者沟通。"],
    }


def test_parse_issue_ref_accepts_shorthand_and_url():
    assert parse_issue_ref("pallets/click#3502") == ("pallets", "click", 3502)
    assert parse_issue_ref("https://github.com/pallets/click/issues/3502") == (
        "pallets",
        "click",
        3502,
    )


def test_analyze_ranks_gold_source_file_for_real_eval_issue(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src/click/shell_completion.py").write_text(
        "class FishComplete:\n"
        "    def format_completion(self):\n"
        "        return 'fish completion string split complete_var'\n",
        encoding="utf-8",
    )
    (repo / "tests/test_shell_completion.py").write_text(
        "def test_fish_complete():\n"
        "    assert 'fish_complete'\n",
        encoding="utf-8",
    )
    (repo / "CHANGES.rst").write_text("fish completion fish fish\n", encoding="utf-8")

    result = analyze(
        repo=repo,
        issue="pallets/click#3502",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_frame,
    )

    top_paths = [item["path"] for item in result["related_files"][:5]]
    assert "src/click/shell_completion.py" in top_paths
    assert (Path(result["run_dir"]) / "brief.md").exists()
    assert (Path(result["run_dir"]) / "trace.jsonl").exists()

    trace_lines = (Path(result["run_dir"]) / "trace.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    trace = [json.loads(line) for line in trace_lines]
    assert any(entry["provider"] == "rg" and entry["result_count"] > 0 for entry in trace)
    ranking = next(entry for entry in trace if entry["node"] == "evidence_ranking")
    assert ranking["selected_evidence"][0]["path"] == "src/click/shell_completion.py"
    assert ranking["selected_evidence"][0]["evidence"]
    assert all(item["evidence"] for item in result["related_files"])


def test_brief_contains_required_m1_sections(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/utils.py").write_text(
        "def echo(value):\n"
        "    file.write(value)\n",
        encoding="utf-8",
    )

    result = analyze(
        repo=repo,
        issue="pallets/click#3487",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_frame,
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    for section in [
        "## 项目结构",
        "## issue 拆解",
        "## issue 是否清楚，缺哪些信息",
        "## 是否适合尝试",
        "## 相关文件 Top-K",
        "## 推荐阅读顺序和理由",
        "## 可能修改点",
        "## 修改影响和风险",
        "## 验证计划",
        "## 测试结果怎么看",
        "## maintainer 沟通草稿",
        "## 本次训练的工程能力",
        "## trace 摘要",
    ]:
        assert section in brief


def test_deepseek_prompt_requires_chinese_issue_translation():
    prompt = build_deepseek_prompt(
        {
            "project_summary": "`click`: Click is a Python package",
            "project_structure": ["click/"],
            "issue_title": "Empty output from HelpFormatter.write_usage",
            "issue_state": "closed",
            "issue_body": 'Expected "Usage: program" from write_usage(args="")',
            "labels": ["bug"],
            "comments": [{"body": "A fix is being worked on at PR #3434"}],
            "related_files": [],
        }
    )

    assert "必须使用简体中文" in prompt
    assert "HelpFormatter.write_usage" in prompt
    assert "函数名、类名、方法名、文件路径、命令、错误信息、PR 编号" in prompt
    assert "结合仓库语境、issue 正文、评论和 related_files" in prompt
    assert "不要把专有名词、协议名、产品名和代码标识符强行翻译" in prompt


def test_normalize_frame_rejects_english_issue_breakdown():
    frame = fake_frame(
        {
            "project_structure": ["click/"],
            "related_files": [
                {
                    "path": "src/click/formatting.py",
                    "evidence": [{"id": "E1"}],
                }
            ]
        }
    )
    frame["issue_summary"] = "HelpFormatter.write_usage outputs an empty line."
    frame["issue_breakdown"] = "The bug is in write_usage when args is empty."

    with pytest.raises(ValueError, match="must be Chinese"):
        normalize_brief_frame(frame)


def test_normalize_frame_accepts_scalar_list_fields_and_rejects_bad_shapes():
    frame = fake_frame(
        {
            "project_structure": ["click/"],
            "related_files": [
                {
                    "path": "src/click/formatting.py",
                    "evidence": [{"id": "E1"}],
                }
            ],
        }
    )
    frame["test_result_interpretation"] = "测试通过说明当前断言覆盖的行为没有坏。"

    normalized = normalize_brief_frame(frame)

    assert normalized["test_result_interpretation"] == [
        "测试通过说明当前断言覆盖的行为没有坏。"
    ]

    frame["test_result_interpretation"] = {"text": "测试通过。"}
    with pytest.raises(ValueError, match="invalid shape"):
        normalize_brief_frame(frame)

    frame["test_result_interpretation"] = ""
    with pytest.raises(ValueError, match="missing fields"):
        normalize_brief_frame(frame)


def test_deepseek_timeout_is_clear_and_configurable(monkeypatch):
    captured = {}

    def fake_urlopen(_request, timeout):
        captured["timeout"] = timeout
        raise TimeoutError("read operation timed out")

    monkeypatch.setenv("PATCHPATH_LLM_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="DeepSeek request timed out after 7 seconds"):
        call_deepseek_frame("key", "model", {"issue_title": "x"})
    assert captured["timeout"] == 7


def test_llm_rewrites_reading_order_and_change_points(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    result = analyze(
        repo=repo,
        issue="pallets/click#3502",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_frame,
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    assert "先看 `src/click/shell_completion.py`，这里是证据最集中的入口。" in brief
    assert "可能是主要修改点" in brief
    assert "matched `fish`" not in brief
    assert "先阅读 Top-K 源文件和对应测试" not in brief


def test_llm_frame_rejects_paths_outside_topk(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    def fake_llm(_payload):
        frame = fake_frame(_payload)
        frame["impact_risks"] = ["先看 `src/click/missing.py` 的影响。"]
        return frame

    with pytest.raises(RuntimeError, match="outside Top-K"):
        analyze(
            repo=repo,
            issue="pallets/click#3502",
            output_root=tmp_path / "runs",
            offline=True,
            llm_client=fake_llm,
        )


def test_llm_frame_rejects_unknown_evidence_ids(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    def fake_llm(_payload):
        frame = fake_frame(_payload)
        frame["test_result_interpretation"] = ["根据 E999 判断测试失败原因。"]
        return frame

    with pytest.raises(RuntimeError, match="unknown evidence ids"):
        analyze(
            repo=repo,
            issue="pallets/click#3502",
            output_root=tmp_path / "runs",
            offline=True,
            llm_client=fake_llm,
        )


def test_codegraph_default_boost_adds_trace_and_evidence(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "docs/shell-completion.md").write_text("\n".join(["fish"] * 80), encoding="utf-8")
    (repo / "src/click/shell_completion.py").write_text("class FishComplete:\n    pass\n", encoding="utf-8")

    def fake_codegraph(_repo, terms):
        assert "fish_complete" in terms
        return [
            {
                "path": "src/click/shell_completion.py",
                "symbol": "FishComplete",
                "kind": "class",
                "term": "fish_complete",
            }
        ]

    result = analyze(
        repo=repo,
        issue="pallets/click#3502",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_frame,
        codegraph_runner=fake_codegraph,
    )

    assert result["related_files"][0]["path"] == "src/click/shell_completion.py"
    assert any(
        evidence["term"] == "codegraph:FishComplete"
        for evidence in result["related_files"][0]["evidence"]
    )
    trace = [
        json.loads(line)
        for line in (Path(result["run_dir"]) / "trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    codegraph_trace = next(entry for entry in trace if entry["provider"] == "codegraph")
    assert codegraph_trace["selected_paths"] == ["src/click/shell_completion.py"]


def test_brief_uses_llm_frame_for_intro_sections(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "README.md").write_text("Click is a CLI toolkit.\n", encoding="utf-8")
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    def fake_llm(_payload):
        return {
            "project_summary": "Click 是一个用来写命令行工具的 Python 库。",
            "issue_summary": "Fish 自动补全在 8.4.1 版本坏了。",
            "issue_breakdown": "需要先确认 fish 补全格式化逻辑。",
            "clarity": "问题方向清楚，但还要确认触发命令和 shell 环境。",
            "suitability": "适合尝试：范围集中，已有相关源码和测试。",
            "maintainer_draft": "我会先验证 fish 补全行为再提交结论。",
            "structure_map": _payload["project_structure"],
            "reading_order": ["先看 `src/click/shell_completion.py`。"],
            "change_points": ["关注 `src/click/shell_completion.py` 的补全格式化逻辑。"],
            "impact_risks": ["修改补全格式可能影响其他 shell。"],
            "validation_plan": ["先运行相关测试，再结合补全行为补最小复现。"],
            "test_result_interpretation": ["如果测试失败，先确认输出格式是否变化。"],
            "ability_takeaways": ["训练 shell 补全路径定位。"],
        }

    result = analyze(
        repo=repo,
        issue="pallets/click#3502",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_llm,
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    assert "Click 是一个用来写命令行工具的 Python 库。" in brief
    assert "Fish 自动补全在 8.4.1 版本坏了。" in brief
    assert "问题方向清楚，但还要确认触发命令和 shell 环境。" in brief
    assert "适合尝试：范围集中，已有相关源码和测试。" in brief

    trace = [
        json.loads(line)
        for line in (Path(result["run_dir"]) / "trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert any(entry["node"] == "llm_frame" and entry["provider"] == "llm" for entry in trace)


def test_analyze_requires_deepseek_key_without_injected_llm(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        analyze(
            repo=repo,
            issue="pallets/click#3502",
            output_root=tmp_path / "runs",
            offline=True,
        )


def test_cli_reports_missing_deepseek_key_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    exit_code = main([
        "analyze",
        "--repo",
        str(repo),
        "--issue",
        "pallets/click#3502",
        "--offline",
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "DEEPSEEK_API_KEY is required" in captured.err
    assert "Traceback" not in captured.err


def test_load_env_file_sets_deepseek_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=from-env-file\n"
        "PATCHPATH_LLM_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    load_env_file(env_file)

    assert __import__("os").environ["DEEPSEEK_API_KEY"] == "from-env-file"
    assert __import__("os").environ["PATCHPATH_LLM_MODEL"] == "deepseek-v4-pro"


def test_incomplete_llm_frame_fails(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing fields"):
        analyze(
            repo=repo,
            issue="pallets/click#3502",
            output_root=tmp_path / "runs",
            offline=True,
            llm_client=lambda _payload: {"project_summary": "Click 是命令行工具库。"},
        )


def test_closed_issue_llm_frame_is_not_current_contribution(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/shell_completion.py").write_text("fish\n", encoding="utf-8")

    result = analyze(
        repo=repo,
        issue="pallets/click#3502",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=lambda _payload: {
            "project_summary": "Click 是命令行工具库。",
            "issue_summary": "Fish 补全坏了。",
            "issue_breakdown": "这个 closed issue 适合复盘定位过程。",
            "clarity": "问题清楚。",
            "suitability": "not recommended：issue 已关闭，不适合作为当前贡献。",
            "maintainer_draft": "这个 issue 已关闭，不建议再发当前贡献 comment。",
            "structure_map": _payload["project_structure"],
            "reading_order": ["先看 `src/click/shell_completion.py`。"],
            "change_points": ["只做复盘，不建议当前修改。"],
            "impact_risks": ["不要在已关闭 issue 上重复提交相同修改。"],
            "validation_plan": ["只作为回归样本运行相关测试。"],
            "test_result_interpretation": ["通过说明当前分支可能已包含修复。"],
            "ability_takeaways": ["训练 closed issue 的复盘判断。"],
        },
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    assert "不适合作为当前贡献" in brief


def test_source_definition_match_beats_noisy_test_mentions(tmp_path):
    repo = tmp_path / "click"
    (repo / "src/click").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src/click/utils.py").write_text(
        "def echo(value, file=None):\n"
        "    if isinstance(value, (bytes, bytearray)):\n"
        "        file.write(value)\n",
        encoding="utf-8",
    )
    (repo / "src/click/testing.py").write_text(
        "\n".join(["echo helper noise"] * 40),
        encoding="utf-8",
    )
    (repo / "tests/test_utils.py").write_text(
        "\n".join(["def test_echo_noise(): assert 'echo'"] * 80),
        encoding="utf-8",
    )

    result = analyze(
        repo=repo,
        issue="pallets/click#3487",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_frame,
    )

    top_paths = [item["path"] for item in result["related_files"][:5]]
    assert top_paths[0] == "src/click/utils.py"


def test_project_summary_skips_html_logo_lines(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# <div><img src='logo.svg'></div>\n\n"
        "# Click\n\n"
        "Click is a Python package for creating command line interfaces.\n",
        encoding="utf-8",
    )

    assert read_project_summary(repo) == (
        "`click`: Click is a Python package for creating command line interfaces."
    )


def test_project_structure_scanner_detects_common_files_and_directories(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for directory in ("src", "tests", "docs"):
        (repo / directory).mkdir()

    structure = build_project_structure(repo)

    assert structure[0] == "project/"
    assert any("pyproject.toml" in line and "Python 包配置" in line for line in structure)
    assert any("src/" in line and "源码" in line for line in structure)
    assert any("tests/" in line and "测试" in line for line in structure)
    assert any("docs/" in line and "文档" in line for line in structure)


def test_project_structure_highlights_issue_related_paths(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='click'\n", encoding="utf-8")
    (repo / "src/click").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src/click/formatting.py").write_text("class HelpFormatter: pass\n", encoding="utf-8")
    (repo / "tests/test_formatting.py").write_text("def test_usage(): pass\n", encoding="utf-8")

    structure = build_project_structure(
        repo,
        ["src/click/formatting.py", "tests/test_formatting.py"],
    )

    assert any("|-- src/" in line and "源码" in line for line in structure)
    assert any("formatting.py" in line and "[issue] 当前 issue 相关源码" in line for line in structure)
    assert any("test_formatting.py" in line and "[issue] 当前 issue 相关测试" in line for line in structure)


def test_project_structure_describes_common_js_entry_files(tmp_path):
    repo = tmp_path / "contextforge"
    repo.mkdir()
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "test").mkdir()
    (repo / "src/cli.js").write_text("console.log('cli')\n", encoding="utf-8")
    (repo / "src/core.js").write_text("export const core = true\n", encoding="utf-8")
    (repo / "src/mcp.js").write_text("export const mcp = true\n", encoding="utf-8")
    (repo / "test/core.test.js").write_text("test('core')\n", encoding="utf-8")

    structure = build_project_structure(
        repo,
        ["src/cli.js", "src/core.js", "src/mcp.js", "test/core.test.js"],
    )

    assert any("cli.js" in line and "命令行入口" in line and "[issue] 当前 issue 相关源码" in line for line in structure)
    assert any("core.js" in line and "核心逻辑" in line and "[issue] 当前 issue 相关源码" in line for line in structure)
    assert any("mcp.js" in line and "MCP 集成" in line and "[issue] 当前 issue 相关源码" in line for line in structure)
    assert any("core.test.js" in line and "测试文件" in line and "[issue] 当前 issue 相关测试" in line for line in structure)


def test_brief_uses_scanned_project_tree_not_llm_structure_rewrite(tmp_path):
    repo = tmp_path / "click"
    repo.mkdir()
    (repo / "src/click").mkdir(parents=True)
    (repo / "src/click/formatting.py").write_text("HelpFormatter write_usage\n", encoding="utf-8")

    def fake_llm(payload):
        frame = fake_frame(payload)
        frame["structure_map"] = ["README-only summary"]
        return frame

    result = analyze(
        repo=repo,
        issue="pallets/click#3360",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=fake_llm,
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    assert "```text\nclick/" in brief
    assert "formatting.py" in brief
    assert "README-only summary" not in brief
