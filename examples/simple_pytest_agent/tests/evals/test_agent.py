from agent import build_agent


def test_choose_math_tool() -> None:
    agent = build_agent()
    assert agent.choose_tool("Add 4 and 7") == "math"


def test_choose_search_tool() -> None:
    agent = build_agent()
    assert agent.choose_tool("What is the capital of France?") == "search"


def test_solve_math_task() -> None:
    agent = build_agent()
    assert agent.solve("Please add 12 and 30") == "42"


def test_solve_multiply_task() -> None:
    agent = build_agent()
    assert agent.solve("Please multiply 6 and 7") == "42"


def test_solve_search_task() -> None:
    agent = build_agent()
    assert agent.solve("What is the capital of France?") == "Paris"
