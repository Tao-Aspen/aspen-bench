import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .common import digest, git, read_json, write_json


ARTIFACT_DIRECTORIES = {".git", "node_modules", "bin", "obj", ".vs", ".idea", "__pycache__", ".pytest_cache", "TestResults", "test-results", "playwright-report", "coverage"}


def file_manifest(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            result[str(path.relative_to(directory))] = {"symlink": os.readlink(path)}
        elif path.is_file():
            result[str(path.relative_to(directory))] = {"sha256": digest(path)}
    return result


def verify_reference(root, task, snapshot):
    directory = root / "private" / "references" / task["id"]
    if file_manifest(directory) != snapshot["reference_files"]:
        raise ValueError(f"Reference files changed: {task['id']}")


def clone_bundle(bundle, destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    git(destination.parent, "clone", "--no-hardlinks", "--branch", "main", "--quiet", str(bundle), str(destination))
    git(destination, "remote", "remove", "origin")
    git(destination, "config", "user.name", "Aspen Developer")
    git(destination, "config", "user.email", "developer@localhost")
    git(destination, "config", "core.hooksPath", os.devnull)


def archive_tree(source, commit, destination):
    destination.mkdir(parents=True)
    with tempfile.TemporaryFile() as stream:
        subprocess.run(["git", "-C", str(source), "archive", commit], stdout=stream, check=True)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as archive:
            archive.extractall(destination, filter="data")


def prepare(root, source, tasks):
    source = Path(source).expanduser().resolve()
    frozen = root / "private" / "history.git"
    if not frozen.exists():
        frozen.parent.mkdir(parents=True, exist_ok=True)
        git(frozen.parent, "init", "--bare", str(frozen))
        head = read_json(root / "catalog.json")["source_commit"]
        git(frozen, "fetch", "--no-tags", source.as_uri(), head)
        git(frozen, "update-ref", "refs/heads/main", head)
        git(frozen, "symbolic-ref", "HEAD", "refs/heads/main")
    for task in tasks:
        identifier = task["id"]
        folder = root / "tasks" / identifier
        lock = read_json(folder / "source.json")
        bundle = folder / "baseline.bundle"
        reference = root / "private" / "references" / identifier
        if bundle.exists() or reference.exists():
            raise FileExistsError(f"{identifier} already has snapshot files; verify them instead of overwriting")
        print(f"Preparing {identifier}", flush=True)
        git(frozen, "merge-base", "--is-ancestor", lock["base_commit"], lock["reference_commit"])
        git(frozen, "merge-base", "--is-ancestor", lock["reference_commit"], "main")
        workspace = root / "workspaces" / identifier
        workspace.parent.mkdir(parents=True, exist_ok=True)
        if workspace.exists():
            raise FileExistsError(workspace)
        workspace.mkdir()
        git(workspace, "init", "--quiet", "--initial-branch=main")
        git(workspace, "fetch", "--quiet", "--no-tags", frozen.as_uri(), lock["base_commit"])
        git(workspace, "reset", "--hard", "FETCH_HEAD")
        instruction_root = root / "private" / "instructions"
        instruction_paths = []
        for path in instruction_root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(instruction_root)
                target = workspace / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                instruction_paths.append(str(relative))
        git(workspace, "add", "-f", "--", *instruction_paths)
        git(workspace, "-c", "user.name=Aspen Developer", "-c", "user.email=developer@localhost", "commit", "--quiet", "--allow-empty", "-m", "Apply current repository instructions")
        baseline = git(workspace, "rev-parse", "HEAD")
        git(workspace, "config", "user.name", "Aspen Developer")
        git(workspace, "config", "user.email", "developer@localhost")
        git(workspace, "config", "core.hooksPath", os.devnull)
        git(workspace, "bundle", "create", str(bundle), "main")
        archive_tree(frozen, lock["reference_commit"], reference / "code")
        patches = reference / "patches"
        patches.mkdir()
        relevant_paths = set()
        ledger = read_json(folder / "ledger.json")
        for entry in ledger["commits"]:
            commit = entry["commit"]
            git(frozen, "merge-base", "--is-ancestor", commit, lock["reference_commit"])
            paths = git(frozen, "diff", "--name-only", commit + "^1", commit).splitlines()
            entry["paths"] = paths
            relevant_paths.update(paths)
            patch = git(frozen, "diff", "--binary", "--no-ext-diff", commit + "^1", commit, binary=True)
            (patches / f"pr-{entry['pr']}.patch").write_bytes(patch)
        write_json(reference / "ledger.json", ledger)
        (reference / "relevant-paths.txt").write_text("\n".join(sorted(relevant_paths)) + "\n")
        (reference / "all-changes.stat").write_text(git(frozen, "diff", "--stat", lock["base_commit"], lock["reference_commit"]) + "\n")
        tracked = git(workspace, "ls-files", "-z", binary=True).decode().split("\0")
        files = {}
        for name in filter(None, tracked):
            path = workspace / name
            files[name] = {"sha256": digest(path) if not path.is_symlink() else None, "symlink": os.readlink(path) if path.is_symlink() else None}
        verification = {
            "baseline_commit": baseline,
            "baseline_tree": git(workspace, "rev-parse", "HEAD^{tree}"),
            "bundle_sha256": digest(bundle),
            "instruction_sha256": {name: digest(workspace / name) for name in instruction_paths},
            "files": files,
            "reference_commit": lock["reference_commit"],
            "reference_tree": git(frozen, "rev-parse", lock["reference_commit"] + "^{tree}"),
            "reference_files": file_manifest(reference),
        }
        write_json(folder / "snapshot.json", verification)
        print(f"Prepared {identifier}: {len(files)} files, {len(ledger['commits'])} scoped PRs", flush=True)


def verify(root, tasks):
    summaries = []
    for task in tasks:
        folder = root / "tasks" / task["id"]
        snapshot = read_json(folder / "snapshot.json")
        bundle = folder / "baseline.bundle"
        if digest(bundle) != snapshot["bundle_sha256"]:
            raise ValueError(f"Bundle checksum mismatch: {task['id']}")
        verify_reference(root, task, snapshot)
        with tempfile.TemporaryDirectory(prefix="aspen-verify-") as temporary:
            clone = Path(temporary) / "repo"
            clone_bundle(bundle, clone)
            if git(clone, "rev-parse", "HEAD") != snapshot["baseline_commit"]:
                raise ValueError("Baseline commit mismatch")
            if git(clone, "remote"):
                raise ValueError("Baseline has a remote")
            git(clone, "fsck", "--full", "--no-reflogs")
            for name, expected in snapshot["files"].items():
                path = clone / name
                actual = {"sha256": digest(path) if not path.is_symlink() else None, "symlink": os.readlink(path) if path.is_symlink() else None}
                if actual != expected:
                    raise ValueError(f"Baseline file mismatch: {name}")
            future = subprocess.run(["git", "-C", str(clone), "cat-file", "-e", snapshot["reference_commit"]], capture_output=True)
            if future.returncode == 0:
                raise ValueError("Reference commit leaked into baseline")
            for name, expected in snapshot["instruction_sha256"].items():
                if digest(root / "private" / "instructions" / name) != expected:
                    raise ValueError(f"Instruction snapshot mismatch: {name}")
        summaries.append({"task": task["id"], "files": len(snapshot["files"]), "verified": True})
    return summaries


def capture_submission(bundle, workspace, destination):
    clone_bundle(bundle, destination)
    tracked = set(filter(None, git(destination, "ls-files", "-z", binary=True).decode().split("\0")))
    for child in destination.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    kept = []
    ignored = []
    for directory, dirs, files in os.walk(workspace, followlinks=False):
        relative = Path(directory).relative_to(workspace)
        for name in list(dirs):
            path = relative / name
            prefix = str(path) + "/"
            contains_tracked = any(item.startswith(prefix) for item in tracked)
            excluded = name == ".git" or (name in ARTIFACT_DIRECTORIES and not contains_tracked)
            if excluded:
                dirs.remove(name)
                ignored.append(str(path))
            elif (workspace / path).is_symlink():
                dirs.remove(name)
                files.append(name)
        for name in files:
            path = relative / name
            if path.parts[0] == ".git":
                continue
            source = workspace / path
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)
            kept.append(str(path))
    git(destination, "add", "-A", "-f", "--", ".")
    patch = git(destination, "diff", "--cached", "--binary", "--no-ext-diff", "HEAD", binary=True)
    git(destination, "commit", "--quiet", "--allow-empty", "-m", "Capture submitted source tree")
    return patch, {"files": len(kept), "excluded_artifact_directories": sorted(ignored), "commit": git(destination, "rev-parse", "HEAD"), "tree": git(destination, "rev-parse", "HEAD^{tree}")}
