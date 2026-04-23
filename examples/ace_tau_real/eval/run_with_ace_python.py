"""Run a helper script with a usable ACE Python interpreter.

Resolution order:
1. ``AUTOHARNESS_ACE_PYTHON`` if it can import required ACE runtime deps
2. ``<workspace>/.venv/bin/python`` if healthy
3. sibling ACE venvs that already have the required packages

This lets AutoHarness evaluate the clean ACE snapshot without forcing a fresh
network-backed environment bootstrap first.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REQUIRED_MODULES = ("pydantic_ai", "litellm", "tau2", "dotenv")


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        raise SystemExit("Usage: run_with_ace_python.py <script> [args...]")

    script_arg = args[0]
    script_args = args[1:]

    workspace_root = Path(os.environ["AUTOHARNESS_WORKSPACE_ROOT"]).resolve()
    framework_root = Path(__file__).resolve().parents[3]
    script_path = (workspace_root / script_arg).resolve()
    if not script_path.exists():
        raise SystemExit(f"Target script does not exist: {script_path}")

    python_exe = _resolve_ace_python(workspace_root, framework_root)

    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = _prepend_path(
        [str(workspace_root), str(framework_root)],
        child_env.get("PYTHONPATH"),
    )
    child_env["AUTOHARNESS_ACE_PYTHON_SELECTED"] = str(python_exe)

    completed = subprocess.run(
        [str(python_exe), str(script_path), *script_args],
        cwd=workspace_root,
        env=child_env,
        text=True,
    )
    return completed.returncode


def _resolve_ace_python(workspace_root: Path, framework_root: Path) -> Path:
    explicit = os.environ.get("AUTOHARNESS_ACE_PYTHON", "").strip()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())

    candidates.extend(
        [
            workspace_root / ".venv" / "bin" / "python",
            framework_root.parent / "agentic-context-engine-main" / ".venv" / "bin" / "python",
            framework_root.parent / "feature-tzerweck-tau-airline-optimization" / ".venv" / "bin" / "python",
        ]
    )

    for candidate in candidates:
        if _python_has_required_modules(candidate, workspace_root, framework_root):
            return candidate

    rendered = "\n".join(f"- {path}" for path in candidates)
    raise SystemExit(
        "Could not find a usable ACE Python interpreter with required runtime deps.\n"
        f"Searched:\n{rendered}"
    )


def _python_has_required_modules(
    python_exe: Path,
    workspace_root: Path,
    framework_root: Path,
) -> bool:
    if not python_exe.exists():
        return False
    probe = (
        "import importlib.util, sys\n"
        f"mods = {REQUIRED_MODULES!r}\n"
        "missing = [m for m in mods if importlib.util.find_spec(m) is None]\n"
        "raise SystemExit(0 if not missing else 1)\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = _prepend_path(
        [str(workspace_root), str(framework_root)],
        env.get("PYTHONPATH"),
    )
    completed = subprocess.run(
        [str(python_exe), "-c", probe],
        cwd=workspace_root,
        env=env,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def _prepend_path(prefixes: list[str], existing: str | None) -> str:
    parts = [part for part in prefixes if part]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
