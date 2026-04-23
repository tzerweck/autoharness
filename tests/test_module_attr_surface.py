from __future__ import annotations

from pathlib import Path

from autoharness.config.models import ModuleAttrSurfaceConfig
from autoharness.surfaces.materialize import (
    copy_editable_surfaces_to_workspace,
    snapshot_candidate_surfaces_from_workspace,
    snapshot_surface_files,
)


def test_module_attr_surface_patches_workspace_and_snapshots(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    module_path = workspace / "prompt_holder.py"
    module_path.write_text('PROMPT = "old value"\n', encoding="utf-8")

    surface = ModuleAttrSurfaceConfig(
        name="prompt",
        kind="module_attr",
        target="PROMPT",
        module="prompt_holder",
        attribute="PROMPT",
        base_value="old value",
        emit_file="prompt.txt",
    )
    editable_dir = tmp_path / "editable"
    snapshot_surface_files({"prompt": surface}, editable_dir)
    (editable_dir / "prompt.txt").write_text("new value", encoding="utf-8")

    written = copy_editable_surfaces_to_workspace(
        {"prompt": surface},
        editable_dir,
        workspace,
    )

    assert written == [module_path]
    assert 'PROMPT = "new value"' in module_path.read_text(encoding="utf-8")

    snapshot_dir = tmp_path / "snapshot"
    snapshot_candidate_surfaces_from_workspace(
        {"prompt": surface},
        workspace,
        editable_dir,
        snapshot_dir,
    )
    assert (snapshot_dir / "prompt.txt").read_text(encoding="utf-8") == "new value"
