"""Python validation entrypoints."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from autoharness.errors import ConfigError
from autoharness.validation.base import ValidationResult


def validate_python_import(workspace_root: Path, entrypoint: str) -> ValidationResult:
    module_name, separator, symbol_name = entrypoint.partition(":")
    if not separator or not module_name or not symbol_name:
        raise ConfigError(
            "validation.entrypoint must look like 'module_name:symbol_name'."
        )

    _evict_workspace_modules(workspace_root)
    sys.path.insert(0, str(workspace_root))
    importlib.invalidate_caches()
    try:
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)
        value = symbol()
        if value is None:
            return ValidationResult(False, f"{entrypoint} returned None.")
        return ValidationResult(True, f"{entrypoint} returned {type(value).__name__}.")
    except Exception as exc:  # pragma: no cover - exercised through integration flow later.
        return ValidationResult(False, f"{entrypoint} failed: {exc}")
    finally:
        sys.path.pop(0)


def _evict_workspace_modules(workspace_root: Path) -> None:
    resolved_root = workspace_root.resolve()
    for name, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            module_path = Path(module_file).resolve()
        except OSError:
            continue
        if resolved_root in module_path.parents or module_path == resolved_root:
            sys.modules.pop(name, None)
