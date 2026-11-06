import argparse
import asyncio
import datetime
import shutil
import subprocess
import uuid
from pathlib import Path

from aspen_bench.common import ROOT, digest, git, read_json, write_json
from aspen_bench.runner import evaluate_tasks, run_tasks
from aspen_bench.snapshots import file_manifest


def main():
    parser = argparse.ArgumentParser(description="Make bounded live Claude SDK calls through the benchmark runner using tiny disposable coding tasks, not the real benchmark.")
    parser.add_argument("--models", nargs="+", default=["haiku", "sonnet", "opus"])
    args = parser.parse_args()
    if len(args.models) != len(set(args.models)) or any("/" in model or ".." in model for model in args.models):
        parser.error("Supply unique model IDs or aliases without slashes")
    root = ROOT / "private" / "validation" / ("claude-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    root.mkdir(parents=True)
    shutil.copy2(ROOT / "EVALUATOR.md", root / "EVALUATOR.md")
    tasks = []
    for model in args.models:
        task = {"id": model}
        tasks.append(task)
        folder = root / "tasks" / model
        source = folder / "source"
        source.mkdir(parents=True)
        (source / "sum.mjs").write_text("export const sum = (a, b) => a - b;\n")
        (source / "AGENTS.md").write_text("Do not write code comments.\n")
        (source / "test.mjs").write_text("import assert from 'node:assert/strict';\nimport { sum } from './sum.mjs';\nassert.equal(sum(2, 3), 5);\nassert.equal(sum(-2, 3), 1);\n")
        git(source, "init", "--quiet", "--initial-branch=main")
        git(source, "config", "user.name", "Aspen smoke fixture")
        git(source, "config", "user.email", "fixture@localhost")
        git(source, "add", ".")
        git(source, "commit", "--quiet", "-m", "Fixture baseline")
        bundle = folder / "baseline.bundle"
        git(source, "bundle", "create", str(bundle), "main")
        reference = root / "private" / "references" / model
        (reference / "code").mkdir(parents=True)
        (reference / "code" / "sum.mjs").write_text("export const sum = (a, b) => a + b;\n")
        write_json(reference / "ledger.json", {"fixture": True, "scope": "Fix sum(a, b) to add the arguments."})
        write_json(folder / "snapshot.json", {"baseline_commit": git(source, "rev-parse", "HEAD"), "bundle_sha256": digest(bundle), "reference_files": file_manifest(reference)})
        write_json(folder / "source.json", {"fixture": True})
        write_json(folder / "rubric.json", {"criteria": [{"id": "addition", "weight": 100, "description": "sum(a, b) adds positive and negative numbers; original tests remain unchanged. Level 0: missing, 1: attempted, 2: partial, 3: mostly correct, 4: fully correct."}]})
        (folder / "prompt.md").write_text("Fix sum.mjs so sum(a, b) adds its arguments. Read AGENTS.md, fix the implementation, then run node test.mjs to verify it. Keep the tests unchanged.\n")
    config = {
        "argv": [shutil.which("node"), str(ROOT / "adapters" / "claude.mjs"), "--prompt", "{prompt}", "--workspace", "{workspace}", "--output", "{output}", "--model", "{task}", "--max-turns", "8", "--max-budget-usd", "1", "--timeout-seconds", "150", "--tools", "Read,Edit,Write,Bash,Glob,Grep"],
        "timeout_seconds": 165,
    }
    run, attempts = asyncio.run(run_tasks(root, tasks, config, len(tasks)))
    results = []
    for task, attempt in zip(tasks, attempts):
        model = task["id"]
        folder = run / model
        success = attempt.get("candidate", {}).get("status") == "completed" and attempt.get("capture", {}).get("status") == "completed"
        report = read_json(folder / "output" / "result.json") if (folder / "output" / "result.json").exists() else {}
        if success:
            submission = folder / "submission"
            test = subprocess.run([shutil.which("node"), "--input-type=module", "-e", "import assert from 'node:assert/strict'; import {sum} from './sum.mjs'; assert.equal(sum(2,3),5); assert.equal(sum(-2,3),1);"], cwd=submission, capture_output=True)
            success = test.returncode == 0 and b"+" in (folder / "candidate.patch").read_bytes()
            original = root / "tasks" / model / "source" / "test.mjs"
            success = success and digest(submission / "test.mjs") == digest(original)
        results.append({"requested_model": model, "resolved_model": report.get("resolved_model"), "passed": success, "sdk_version": report.get("sdk_version"), "authentication": report.get("authentication"), "num_turns": report.get("num_turns"), "estimated_cost_usd": report.get("total_cost_usd"), "attempt": str(folder)})
    evaluation = None
    if all(row["passed"] for row in results):
        judge = {**config, "argv": [*config["argv"], "--evaluator"]}
        judge["argv"][judge["argv"].index("--max-turns") + 1] = "16"
        evaluation = asyncio.run(evaluate_tasks(root, run, tasks[:1], judge, 1))
    summary = {"purpose": "Live SDK authentication, coding tools, parallel runner, submission capture, and evaluator JSON smoke check. These are not benchmark scores.", "passed": all(row["passed"] for row in results) and bool(evaluation and evaluation["complete"]), "results": results, "evaluation": evaluation}
    write_json(root / "summary.json", summary)
    print(root / "summary.json")
    for row in results:
        print(f"{row['requested_model']}: {'PASS' if row['passed'] else 'FAIL'} ({row['resolved_model']})")
    print(f"Evaluator handoff: {'PASS' if evaluation and evaluation['complete'] else 'FAIL'}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
