"""Simple tool implementations for the example agent."""

from __future__ import annotations

import re


class MathTool:
    def run(self, task: str) -> str:
        numbers = [int(match) for match in re.findall(r"-?\d+", task)]
        if len(numbers) >= 2:
            return str(sum(numbers))
        return "0"


class SearchTool:
    def run(self, task: str) -> str:
        if "capital of france" in task.lower():
            return "Paris"
        return "search-result"
