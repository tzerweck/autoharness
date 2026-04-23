"""Manual proposer backend."""

from __future__ import annotations

import shutil
from pathlib import Path

from autoharness.config.models import ProposerConfig
from autoharness.errors import AutoharnessError
from autoharness.proposer.base import ProposerResult
from autoharness.proposer.session import (
    detect_changed_files,
    load_structured_proposer_result,
    snapshot_editable_contents,
)


def run_manual_proposer(
    proposer_config: ProposerConfig,
    workspace: Path,
    editable_files: list[Path],
) -> ProposerResult:
    if proposer_config.manual_source_dir is None:
        raise AutoharnessError(
            "manual proposer requires proposer.manual_source_dir so files can be staged."
        )

    before = snapshot_editable_contents(editable_files)
    editable_root = workspace / "editable"
    for path in editable_files:
        relative = path.relative_to(editable_root)
        source = proposer_config.manual_source_dir / relative
        if source.exists():
            if source.is_dir():
                if path.exists():
                    shutil.rmtree(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, path)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, path)

    changed_files = detect_changed_files(before, editable_files)
    structured = load_structured_proposer_result(
        proposer_config.manual_source_dir,
        proposer_config.result_filename,
    )
    metadata = {"mode": "manual", "returncode": 0, **structured}
    return ProposerResult(
        changed_files=changed_files,
        notes=str(structured.get("notes", "Manual proposer staged candidate files.")),
        metadata=metadata,
    )
