import json
import sys
import types
from pathlib import Path

import pytest

from patchpath.web import (
    WEB_DEMO_PATH,
    build_analyze_response,
    build_prepare_env_response,
    detect_test_environment,
    ensure_repo_checkout,
    parse_brief_sections,
)
from patchpath.cli import main


def test_parse_brief_sections_extracts_title_and_sections():
    brief = (
        "# PatchPath 开源贡献训练单: pallets/click#3360\n\n"
        "## 项目结构\n"
        "`click`: Click project\n\n"
        "- src/: source code\n\n"
        "## issue 拆解\n"
        "usage output is empty\n"
    )

    parsed = parse_brief_sections(brief)

    assert parsed["title"] == "PatchPath 开源贡献训练单: pallets/click#3360"
    assert parsed["sections"]["项目结构"] == "`click`: Click project\n\n- src/: source code"
    assert parsed["sections"]["issue 拆解"] == "usage output is empty"


def test_build_analyze_response_uses_injected_analyzer(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    brief_path = run_dir / "brief.md"
    trace_path = run_dir / "trace.jsonl"
    brief_path.write_text(
        "# PatchPath 开源贡献训练单: pallets/click#3360\n\n"
        "## 项目结构\n"
        "project structure\n",
        encoding="utf-8",
    )
    trace_path.write_text(json.dumps({"node": "issue_intake"}) + "\n", encoding="utf-8")

    def fake_analyzer(**_kwargs):
        return {
            "run_dir": str(run_dir),
            "brief_path": str(brief_path),
            "trace_path": str(trace_path),
            "related_files": [
                {
                    "path": "src/click/formatting.py",
                    "score": 42.0,
                    "evidence": [{"id": "E1", "line": 10, "term": "HelpFormatter"}],
                }
            ],
            "issue": {"key": "pallets/click#3360", "title": "Empty usage"},
        }

    response = build_analyze_response(
        {"issue": "pallets/click#3360", "offline": True},
        analyzer=fake_analyzer,
        repo_resolver=lambda _issue: Path("../click"),
        output_root=tmp_path / "runs",
    )

    assert response["ok"] is True
    assert response["issue"]["key"] == "pallets/click#3360"
    assert response["brief"]["sections"]["项目结构"] == "project structure"
    assert response["related_files"][0]["path"] == "src/click/formatting.py"
    assert response["trace_count"] == 1


def test_ensure_repo_checkout_clones_into_cache(tmp_path):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        dest = Path(command[-1])
        dest.mkdir(parents=True)
        (dest / ".git").mkdir()
        return types.SimpleNamespace(returncode=0, stderr="")

    path = ensure_repo_checkout(
        "https://github.com/pallets/click/issues/3360",
        repos_dir=tmp_path / "repos",
        runner=fake_run,
    )

    assert path == tmp_path / "repos" / "pallets" / "click"
    assert calls == [
        [
            "git",
            "clone",
            "https://github.com/pallets/click.git",
            str(tmp_path / "repos" / "pallets" / "click"),
        ]
    ]


def test_ensure_repo_checkout_reuses_existing_checkout(tmp_path):
    repo = tmp_path / "repos" / "pallets" / "click"
    (repo / ".git").mkdir(parents=True)

    path = ensure_repo_checkout(
        "pallets/click#3360",
        repos_dir=tmp_path / "repos",
        runner=lambda *_args, **_kwargs: pytest.fail("should not clone"),
    )

    assert path == repo


def test_detect_test_environment_prefers_uv_for_python_project(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='x'\n\n[dependency-groups]\ntests=['pytest']\n",
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text("", encoding="utf-8")

    plan = detect_test_environment(repo)

    assert plan["available"] is True
    assert plan["project_type"] == "Python"
    assert plan["command"] == ["uv", "sync", "--group", "tests"]
    assert plan["cwd"] == str(repo)


def test_detect_test_environment_does_not_guess_pip_dependency_groups(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='x'\n\n[dependency-groups]\ntests=['pytest']\n",
        encoding="utf-8",
    )

    plan = detect_test_environment(repo)

    assert plan["available"] is False


def test_prepare_env_response_runs_detected_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='x'\n\n[dependency-groups]\ntests=['pytest']\n",
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text("", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["cwd"]))
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

    response = build_prepare_env_response({"repo_path": str(repo)}, runner=fake_run)

    assert response["ok"] is True
    assert response["plan"]["command"] == ["uv", "sync", "--group", "tests"]
    assert calls == [(["uv", "sync", "--group", "tests"], str(repo))]


def test_web_prototype_uses_issue_url_and_test_env_button():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert "GitHub Issue URL" in html
    assert "准备测试环境" in html
    assert "/api/test-env/plan" in html
    assert "/api/test-env/prepare" in html
    assert "repoInput" not in html
    assert "offlineInput" not in html
    assert "使用内置 issue fixture" not in html


def test_web_prototype_uses_workbench_layout():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert 'class="workbench"' in html
    assert 'class="panel section-nav"' in html
    assert 'class="panel coach-rail"' in html
    assert "下一步" in html
    assert 'class="tabs"' not in html


def test_web_prototype_keeps_structure_as_wide_block_and_meta_readable():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert "structure-block" in html
    assert "issue-block" in html
    assert "assessment-grid" in html
    assert "grid-template-columns: 72px minmax(0, 1fr)" in html
    assert "white-space: nowrap" in html


def test_web_prototype_sample_issue_breakdown_is_chinese_with_code_terms():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert "HelpFormatter.write_usage 在没有传递参数时输出空行" in html
    assert "Usage: program" in html
    assert "PR #3434" in html
    assert "证据驱动" in html
    assert "不自动改代码" in html
    assert "第 ${file.line} 行 关键词" in html
    assert "outputs an empty line when no args" not in html
    assert "Evidence-backed" not in html


def test_web_prototype_persists_issue_url_and_last_result():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert "patchpath.issueUrl" in html
    assert "patchpath.lastAnalyzeResult" in html
    assert "localStorage.setItem(STORAGE_ISSUE_KEY" in html
    assert "localStorage.setItem(STORAGE_RESULT_KEY" in html
    assert "restoreSavedSession()" in html


def test_web_prototype_keeps_current_result_on_analyze_failure():
    html = WEB_DEMO_PATH.read_text(encoding="utf-8")

    assert "分析失败，保留当前结果" in html
    assert "后端不可用，显示样例" not in html
    assert "真实后端暂不可用" not in html


def test_cli_serve_dispatches_web_server(monkeypatch):
    called = {}

    def fake_serve(host, port):
        called["host"] = host
        called["port"] = port

    monkeypatch.setitem(sys.modules, "patchpath.web", types.SimpleNamespace(serve=fake_serve))

    assert main(["serve", "--host", "127.0.0.1", "--port", "0"]) == 0
    assert called == {"host": "127.0.0.1", "port": 0}
