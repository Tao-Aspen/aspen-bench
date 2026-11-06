import fcntl
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import git, read_json
from .snapshots import file_manifest, prepare, verify


def validate_inputs(root, source, tasks):
    if sys.version_info < (3, 12):
        raise ValueError("Bootstrap requires Python 3.12 or newer")
    manifest = read_json(root / "dataset" / "manifest.json")
    if manifest["version"] != 1:
        raise ValueError("Unsupported dataset manifest version")
    instructions = root / "dataset" / "instructions"
    if file_manifest(instructions) != manifest["instructions"]:
        raise ValueError("Packaged instruction files differ from dataset/manifest.json")
    try:
        if git(source, "rev-parse", "--is-shallow-repository") == "true":
            raise ValueError("AspenAI history is shallow. Fetch its complete history before bootstrapping")
        commits = {read_json(root / "catalog.json")["source_commit"]}
        for task in tasks:
            folder = root / "tasks" / task["id"]
            lock = read_json(folder / "source.json")
            expected = manifest["tasks"][task["id"]]
            if lock["reference_commit"] != expected["reference_commit"]:
                raise ValueError(f"Reference pin changed for {task['id']}")
            commits.update([lock["base_commit"], lock["reference_commit"]])
            commits.update(entry["commit"] for entry in read_json(folder / "ledger.json")["commits"])
        for commit in sorted(commits):
            git(source, "cat-file", "-e", commit + "^{commit}")
    except subprocess.CalledProcessError as exception:
        raise ValueError("The source must be an AspenAI Git checkout containing the pinned main history. Fetch main and retry; bootstrap never fetches from the network or changes your checkout.\n" + exception.stderr.decode().strip()) from exception
    return manifest


def verify_pins(root, tasks, manifest):
    for task in tasks:
        snapshot = read_json(root / "tasks" / task["id"] / "snapshot.json")
        for key, expected in manifest["tasks"][task["id"]].items():
            if snapshot[key] != expected:
                raise ValueError(f"Rebuilt {key} differs from the original benchmark: {task['id']}")


def task_outputs(root, identifier):
    return [
        root / "tasks" / identifier / "baseline.bundle",
        root / "tasks" / identifier / "snapshot.json",
        root / "private" / "references" / identifier,
        root / "workspaces" / identifier,
    ]


def bootstrap(root, source, tasks):
    root = Path(root).resolve()
    source = Path(source).expanduser().resolve()
    manifest = validate_inputs(root, source, tasks)
    private = root / "private"
    private.mkdir(exist_ok=True)
    with (private / "bootstrap.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exception:
            raise ValueError("Another bootstrap is running for this benchmark") from exception
        return build_missing(root, source, tasks, manifest)


def build_missing(root, source, tasks, manifest):
    existing = []
    missing = []
    for task in tasks:
        outputs = task_outputs(root, task["id"])
        present = [path.exists() or path.is_symlink() for path in outputs]
        if any(present) and not all(present):
            paths = "\n".join(str(path) for path, exists in zip(outputs, present) if exists)
            raise ValueError(f"Incomplete existing snapshot for {task['id']}. Move these generated outputs aside and retry; no files were overwritten:\n{paths}")
        (existing if all(present) else missing).append(task)
    instructions = root / "private" / "instructions"
    if instructions.exists() and file_manifest(instructions) != manifest["instructions"]:
        raise ValueError("Existing private/instructions differ from the packaged instruction snapshot")
    if existing:
        if not instructions.exists():
            raise ValueError("Existing snapshots are missing private/instructions; restore it from dataset/instructions")
        verify_pins(root, existing, manifest)
        verify(root, existing)
        for task in existing:
            print(f"Already built and verified: {task['id']}", flush=True)
    if not missing:
        return
    with tempfile.TemporaryDirectory(prefix=".bootstrap-", dir=root) as temporary:
        stage = Path(temporary)
        shutil.copy2(root / "catalog.json", stage / "catalog.json")
        shutil.copytree(root / "dataset" / "instructions", stage / "private" / "instructions")
        for task in missing:
            folder = stage / "tasks" / task["id"]
            folder.mkdir(parents=True)
            for name in ("source.json", "ledger.json"):
                shutil.copy2(root / "tasks" / task["id"] / name, folder / name)
        history = root / "private" / "history.git"
        if history.exists():
            expected = read_json(root / "catalog.json")["source_commit"]
            if git(history, "rev-parse", "main") != expected:
                raise ValueError("Existing private/history.git does not match catalog.json")
            (stage / "private" / "history.git").symlink_to(history, target_is_directory=True)
        prepare(stage, source, missing)
        verify_pins(stage, missing, manifest)
        verify(stage, missing)
        if not instructions.exists():
            (stage / "private" / "instructions").rename(instructions)
        if not history.exists():
            (stage / "private" / "history.git").rename(history)
        for task in missing:
            for staged, destination in zip(task_outputs(stage, task["id"]), task_outputs(root, task["id"])):
                destination.parent.mkdir(parents=True, exist_ok=True)
                staged.rename(destination)
            print(f"Built and verified: {task['id']}", flush=True)
