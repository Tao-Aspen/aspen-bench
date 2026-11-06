import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def git(directory, *args, binary=False):
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.autocrlf=false", *args],
        cwd=directory, env=environment, capture_output=True, check=True,
    )
    return result.stdout if binary else result.stdout.decode().strip()


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def selected_tasks(root, identifiers):
    tasks = read_json(root / "catalog.json")["tasks"]
    lookup = {task["id"]: task for task in tasks}
    lookup.update({str(index + 1): task for index, task in enumerate(tasks)})
    result = []
    for identifier in identifiers:
        task = lookup.get(identifier)
        if task is None:
            raise ValueError(f"Unknown task: {identifier}")
        if task["status"] != "ready":
            raise ValueError(f"{task['id']} is planned, not implemented yet")
        if task not in result:
            result.append(task)
    if not result:
        raise ValueError("Select at least one task")
    return result
