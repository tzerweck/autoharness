"""Command-based proposer backend."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from autoharness.config.models import ProposerConfig
from autoharness.errors import AutoharnessError
from autoharness.proposer.base import ProposerResult
from autoharness.proposer.session import (
    detect_changed_files,
    load_structured_proposer_result,
    snapshot_editable_contents,
)


def run_command_proposer(
    proposer_config: ProposerConfig,
    workspace: Path,
    editable_files: list[Path],
) -> ProposerResult:
    if not proposer_config.command:
        raise AutoharnessError("Command proposer requires a non-empty proposer.command.")

    before = snapshot_editable_contents(editable_files)
    env = os.environ.copy()
    env.update(proposer_config.environment)
    env["AUTOHARNESS_EDITABLE_DIR"] = str(workspace / "editable")
    env["AUTOHARNESS_CONTEXT_DIR"] = str(workspace / "context")
    env["AUTOHARNESS_CONTRACT_DIR"] = str(workspace / "contract")

    completed = subprocess.run(
        proposer_config.command,
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=proposer_config.timeout_sec,
    )

    changed_files = detect_changed_files(before, editable_files)
    structured = load_structured_proposer_result(workspace, proposer_config.result_filename)

    return ProposerResult(
        changed_files=changed_files,
        notes=str(structured.get("notes", "Command proposer completed.")),
        metadata={
            "command": proposer_config.command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            **structured,
        },
    )
