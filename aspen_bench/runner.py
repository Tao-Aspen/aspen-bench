import asyncio
import datetime
import shutil
import uuid

from .common import digest, read_json, write_json
from .evaluation import evaluate_task
from .processes import execute
from .snapshots import capture_submission, clone_bundle


async def run_task(root, run, task, config, image):
    identifier = task["id"]
    attempt = run / identifier
    attempt.mkdir()
    workspace = attempt / "workspace"
    folder = root / "tasks" / identifier
    bundle = folder / "baseline.bundle"
    snapshot = read_json(folder / "snapshot.json")
    if digest(bundle) != snapshot["bundle_sha256"]:
        raise ValueError(f"Corrupt baseline for {identifier}")
    await asyncio.to_thread(clone_bundle, bundle, workspace)
    input_dir = attempt / "input"
    input_dir.mkdir()
    prompt_path = input_dir / "prompt.md"
    shutil.copy2(folder / "prompt.md", prompt_path)
    output_dir = attempt / "output"
    output_dir.mkdir()
    specification = attempt / "specification"
    specification.mkdir()
    for name in ["rubric.json", "source.json", "snapshot.json"]:
        shutil.copy2(folder / name, specification / name)
    shutil.copy2(root / "EVALUATOR.md", specification / "EVALUATOR.md")
    replacements = {"prompt": str(prompt_path), "prompt_text": prompt_path.read_text(), "workspace": str(workspace), "output": str(output_dir / "result.json"), "task": identifier, "run_id": run.name}
    state = {"task": identifier, "baseline_commit": snapshot["baseline_commit"], "bundle_sha256": snapshot["bundle_sha256"], "prompt_sha256": digest(prompt_path), "specification_sha256": {path.name: digest(path) for path in specification.iterdir()}, "candidate": {"status": "running"}}
    write_json(attempt / "attempt.json", state)
    print(f"Starting {identifier}", flush=True)
    try:
        state["candidate"] = await execute(config, replacements, workspace, attempt / "candidate-process", image)
    except asyncio.CancelledError:
        state["candidate"] = {"status": "cancelled"}
        write_json(attempt / "attempt.json", state)
        raise
    try:
        patch, capture = await asyncio.to_thread(capture_submission, bundle, workspace, attempt / "submission")
        (attempt / "candidate.patch").write_bytes(patch)
        state["capture"] = {"status": "completed", **capture, "patch_sha256": digest(attempt / "candidate.patch")}
    except Exception as exception:
        state["capture"] = {"status": "failed", "error": str(exception)}
    write_json(attempt / "attempt.json", state)
    print(f"Finished {identifier}: {state['candidate']['status']}", flush=True)
    return state


async def parallel(items, jobs, function):
    semaphore = asyncio.Semaphore(jobs)

    async def one(item):
        async with semaphore:
            try:
                return await function(item)
            except Exception as exception:
                return {"task": item["id"], "status": "infrastructure_error", "error": str(exception)}

    return await asyncio.gather(*(one(item) for item in items))


async def run_tasks(root, tasks, config, jobs, image=None, evaluator=None):
    name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    run = root / "runs" / name
    run.mkdir(parents=True)
    write_json(run / "run.json", {"id": name, "tasks": [task["id"] for task in tasks], "jobs": jobs, "isolation": "docker" if image else "local-process", "candidate_command": {"argv": config["argv"], "timeout_seconds": config.get("timeout_seconds", 7200)}, "image": image})
    print(f"Run: {run}", flush=True)
    attempts = await parallel(tasks, jobs, lambda task: run_task(root, run, task, config, image))
    write_json(run / "attempts.json", attempts)
    if evaluator:
        await evaluate_tasks(root, run, tasks, evaluator, jobs)
    return run, attempts


async def evaluate_tasks(root, run, tasks, config, jobs):
    results = await parallel(tasks, jobs, lambda task: evaluate_task(root, run, task, config))
    rows = [{"task": task["id"], **result} for task, result in zip(tasks, results)]
    scored = [row["score"] for row in rows if row.get("status") == "completed"]
    summary = {"run": str(run), "evaluated_tasks": len(scored), "selected_tasks": len(tasks), "complete": len(scored) == len(tasks), "mean_score": round(sum(scored) / len(scored), 2) if len(scored) == len(tasks) else None, "results": rows}
    write_json(run / "scoreboard.json", summary)
    return summary
