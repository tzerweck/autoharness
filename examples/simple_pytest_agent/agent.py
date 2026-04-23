"""Demonstrative agent harness used by the initial example eval suite."""

from __future__ import annotations

from pathlib import Path

from tools import MathTool, SearchTool


PROMPT = Path(__file__).with_name("prompt.md").read_text(encoding="utf-8")


class SimpleAgent:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.math_tool = MathTool()
        self.search_tool = SearchTool()

    def choose_tool(self, task: str) -> str:
        lowered = task.lower()
        if any(token in lowered for token in ("sum", "add", "multiply", "divide", "subtract")):
            return "math"
        return "search"

    def solve(self, task: str) -> str:
        tool_name = self.choose_tool(task)
        if tool_name == "math":
            return self.math_tool.run(task)
        return self.search_tool.run(task)


def build_agent() -> SimpleAgent:
    return SimpleAgent(PROMPT)
