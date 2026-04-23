"""Final report generation helpers."""

from __future__ import annotations

from pathlib import Path

from autoharness.reporting.summary import render_run_summary
from autoharness.store.writer import write_text


def render_final_report(run_dir: Path) -> str:
    return render_run_summary(run_dir)


def write_final_report(run_dir: Path) -> Path:
    output_path = run_dir / "reports" / "final.md"
    write_text(output_path, render_final_report(run_dir))
    return output_path
