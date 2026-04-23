"""Base data structures for editable surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MaterializedSurface:
    name: str
    source_path: Path
    target_path: Path
