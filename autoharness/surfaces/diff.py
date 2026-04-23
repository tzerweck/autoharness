"""Diff helpers for candidate surface changes."""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from autoharness.config.models import (
    ModuleAttrSurfaceConfig,
    SurfaceConfig,
    WorkspaceFileSurfaceConfig,
    WorkspaceTreeSurfaceConfig,
)
from autoharness.store.writer import write_text


def write_candidate_diff(
    surfaces: dict[str, SurfaceConfig],
    previous_dir: Path,
    current_dir: Path,
    output_path: Path,
) -> Path:
    patch_chunks: list[str] = []
    for surface in surfaces.values():
        for relative_name in _surface_snapshot_names(surface, previous_dir, current_dir):
            previous_path = previous_dir / relative_name
            current_path = current_dir / relative_name
            previous_lines = (
                previous_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if previous_path.exists()
                else []
            )
            current_lines = (
                current_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if current_path.exists()
                else []
            )
            diff_lines = list(
                unified_diff(
                    previous_lines,
                    current_lines,
                    fromfile=str(previous_path),
                    tofile=str(current_path),
                )
            )
            if diff_lines:
                patch_chunks.append("".join(diff_lines))

    write_text(output_path, "\n".join(chunk.rstrip("\n") for chunk in patch_chunks) + ("\n" if patch_chunks else ""))
    return output_path


def _surface_snapshot_names(
    surface: SurfaceConfig,
    previous_dir: Path,
    current_dir: Path,
) -> list[str]:
    if isinstance(surface, WorkspaceFileSurfaceConfig):
        return [surface.filename]
    if isinstance(surface, WorkspaceTreeSurfaceConfig):
        root = surface.target
        previous_root = previous_dir / root
        current_root = current_dir / root
        names: set[str] = set()
        if previous_root.exists():
            names.update(_iter_tree_files(previous_root, previous_dir))
        if current_root.exists():
            names.update(_iter_tree_files(current_root, current_dir))
        return sorted(names)
    if isinstance(surface, ModuleAttrSurfaceConfig):
        return [surface.emit_file]
    raise TypeError(f"Unsupported surface type: {type(surface)!r}")


def _iter_tree_files(root: Path, base_dir: Path) -> list[str]:
    return [
        str(path.relative_to(base_dir))
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
