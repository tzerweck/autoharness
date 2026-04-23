"""Base types for proposer backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from autoharness.config.models import ProposerConfig
from autoharness.errors import AutoharnessError


@dataclass(frozen=True)
class ProposerResult:
    changed_files: list[Path] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class ProposerBackend(Protocol):
    def run(self, workspace: Path) -> ProposerResult:
        """Execute the proposer in the provided workspace."""


def run_proposer(
    proposer_config: ProposerConfig,
    workspace: Path,
    editable_files: list[Path],
) -> ProposerResult:
    if proposer_config.backend == "command":
        from autoharness.proposer.command import run_command_proposer

        return run_command_proposer(proposer_config, workspace, editable_files)
    if proposer_config.backend == "manual":
        from autoharness.proposer.manual import run_manual_proposer

        return run_manual_proposer(proposer_config, workspace, editable_files)
    raise AutoharnessError(f"Unsupported proposer backend: {proposer_config.backend}")
