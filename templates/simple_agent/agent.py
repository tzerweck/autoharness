"""Starter agent harness template."""

from __future__ import annotations

from pathlib import Path

from tools import EchoTool


PROMPT = Path(__file__).with_name("prompt.md").read_text(encoding="utf-8")


class TemplateAgent:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.echo_tool = EchoTool()

    def solve(self, task: str) -> str:
        return self.echo_tool.run(task)


def build_agent() -> TemplateAgent:
    return TemplateAgent(PROMPT)
