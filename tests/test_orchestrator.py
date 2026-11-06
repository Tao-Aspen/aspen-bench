import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from aspen_bench.common import digest, git, read_json, selected_tasks, write_json
from aspen_bench.evaluation import validate_judgment
from aspen_bench.processes import execute, expand, load_command
from aspen_bench.runner import parallel, run_tasks
from aspen_bench.snapshots import capture_submission, clone_bundle, file_manifest


class TemporaryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def repository(self, name="source"):
        repo = self.root / name
        repo.mkdir()
        git(repo, "init", "--quiet", "--initial-branch=main")
        git(repo, "config", "user.name", "Test")
        git(repo, "config", "user.email", "test@localhost")
        (repo / "tracked.txt").write_text("before\n")
        (repo / "delete.txt").write_text("remove this\n")
        (repo / ".gitignore").write_text("node_modules/\nhidden.txt\n")
        git(repo, "add", ".")
        git(repo, "commit", "--quiet", "-m", "Initial")
        return repo

    def bundle(self):
        repo = self.repository()
        bundle = self.root / "baseline.bundle"
        git(repo, "bundle", "create", str(bundle), "main")
        return repo, bundle


class SnapshotTests(TemporaryTest):
    def test_bundle_has_no_future_history_or_remote(self):
        source, bundle = self.bundle()
        (source / "answer.txt").write_text("private solution")
        git(source, "add", ".")
        git(source, "commit", "--quiet", "-m", "Future")
        future = git(source, "rev-parse", "HEAD")
        clone = self.root / "candidate"
        clone_bundle(bundle, clone)
        self.assertEqual(git(clone, "remote"), "")
        self.assertFalse((clone / "answer.txt").exists())
        self.assertNotEqual(subprocess.run(["git", "-C", str(clone), "cat-file", "-e", future], capture_output=True).returncode, 0)
        self.assertFalse((clone / ".git/objects/info/alternates").exists())

    def test_capture_includes_committed_untracked_ignored_and_deleted_source(self):
        _, bundle = self.bundle()
        workspace = self.root / "workspace"
        clone_bundle(bundle, workspace)
        (workspace / "tracked.txt").write_text("committed\n")
        git(workspace, "add", ".")
        git(workspace, "commit", "--quiet", "-m", "Candidate edit")
        (workspace / "new.cs").write_text("new source")
        (workspace / "hidden.txt").write_text("cannot hide source with gitignore")
        (workspace / "delete.txt").unlink()
        (workspace / "node_modules").mkdir()
        (workspace / "node_modules/output").write_text("generated")
        submission = self.root / "submission"
        patch, capture = capture_submission(bundle, workspace, submission)
        self.assertIn(b"committed", patch)
        self.assertIn(b"new.cs", patch)
        self.assertIn(b"hidden.txt", patch)
        self.assertIn(b"deleted file mode", patch)
        self.assertFalse((submission / "node_modules").exists())
        self.assertEqual(capture["excluded_artifact_directories"], [".git", "node_modules"])
        self.assertEqual(git(submission, "status", "--porcelain"), "")

    def test_capture_does_not_trust_candidate_git_directory(self):
        _, bundle = self.bundle()
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / "new.cs").write_text("source without any git directory")
        patch, _ = capture_submission(bundle, workspace, self.root / "submission")
        self.assertIn(b"new.cs", patch)
        self.assertIn(b"deleted file mode", patch)

    def test_capture_preserves_symlinks_without_reading_their_targets(self):
        _, bundle = self.bundle()
        workspace = self.root / "workspace"
        clone_bundle(bundle, workspace)
        (workspace / "link").symlink_to("missing-target")
        patch, _ = capture_submission(bundle, workspace, self.root / "submission")
        self.assertIn(b"120000", patch)
        self.assertTrue((self.root / "submission/link").is_symlink())


class ConfigurationTests(TemporaryTest):
    def test_expansion_is_one_pass_and_does_not_interpret_shell_text(self):
        values = dict(prompt="a b;$(echo x)", prompt_text="literal {task}", workspace="work", output="out", task="task", run_id="run")
        self.assertEqual(expand("{prompt}", values), "a b;$(echo x)")
        self.assertEqual(expand("{prompt_text}", values), "literal {task}")
        self.assertEqual(expand('{"custom":true}', values), '{"custom":true}')

    def test_invalid_command_is_rejected(self):
        for config in [{"argv": []}, {"argv": "shell string"}, {"argv": ["echo"], "timeout_seconds": 0}, {"argv": ["echo"], "env": {"A": 1}}]:
            path = self.root / "config.json"
            write_json(path, config)
            with self.assertRaises(ValueError):
                load_command(path)

    def test_planned_or_unknown_tasks_are_rejected_and_duplicates_collapsed(self):
        write_json(self.root / "catalog.json", {"tasks": [{"id": "one", "status": "ready"}, {"id": "two", "status": "planned"}]})
        self.assertEqual(len(selected_tasks(self.root, ["1", "one"])), 1)
        for selected in [["2"], ["missing"], []]:
            with self.assertRaises(ValueError):
                selected_tasks(self.root, selected)


class JudgmentTests(unittest.TestCase):
    def setUp(self):
        self.rubric = {"criteria": [{"id": "a", "weight": 60}, {"id": "b", "weight": 40}]}
        self.judgment = {"summary": "Assessment", "criteria": [{"id": "a", "level": 3, "rationale": "Evidence", "verification": "tested", "evidence": ["candidate/file:1"]}, {"id": "b", "level": 2, "rationale": "Gap", "verification": "inspected", "evidence": ["candidate/file:2"]}]}

    def test_score_is_computed_from_levels_not_model_total(self):
        self.judgment["score"] = 100
        self.assertEqual(validate_judgment(self.judgment, self.rubric)["score"], 65)

    def test_missing_duplicate_unknown_and_noninteger_levels_fail(self):
        changes = [lambda j: j["criteria"].pop(), lambda j: j["criteria"].append(j["criteria"][0]), lambda j: j["criteria"][0].update(id="unknown"), lambda j: j["criteria"][0].update(level=True), lambda j: j["criteria"][0].update(level=3.5)]
        for change in changes:
            value = json.loads(json.dumps(self.judgment))
            change(value)
            with self.assertRaises(ValueError):
                validate_judgment(value, self.rubric)

    def test_evidence_required_and_blocked_cannot_receive_full_credit(self):
        self.judgment["criteria"][0]["evidence"] = []
        with self.assertRaises(ValueError):
            validate_judgment(self.judgment, self.rubric)
        self.judgment["criteria"][0].update(evidence=["unavailable"], verification="blocked", level=4)
        with self.assertRaises(ValueError):
            validate_judgment(self.judgment, self.rubric)


class ProcessTests(TemporaryTest):
    def replacements(self):
        return dict(prompt=str(self.root / "prompt.md"), prompt_text="hello", workspace=str(self.root), output=str(self.root / "out.json"), task="one", run_id="test")

    def test_process_success_failure_and_missing_executable(self):
        for name, argv, expected in [("success", [sys.executable, "-c", "print('ok')"], "completed"), ("failure", [sys.executable, "-c", "raise SystemExit(7)"], "failed"), ("missing", [str(self.root / "no-executable")], "launch_failed")]:
            result = asyncio.run(execute({"argv": argv}, self.replacements(), self.root, self.root / name))
            self.assertEqual(result["status"], expected)

    def test_timeout_terminates_spawned_children(self):
        marker = self.root / "should-not-exist"
        child = f"import time,pathlib;time.sleep(2);pathlib.Path({str(marker)!r}).write_text('bad')"
        parent = f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',{child!r}]);time.sleep(10)"
        result = asyncio.run(execute({"argv": [sys.executable, "-c", parent], "timeout_seconds": 0.2}, self.replacements(), self.root, self.root / "timeout"))
        self.assertEqual(result["status"], "timeout")
        time.sleep(2.1)
        self.assertFalse(marker.exists())

    def test_cancellation_reaps_the_process(self):
        async def scenario():
            task = asyncio.create_task(execute({"argv": [sys.executable, "-c", "import time;time.sleep(30)"]}, self.replacements(), self.root, self.root / "cancel"))
            await asyncio.sleep(0.1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(scenario())
        self.assertEqual(read_json(self.root / "cancel/process.json")["status"], "cancelled")

    def test_parallel_limit_and_failure_isolation(self):
        active = 0
        maximum = 0

        async def worker(task):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.05)
            active -= 1
            if task["id"] == "bad":
                raise ValueError("isolated failure")
            return task

        results = asyncio.run(parallel([{"id": name} for name in ["one", "bad", "three"]], 2, worker))
        self.assertEqual(maximum, 2)
        self.assertEqual(results[1]["status"], "infrastructure_error")
        self.assertEqual(results[2]["id"], "three")


class IntegrationTests(TemporaryTest):
    def test_runner_and_evaluator_complete_real_subprocess_workflow(self):
        source = self.repository()
        tasks = [{"id": "one", "status": "ready"}, {"id": "two", "status": "ready"}]
        (self.root / "EVALUATOR.md").write_text("Review this task.")
        for task in tasks:
            folder = self.root / "tasks" / task["id"]
            folder.mkdir(parents=True)
            bundle = folder / "baseline.bundle"
            git(source, "bundle", "create", str(bundle), "main")
            (folder / "prompt.md").write_text("Make the change.")
            write_json(folder / "rubric.json", {"criteria": [{"id": "change", "weight": 100}]})
            write_json(folder / "source.json", {"task": task["id"]})
            reference = self.root / "private/references" / task["id"]
            reference.mkdir(parents=True)
            (reference / "code").mkdir()
            (reference / "code/reference.txt").write_text("Expected behavior")
            write_json(reference / "ledger.json", {"commits": []})
            write_json(folder / "snapshot.json", {"baseline_commit": git(source, "rev-parse", "HEAD"), "bundle_sha256": digest(bundle), "reference_files": file_manifest(reference)})
        candidate = {"argv": [sys.executable, "-c", "from pathlib import Path;Path('new.cs').write_text('implemented')"]}
        judge = {"argv": [sys.executable, "-c", "import json,os;from pathlib import Path;assert Path('candidate/new.cs').exists();assert Path('reference/code/reference.txt').exists();Path(os.environ['ASPEN_RESULT_FILE']).write_text(json.dumps({'summary':'Smoke test, not a model score','criteria':[{'id':'change','level':3,'rationale':'fixture','verification':'tested','evidence':['candidate/new.cs']}]}))"]}
        run, results = asyncio.run(run_tasks(self.root, tasks, candidate, 2, evaluator=judge))
        scoreboard = read_json(run / "scoreboard.json")
        self.assertTrue(scoreboard["complete"])
        self.assertEqual(scoreboard["mean_score"], 75)
        self.assertTrue(all(result["capture"]["status"] == "completed" for result in results))
        self.assertFalse((source / "new.cs").exists())


if __name__ == "__main__":
    unittest.main()
