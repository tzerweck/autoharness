"""Helpers for module-attribute editable surfaces."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from autoharness.config.models import ModuleAttrSurfaceConfig
from autoharness.errors import AutoharnessError


def apply_module_attr_surface(
    surface: ModuleAttrSurfaceConfig,
    editable_value_path: Path,
    workspace_root: Path,
) -> Path:
    module_path = resolve_module_path(surface.module, workspace_root)
    rendered_value = editable_value_path.read_text(encoding="utf-8")
    source = module_path.read_text(encoding="utf-8")
    updated = patch_module_attribute(
        source=source,
        attribute=surface.attribute,
        rendered_value=rendered_value,
        value_format=surface.value_format,
    )
    module_path.write_text(updated, encoding="utf-8")
    return module_path


def patch_module_attribute(
    source: str,
    attribute: str,
    rendered_value: str,
    value_format: str,
) -> str:
    tree = ast.parse(source)
    value_source = _render_value(rendered_value, value_format)
    for node in tree.body:
        start = end = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == attribute:
                    start, end = _node_value_span(source, node.value)
                    break
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == attribute and node.value is not None:
                start, end = _node_value_span(source, node.value)

        if start is not None and end is not None:
            return source[:start] + value_source + source[end:]

    suffix = "" if source.endswith("\n") else "\n"
    return f"{source}{suffix}{attribute} = {value_source}\n"


def resolve_module_path(module: str, workspace_root: Path) -> Path:
    module_parts = module.split(".")
    base = workspace_root.joinpath(*module_parts)
    module_file = base.with_suffix(".py")
    if module_file.exists():
        return module_file
    package_init = base / "__init__.py"
    if package_init.exists():
        return package_init
    raise AutoharnessError(
        f"Could not resolve module '{module}' under workspace {workspace_root}."
    )


def _render_value(rendered_value: str, value_format: str) -> str:
    if value_format == "python_expr":
        return rendered_value
    return json.dumps(rendered_value)


def _node_value_span(source: str, node: ast.AST) -> tuple[int, int]:
    assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1]) + node.col_offset
    end = sum(len(line) for line in lines[: node.end_lineno - 1]) + node.end_col_offset
    return start, end
