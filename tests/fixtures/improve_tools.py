from pathlib import Path
import json


editable_dir = Path("editable")
tools_path = editable_dir / "tools.py"
original = tools_path.read_text(encoding="utf-8")
updated = original.replace(
    "        if len(numbers) >= 2:\n            return str(sum(numbers))\n",
    (
        "        lowered = task.lower()\n"
        "        if 'multiply' in lowered and len(numbers) >= 2:\n"
        "            return str(numbers[0] * numbers[1])\n"
        "        if len(numbers) >= 2:\n"
        "            return str(sum(numbers))\n"
    ),
)
tools_path.write_text(updated, encoding="utf-8")

contract_dir = Path("contract")
contract_dir.mkdir(exist_ok=True)
(contract_dir / "proposer_result.json").write_text(
    json.dumps({"notes": "Added multiply support to MathTool."}),
    encoding="utf-8",
)
