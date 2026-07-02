import json
from pathlib import Path

import pytest

from patchpath.cli import (
    analyze,
    load_env_file,
    main,
    parse_issue_ref,
    plan_search_terms,
    rank_files,
    read_project_summary,
)


@pytest.fixture(autouse=True)
def no_deepseek_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def fake_frame(payload):
    path = payload["related_files"][0]["path"]
    return {
        "project_summary": "Click 是命令行工具库。",
        "issue_summary": "这是一个真实 issue。",
        "clarity": "问题描述需要结合证据阅读。",
        "suitability": "适合作为证据定位练习。",
        "reading_order": [
            f"先看 `{path}`，这里是证据最集中的入口。",
            "再看测试文件，确认行为边界。",
        ],
        "change_points": [
            f"`{path}` 可能是主要修改点，因为 evidence 指向相关逻辑。"
        ],
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
        "## 项目是什么",
        "## issue 在解决什么",
        "## issue 是否清楚，缺哪些信息",
        "## 是否适合尝试",
        "## 相关文件 Top-K",
        "## 推荐阅读顺序",
        "## 可能修改点",
        "## 验证命令或缺失的验证信息",
        "## 风险点",
        "## 可发给 maintainer 的澄清问题/comment 草稿",
        "## trace 摘要",
    ]:
        assert section in brief


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
        frame["reading_order"] = ["先看 `src/click/missing.py`。"]
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
        frame["change_points"] = ["根据 E999 看 `src/click/shell_completion.py`。"]
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
            "clarity": "问题方向清楚，但还要确认触发命令和 shell 环境。",
            "suitability": "适合尝试：范围集中，已有相关源码和测试。",
            "reading_order": ["先看 `src/click/shell_completion.py`。"],
            "change_points": ["关注 `src/click/shell_completion.py` 的补全格式化逻辑。"],
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
            "clarity": "问题清楚。",
            "suitability": "not recommended：issue 已关闭，不适合作为当前贡献。",
            "reading_order": ["先看 `src/click/shell_completion.py`。"],
            "change_points": ["只做复盘，不建议当前修改。"],
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


def test_search_terms_filter_generic_noise():
    terms = plan_search_terms(
        {
            "title": "Document 415 on the receiving json section",
            "body": "add request text https pytest logLevel FST_ERR_ROUTE_LOG_LEVEL_INVALID",
        }
    )

    assert "logLevel" in terms
    assert "FST_ERR_ROUTE_LOG_LEVEL_INVALID" in terms
    assert not {"Document", "request", "text", "https", "pytest", "add"} & set(terms)


def test_docs_issue_prioritizes_matching_docs_path():
    files = {
        "docs/patterns/javascript.rst": {
            "path": "docs/patterns/javascript.rst",
            "score": 0.0,
            "match_count": 4,
            "terms": {"receiving", "json", "section"},
            "evidence": [{"id": "E1", "term": "receiving", "line": 1, "text": "Receiving JSON in Views"}],
        },
        "src/flask/app.py": {
            "path": "src/flask/app.py",
            "score": 0.0,
            "match_count": 20,
            "terms": {"json", "request"},
            "evidence": [{"id": "E2", "term": "json", "line": 1, "text": "json request"}],
        },
    }

    ranked = rank_files(
        files,
        {"title": "Document 415 on the receiving json section", "labels": ["docs"]},
    )

    assert ranked[0]["path"] == "docs/patterns/javascript.rst"


def test_ranking_keeps_matching_tests_near_source():
    files = {
        "src/_pytest/config/__init__.py": {
            "path": "src/_pytest/config/__init__.py",
            "score": 0.0,
            "match_count": 5,
            "terms": {"strict-config", "addopts"},
            "evidence": [{"id": "E1", "term": "strict-config", "line": 1, "text": "strict-config addopts"}],
        },
        "testing/test_config.py": {
            "path": "testing/test_config.py",
            "score": 0.0,
            "match_count": 4,
            "terms": {"strict-config", "addopts"},
            "evidence": [{"id": "E2", "term": "addopts", "line": 1, "text": "strict_config from addopts"}],
        },
        "src/_pytest/capture.py": {
            "path": "src/_pytest/capture.py",
            "score": 0.0,
            "match_count": 20,
            "terms": {"working"},
            "evidence": [{"id": "E3", "term": "working", "line": 1, "text": "working"}],
        },
    }

    top_paths = [item["path"] for item in rank_files(files)[:2]]

    assert "testing/test_config.py" in top_paths


def test_needs_info_issue_uses_review_points_not_change_points(tmp_path):
    repo = tmp_path / "pytest"
    (repo / "src/_pytest").mkdir(parents=True)
    (repo / "src/_pytest/logging.py").write_text("handlers loggers\n", encoding="utf-8")

    result = analyze(
        repo=repo,
        issue="pytest-dev/pytest#14603",
        output_root=tmp_path / "runs",
        offline=True,
        llm_client=lambda _payload: {
            "project_summary": "pytest 是测试框架。",
            "issue_summary": "非传播 logger handler 行为讨论。",
            "clarity": "需要更多复现和 maintainer 判断。",
            "suitability": "not recommended：needs information，不适合作为当前贡献。",
            "reading_order": ["先看 `src/_pytest/logging.py`。"],
            "change_points": ["检查 `src/_pytest/logging.py` 的 handler 逻辑。"],
        },
    )

    brief = (Path(result["run_dir"]) / "brief.md").read_text(encoding="utf-8")
    assert "## 澄清/复盘点" in brief
    assert "## 可能修改点" not in brief
