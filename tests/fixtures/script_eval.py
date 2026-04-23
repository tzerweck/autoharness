from __future__ import annotations

import json
import os
from pathlib import Path


manifest_path = Path(os.environ["AUTOHARNESS_CASES_MANIFEST"])
result_path = Path(os.environ["AUTOHARNESS_RESULT_JSON_PATH"])
split = os.environ["AUTOHARNESS_SPLIT"]
cases = json.loads(manifest_path.read_text(encoding="utf-8"))

case_results = []
for case in cases:
    passed = not case["id"].endswith("fail")
    score = 1.0 if passed else 0.0
    case_results.append(
        {
            "case_id": case["id"],
            "split": split,
            "passed": passed,
            "score": score,
            "duration_sec": 0.01,
            "metadata": {"runner_ref": case["runner_ref"]},
        }
    )

summary = {
    "split": split,
    "n_cases": len(case_results),
    "n_passed": sum(1 for case in case_results if case["passed"]),
    "mean_score": sum(case["score"] for case in case_results) / len(case_results),
    "duration_sec": sum(case["duration_sec"] for case in case_results),
}
result_path.write_text(
    json.dumps({"summary": summary, "cases": case_results}),
    encoding="utf-8",
)
