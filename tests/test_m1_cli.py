import json
from pathlib import Path

from patchpath.cli import analyze, parse_issue_ref, read_project_summary


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
