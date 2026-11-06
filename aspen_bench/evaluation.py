import asyncio
import math
import shutil
from pathlib import Path

from .common import digest, git, read_json, write_json
from .processes import execute
from .snapshots import clone_bundle, verify_reference


def validate_judgment(value, rubric):
    if not isinstance(value, dict) or not isinstance(value.get("criteria"), list):
        raise ValueError("Judgment must contain a criteria array")
    expected = {item["id"]: item for item in rubric["criteria"]}
    seen = set()
    score = 0.0
    for item in value["criteria"]:
        if not isinstance(item, dict):
            raise ValueError("Each criterion must be an object")
        identifier = item.get("id")
        if identifier not in expected or identifier in seen:
            raise ValueError(f"Unknown or duplicated criterion: {identifier}")
        seen.add(identifier)
        level = item.get("level")
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
            raise ValueError(f"Invalid level for {identifier}")
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            raise ValueError(f"Missing rationale for {identifier}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(entry, str) or not entry.strip() for entry in evidence):
            raise ValueError(f"Missing evidence for {identifier}")
        if item.get("verification") not in {"tested", "inspected", "blocked"}:
            raise ValueError(f"Invalid verification for {identifier}")
        if item["verification"] == "blocked" and level == 4:
            raise ValueError(f"Blocked criterion cannot receive full credit: {identifier}")
        score += expected[identifier]["weight"] * level / 4
    if seen != set(expected):
        raise ValueError(f"Missing criteria: {sorted(set(expected) - seen)}")
    if sum(item["weight"] for item in expected.values()) != 100 or not math.isfinite(score):
        raise ValueError("Invalid rubric weights")
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        raise ValueError("Missing judgment summary")
    return {**value, "score": round(score, 2), "maximum_score": 100}


async def evaluate_task(root, run, task, config):
    attempt = run / task["id"]
    source = read_json(attempt / "attempt.json")
    if source.get("capture", {}).get("status") != "completed":
        return {"status": "not_evaluated", "reason": "No complete submission snapshot"}
    if source.get("candidate", {}).get("status") in {"launch_failed", "cancelled", "running"}:
        return {"status": "not_evaluated", "reason": "Candidate did not finish a valid attempt"}
    if digest(attempt / "input" / "prompt.md") != source["prompt_sha256"]:
        raise ValueError("Candidate prompt changed after launch")
    for name, expected in source.get("specification_sha256", {}).items():
        if digest(attempt / "specification" / name) != expected:
            raise ValueError(f"Frozen task specification changed: {name}")
    snapshot = read_json(attempt / "specification" / "snapshot.json")
    await asyncio.to_thread(verify_reference, root, task, snapshot)
    bundle = root / "tasks" / task["id"] / "baseline.bundle"
    if digest(bundle) != source["bundle_sha256"]:
        raise ValueError("Baseline bundle changed after this attempt")
    if digest(attempt / "candidate.patch") != source["capture"]["patch_sha256"]:
        raise ValueError("Captured candidate patch changed")
    submission = attempt / "submission"
    if git(submission, "status", "--porcelain") or git(submission, "rev-parse", "HEAD^{tree}") != source["capture"]["tree"]:
        raise ValueError("Captured candidate repository changed")
    evaluation_root = attempt / "evaluations"
    evaluation_root.mkdir(exist_ok=True)
    number = 1
    while (evaluation_root / str(number)).exists():
        number += 1
    evaluation = evaluation_root / str(number)
    evaluation.mkdir()
    baseline = evaluation / "baseline"
    candidate = evaluation / "candidate"
    reference = evaluation / "reference"
    await asyncio.to_thread(clone_bundle, root / "tasks" / task["id"] / "baseline.bundle", baseline)
    await asyncio.to_thread(shutil.copytree, attempt / "submission", candidate, symlinks=True)
    await asyncio.to_thread(shutil.copytree, root / "private" / "references" / task["id"], reference, symlinks=True)
    for file in ["rubric.json", "source.json"]:
        shutil.copy2(attempt / "specification" / file, evaluation / file)
    shutil.copy2(attempt / "input" / "prompt.md", evaluation / "prompt.md")
    shutil.copy2(attempt / "candidate.patch", evaluation / "candidate.patch")
    shutil.copy2(attempt / "attempt.json", evaluation / "attempt.json")
    output = evaluation / "judgment.json"
    prompt = (attempt / "specification" / "EVALUATOR.md").read_text()
    prompt += "\n\nCurrent review packet\n\n"
    prompt += f"Task: {task['id']}\nWorking directory: {evaluation}\n"
    prompt += f"Write the JSON judgment to: {output}\n"
    prompt += "All relative paths below resolve within this packet. Read prompt.md, rubric.json, source.json, attempt.json, and reference/ledger.json first.\n"
    prompt_path = evaluation / "evaluate.md"
    prompt_path.write_text(prompt)
    replacements = {"prompt": str(prompt_path), "prompt_text": prompt, "workspace": str(evaluation), "output": str(output), "task": task["id"], "run_id": run.name}
    process = await execute(config, replacements, evaluation, evaluation / "process")
    result = {"status": "failed", "process": process, "packet": str(evaluation)}
    if process["status"] == "completed":
        try:
            judgment = validate_judgment(read_json(output), read_json(evaluation / "rubric.json"))
            write_json(evaluation / "validated-judgment.json", judgment)
            result.update(status="completed", score=judgment["score"], judgment=str(evaluation / "validated-judgment.json"))
        except (ValueError, OSError, TypeError, KeyError) as exception:
            result["error"] = str(exception)
    write_json(evaluation / "evaluation.json", result)
    return result
