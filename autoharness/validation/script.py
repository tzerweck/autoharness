"""Script-based validation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from autoharness.validation.base import ValidationResult


def validate_script(workspace_root: Path, command: list[str], timeout_sec: float) -> ValidationResult:
    env = os.environ.copy()
    env["AUTOHARNESS_WORKSPACE_ROOT"] = str(workspace_root)
    try:
        completed = subprocess.run(
            command,
            cwd=workspace_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except Exception as exc:
        return ValidationResult(False, f"script validation failed to run: {exc}")

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        return ValidationResult(
            False,
            f"script validation exited with {completed.returncode}: {stderr or completed.stdout.strip()}",
        )
    return ValidationResult(True, completed.stdout.strip() or "script validation succeeded")
