import argparse
import asyncio
import json
import shlex
import subprocess
from pathlib import Path

from .common import ROOT, read_json, selected_tasks
from .bootstrap import bootstrap
from .processes import load_command
from .runner import evaluate_tasks, run_tasks
from .snapshots import prepare, verify


def positive_integer(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("Must be at least 1")
    return result


def command_config(path, command, timeout):
    if path:
        return load_command(path)
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Command must not be empty")
    return {"argv": argv, "timeout_seconds": timeout}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Aspen coding tasks in parallel and evaluate their source changes against frozen merged implementations.")
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    build = commands.add_parser("bootstrap", help="Rebuild heavy artifacts from a local AspenAI checkout using the packaged dataset inputs")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--tasks", nargs="+", default=["1", "2", "3"])
    freeze = commands.add_parser("prepare", help="Create frozen full-repository baselines and private references")
    freeze.add_argument("--source", type=Path, required=True)
    freeze.add_argument("--tasks", nargs="+", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--tasks", nargs="+", required=True)
    run = commands.add_parser("run")
    run.add_argument("--tasks", nargs="+", required=True)
    candidate = run.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-config", type=Path)
    candidate.add_argument("--candidate-command", help="Command parsed into argv without a shell; use {prompt} for the prompt document path")
    evaluator = run.add_mutually_exclusive_group()
    evaluator.add_argument("--evaluator-config", type=Path)
    evaluator.add_argument("--evaluator-command")
    run.add_argument("--candidate-timeout", type=positive_integer, default=7200)
    run.add_argument("--evaluator-timeout", type=positive_integer, default=3600)
    run.add_argument("--jobs", type=positive_integer, default=3)
    run.add_argument("--candidate-image", help="Run each candidate in this Docker image with only its own workspace, prompt, and output mounted")
    judge = commands.add_parser("evaluate")
    judge.add_argument("--run", type=Path, required=True)
    judge.add_argument("--tasks", nargs="+", required=True)
    evaluator = judge.add_mutually_exclusive_group(required=True)
    evaluator.add_argument("--evaluator-config", type=Path)
    evaluator.add_argument("--evaluator-command")
    judge.add_argument("--evaluator-timeout", type=positive_integer, default=3600)
    judge.add_argument("--jobs", type=positive_integer, default=3)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.command == "list":
            for task in read_json(root / "catalog.json")["tasks"]:
                print(f"{task['id']:28} {task['status']:8} {task['title']}")
            return 0
        tasks = selected_tasks(root, args.tasks)
        if args.command == "bootstrap":
            bootstrap(root, args.source, tasks)
        elif args.command == "prepare":
            prepare(root, args.source, tasks)
        elif args.command == "verify":
            print(json.dumps(verify(root, tasks), indent=2))
        elif args.command == "run":
            config = command_config(args.candidate_config, args.candidate_command, args.candidate_timeout)
            evaluator = command_config(args.evaluator_config, args.evaluator_command, args.evaluator_timeout) if args.evaluator_config or args.evaluator_command else None
            run_path, attempts = asyncio.run(run_tasks(root, tasks, config, args.jobs, args.candidate_image, evaluator))
            print(run_path)
            failed = any(item.get("candidate", {}).get("status") != "completed" or item.get("capture", {}).get("status") != "completed" for item in attempts)
            if evaluator:
                failed = failed or not read_json(run_path / "scoreboard.json")["complete"]
            return 1 if failed else 0
        elif args.command == "evaluate":
            run_path = args.run.expanduser().resolve()
            selected = read_json(run_path / "run.json")["tasks"]
            if any(task["id"] not in selected for task in tasks):
                raise ValueError("Selected task was not part of this run")
            config = command_config(args.evaluator_config, args.evaluator_command, args.evaluator_timeout)
            result = asyncio.run(evaluate_tasks(root, run_path, tasks, config, args.jobs))
            print(json.dumps(result, indent=2))
            return 0 if result["complete"] else 1
        return 0
    except (ValueError, OSError) as exception:
        parser.exit(2, f"Error: {exception}\n")
    except subprocess.CalledProcessError as exception:
        parser.exit(2, f"Git operation failed: {exception.stderr.decode().strip()}\n")
    except KeyboardInterrupt:
        return 130
