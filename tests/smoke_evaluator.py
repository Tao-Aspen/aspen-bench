import json
import os
from pathlib import Path


rubric = json.loads(Path("rubric.json").read_text())
assert Path("candidate/runner-smoke.txt").is_file()
assert Path("reference/code/AspenAI.sln").is_file()
assert Path("baseline/AspenAI.sln").is_file()
assert not Path("baseline/runner-smoke.txt").exists()
judgment = {
    "summary": "HARNESS SMOKE TEST ONLY. No model was invoked and this is not a benchmark performance result.",
    "criteria": [
        {"id": criterion["id"], "level": 0, "rationale": "Transport and schema smoke test only.", "verification": "inspected", "evidence": ["candidate/runner-smoke.txt:1 - harness fixture"]}
        for criterion in rubric["criteria"]
    ],
}
Path(os.environ["ASPEN_RESULT_FILE"]).write_text(json.dumps(judgment))
