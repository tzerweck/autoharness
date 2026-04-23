from __future__ import annotations

from pathlib import Path

from autoharness.config.models import WorkspaceTreeSurfaceConfig
from autoharness.surfaces.diff import write_candidate_diff
from autoharness.surfaces.materialize import (
    copy_editable_surfaces_to_workspace,
    snapshot_candidate_surfaces_from_workspace,
    snapshot_surface_files,
)


def test_workspace_tree_surface_snapshots_copies_and_diffs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ace_dir = workspace / "ace"
    (ace_dir / "module").mkdir(parents=True)
    (ace_dir / "module" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (ace_dir / "module" / "b.py").write_text("B = 2\n", encoding="utf-8")

    surface = WorkspaceTreeSurfaceConfig(
        name="ace_code",
        kind="workspace_tree",
        target="ace",
        base_dir=ace_dir,
    )

    editable_dir = tmp_path / "editable"
    written = snapshot_surface_files({"ace_code": surface}, editable_dir)
    before_snapshot = tmp_path / "before_snapshot"
    snapshot_surface_files({"ace_code": surface}, before_snapshot)

    assert written == [editable_dir / "ace"]
    assert (editable_dir / "ace" / "module" / "a.py").read_text(encoding="utf-8") == "A = 1\n"

    (editable_dir / "ace" / "module" / "a.py").write_text("A = 10\n", encoding="utf-8")
    (editable_dir / "ace" / "module" / "b.py").unlink()
    (editable_dir / "ace" / "module" / "c.py").write_text("C = 3\n", encoding="utf-8")

    copied = copy_editable_surfaces_to_workspace(
        {"ace_code": surface},
        editable_dir,
        workspace,
    )
    assert copied == [workspace / "ace"]
    assert (workspace / "ace" / "module" / "a.py").read_text(encoding="utf-8") == "A = 10\n"
    assert not (workspace / "ace" / "module" / "b.py").exists()
    assert (workspace / "ace" / "module" / "c.py").read_text(encoding="utf-8") == "C = 3\n"

    after_snapshot = tmp_path / "after_snapshot"
    snapshot_candidate_surfaces_from_workspace(
        {"ace_code": surface},
        workspace,
        editable_dir,
        after_snapshot,
    )

    diff_path = tmp_path / "unified.patch"
    write_candidate_diff(
        {"ace_code": surface},
        before_snapshot,
        after_snapshot,
        diff_path,
    )
    diff_text = diff_path.read_text(encoding="utf-8")
    assert "a.py" in diff_text
    assert "b.py" in diff_text
    assert "c.py" in diff_text
