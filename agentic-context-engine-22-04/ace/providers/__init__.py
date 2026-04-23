"""ACE LLM providers — PydanticAI model resolution and configuration.

- ``resolve_model`` — resolve a model string to a PydanticAI model
- ``settings_from_config`` — build ModelSettings from ACEModelConfig
- ``ModelConfig`` / ``ACEModelConfig`` — configuration types
- ``validate_connection`` / ``search_models`` — model registry helpers
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Config is lightweight — always available eagerly.
from .config import ACEModelConfig, ModelConfig, load_config, save_config

if TYPE_CHECKING:
    from .pydantic_ai import resolve_model, settings_from_config
    from .registry import ValidationResult, search_models, validate_connection

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # PydanticAI helpers
    "resolve_model": ("ace.providers.pydantic_ai", "resolve_model"),
    "settings_from_config": ("ace.providers.pydantic_ai", "settings_from_config"),
    # Registry
    "ValidationResult": ("ace.providers.registry", "ValidationResult"),
    "validate_connection": ("ace.providers.registry", "validate_connection"),
    "search_models": ("ace.providers.registry", "search_models"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'ace.providers' has no attribute {name!r}")


__all__ = [
    # Config
    "ModelConfig",
    "ACEModelConfig",
    "load_config",
    "save_config",
    # PydanticAI helpers
    "resolve_model",
    "settings_from_config",
    # Registry
    "ValidationResult",
    "validate_connection",
    "search_models",
]
