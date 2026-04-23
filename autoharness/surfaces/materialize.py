"""Candidate surface materialization helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from autoharness.config.models import (
    ModuleAttrSurfaceConfig,
    SurfaceConfig,
    WorkspaceFileSurfaceConfig,
    WorkspaceTreeSurfaceConfig,
)
from autoharness.surfaces.module_attr import apply_module_attr_surface


def snapshot_surface_files(
    surfaces: dict[str, SurfaceConfig],
    destination_dir: Path,
) -> list[Path]:
    """Write the current surface state into a candidate snapshot directory."""

    written: list[Path] = []
    for surface in surfaces.values():
        if isinstance(surface, WorkspaceFileSurfaceConfig):
            output_path = destination_dir / surface.filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(surface.base_file, output_path)
            written.append(output_path)
            continue

        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            output_path = destination_dir / surface.target
            _copy_tree(surface.base_dir, output_path)
            written.append(output_path)
            continue

        if isinstance(surface, ModuleAttrSurfaceConfig):
            output_path = destination_dir / surface.emit_file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(surface.base_value, encoding="utf-8")
            written.append(output_path)
            continue

        raise TypeError(f"Unsupported surface type: {type(surface)!r}")

    return written


def snapshot_surface_files_from_source(
    surfaces: dict[str, SurfaceConfig],
    source_dir: Path,
    destination_dir: Path,
) -> list[Path]:
    """Copy previously snapshotted surface files into a new workspace."""

    written: list[Path] = []
    for surface in surfaces.values():
        relative_name = _surface_editable_name(surface)
        source_path = source_dir / relative_name
        destination_path = destination_dir / relative_name
        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            _copy_tree(source_path, destination_path)
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
        written.append(destination_path)
    return written


def copy_editable_surfaces_to_workspace(
    surfaces: dict[str, SurfaceConfig],
    editable_dir: Path,
    workspace_root: Path,
) -> list[Path]:
    """Apply edited surface files onto a materialized candidate workspace."""

    written: list[Path] = []
    for surface in surfaces.values():
        if isinstance(surface, WorkspaceFileSurfaceConfig):
            source_path = editable_dir / surface.filename
            destination_path = workspace_root / surface.target
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            written.append(destination_path)
            continue

        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            source_path = editable_dir / surface.target
            destination_path = workspace_root / surface.target
            _copy_tree(source_path, destination_path)
            written.append(destination_path)
            continue

        if isinstance(surface, ModuleAttrSurfaceConfig):
            source_path = editable_dir / surface.emit_file
            destination_path = apply_module_attr_surface(surface, source_path, workspace_root)
            written.append(destination_path)
            continue

        raise TypeError(f"Unsupported surface type: {type(surface)!r}")

    return written


def snapshot_candidate_surfaces_from_workspace(
    surfaces: dict[str, SurfaceConfig],
    workspace_root: Path,
    editable_dir: Path,
    destination_dir: Path,
) -> list[Path]:
    """Persist candidate surfaces after materialization for future iterations."""

    written: list[Path] = []
    for surface in surfaces.values():
        if isinstance(surface, WorkspaceFileSurfaceConfig):
            source = workspace_root / surface.target
            destination = destination_dir / surface.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            written.append(destination)
            continue

        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            source = workspace_root / surface.target
            destination = destination_dir / surface.target
            _copy_tree(source, destination)
            written.append(destination)
            continue

        if isinstance(surface, ModuleAttrSurfaceConfig):
            source = editable_dir / surface.emit_file
            destination = destination_dir / surface.emit_file
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            written.append(destination)
            continue

        raise TypeError(f"Unsupported surface type: {type(surface)!r}")

    return written


def _surface_editable_name(surface: SurfaceConfig) -> str:
    if isinstance(surface, WorkspaceFileSurfaceConfig):
        return surface.filename
    if isinstance(surface, WorkspaceTreeSurfaceConfig):
        return surface.target
    if isinstance(surface, ModuleAttrSurfaceConfig):
        return surface.emit_file
    raise TypeError(f"Unsupported surface type: {type(surface)!r}")


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".venv",
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
        ),
    )
