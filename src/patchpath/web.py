from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from patchpath.cli import analyze, load_env_file, parse_issue_ref


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DEMO_PATH = PROJECT_ROOT / "docs" / "prototypes" / "patchpath-web-demo.html"


def parse_brief_sections(brief: str) -> dict[str, Any]:
    title = ""
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in brief.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush()
            current = line[3:].strip()
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return {"title": title, "sections": sections}


def build_analyze_response(
    payload: dict[str, Any],
    analyzer: Callable[..., dict[str, Any]] = analyze,
    repo_resolver: Callable[[str], Path] | None = None,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    issue = str(payload.get("issue", "")).strip()
    if not issue:
        raise ValueError("issue is required")

    repo_path = Path(str(payload.get("repo", "")).strip()).expanduser() if payload.get("repo") else None
    if repo_path is None:
        repo_path = repo_resolver(issue) if repo_resolver else ensure_repo_checkout(issue)

    result = analyzer(
        repo=repo_path,
        issue=issue,
        output_root=output_root or Path.cwd() / ".patchpath" / "web-runs",
        offline=bool(payload.get("offline", False)),
    )
    brief_text = Path(result["brief_path"]).read_text(encoding="utf-8")
    trace_path = Path(result["trace_path"])
    trace_count = 0
    if trace_path.exists():
        trace_count = len([line for line in trace_path.read_text(encoding="utf-8").splitlines() if line])

    return {
        "ok": True,
        "issue": result["issue"],
        "run_dir": result["run_dir"],
        "repo_path": str(repo_path),
        "brief_path": result["brief_path"],
        "trace_path": result["trace_path"],
        "brief": parse_brief_sections(brief_text),
        "brief_markdown": brief_text,
        "related_files": result["related_files"][:5],
        "trace_count": trace_count,
    }


def repos_root() -> Path:
    return Path(os.environ.get("PATCHPATH_REPOS_DIR", Path.home() / ".patchpath" / "repos")).expanduser()


def load_pyproject(repo: Path) -> dict[str, Any]:
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def declared_python_test_command(repo: Path, manager: str) -> list[str]:
    data = load_pyproject(repo)
    dependency_groups = data.get("dependency-groups", {})
    optional_dependencies = data.get("project", {}).get("optional-dependencies", {})
    for group in ("tests", "test", "dev"):
        if group in dependency_groups:
            if manager == "uv":
                return ["uv", "sync", "--group", group]
    for extra in ("tests", "test", "dev"):
        if extra in optional_dependencies:
            if manager == "uv":
                return ["uv", "sync", "--extra", extra]
            if manager == "pip":
                return ["python", "-m", "pip", "install", "-e", f".[{extra}]"]
    return ["uv", "sync"] if manager == "uv" else []


def ensure_repo_checkout(
    issue: str,
    repos_dir: str | Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> Path:
    owner, repo, _number = parse_issue_ref(issue)
    root = Path(repos_dir).expanduser() if repos_dir else repos_root()
    checkout = root / owner / repo
    if (checkout / ".git").is_dir():
        return checkout
    if checkout.exists():
        raise RuntimeError(f"repo cache path exists but is not a git checkout: {checkout}")

    checkout.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", f"https://github.com/{owner}/{repo}.git", str(checkout)]
    completed = runner(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git clone failed")
    return checkout


def detect_test_environment(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path).expanduser().resolve()
    if (repo / "pyproject.toml").exists() and (repo / "uv.lock").exists():
        command = declared_python_test_command(repo, "uv")
        return {
            "available": True,
            "project_type": "Python",
            "dependency_files": ["pyproject.toml", "uv.lock"],
            "command": command,
            "cwd": str(repo),
        }
    if (repo / "pyproject.toml").exists() and (repo / "poetry.lock").exists():
        return {
            "available": True,
            "project_type": "Python",
            "dependency_files": ["pyproject.toml", "poetry.lock"],
            "command": ["poetry", "install"],
            "cwd": str(repo),
        }
    if (repo / "pyproject.toml").exists():
        command = declared_python_test_command(repo, "pip")
        if command:
            return {
                "available": True,
                "project_type": "Python",
                "dependency_files": ["pyproject.toml"],
                "command": command,
                "cwd": str(repo),
            }

    candidates: list[tuple[str, list[str], list[str]]] = [
        ("Node.js", ["package-lock.json", "package.json"], ["npm", "ci"]),
        ("Node.js", ["pnpm-lock.yaml", "package.json"], ["pnpm", "install", "--frozen-lockfile"]),
        ("Node.js", ["yarn.lock", "package.json"], ["yarn", "install", "--frozen-lockfile"]),
        ("Rust", ["Cargo.toml"], ["cargo", "test", "--no-run"]),
        ("Go", ["go.mod"], ["go", "test", "./...", "-run", "^$"]),
    ]
    for project_type, files, command in candidates:
        if all((repo / file).exists() for file in files):
            return {
                "available": True,
                "project_type": project_type,
                "dependency_files": files,
                "command": command,
                "cwd": str(repo),
            }
    return {
        "available": False,
        "project_type": "unknown",
        "dependency_files": [],
        "command": [],
        "cwd": str(repo),
        "message": "未检测到受支持的项目依赖声明。",
    }


def build_prepare_env_response(
    payload: dict[str, Any],
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    repo_path = str(payload.get("repo_path", "")).strip()
    if not repo_path:
        issue = str(payload.get("issue", "")).strip()
        if not issue:
            raise ValueError("repo_path or issue is required")
        repo_path = str(ensure_repo_checkout(issue))

    plan = detect_test_environment(repo_path)
    if not plan["available"]:
        return {"ok": False, "plan": plan, "error": plan.get("message")}
    completed = runner(
        plan["command"],
        cwd=plan["cwd"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "plan": plan,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "exit_code": completed.returncode,
    }


def make_handler(index_path: Path = WEB_DEMO_PATH) -> type[BaseHTTPRequestHandler]:
    class PatchPathHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self.send_text(index_path.read_text(encoding="utf-8"), "text/html; charset=utf-8")
                return
            if self.path == "/health":
                self.send_json({"ok": True})
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path not in ("/api/analyze", "/api/test-env/plan", "/api/test-env/prepare"):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw or "{}")
                if self.path == "/api/analyze":
                    self.send_json(build_analyze_response(payload))
                elif self.path == "/api/test-env/plan":
                    repo_path = str(payload.get("repo_path", "")).strip()
                    if not repo_path:
                        repo_path = str(ensure_repo_checkout(str(payload.get("issue", "")).strip()))
                    self.send_json({"ok": True, "plan": detect_test_environment(repo_path), "repo_path": repo_path})
                else:
                    self.send_json(build_prepare_env_response(payload))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return PatchPathHandler


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    load_env_file()
    server = ThreadingHTTPServer((host, port), make_handler())
    print(f"PatchPath web: http://{host}:{server.server_port}", file=sys.stderr)
    server.serve_forever()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="patchpath-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
