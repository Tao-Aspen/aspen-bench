import shutil
import tempfile
import unittest
from pathlib import Path

from aspen_bench.bootstrap import bootstrap
from aspen_bench.common import digest, git, read_json, write_json
from aspen_bench.snapshots import file_manifest


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "AspenAI with spaces"
        self.source.mkdir()
        git(self.source, "init", "--quiet", "--initial-branch=main")
        git(self.source, "config", "user.name", "Test")
        git(self.source, "config", "user.email", "test@localhost")
        (self.source / "AGENTS.md").write_text("Repository instructions\n")
        (self.source / "unrelated.txt").write_text("Full repository context\n")
        git(self.source, "add", ".")
        git(self.source, "commit", "--quiet", "-m", "Before project")
        self.base = git(self.source, "rev-parse", "HEAD")
        self.base_tree = git(self.source, "rev-parse", "HEAD^{tree}")
        (self.source / "solution.txt").write_text("Merged implementation\n")
        git(self.source, "add", ".")
        git(self.source, "commit", "--quiet", "-m", "Completed project")
        self.reference = git(self.source, "rev-parse", "HEAD")
        self.root = self.directory / "benchmark"
        self.instructions = self.root / "dataset" / "instructions"
        self.instructions.mkdir(parents=True)
        shutil.copy2(self.source / "AGENTS.md", self.instructions / "AGENTS.md")
        self.tasks = [{"id": "one", "status": "ready"}, {"id": "two", "status": "ready"}]
        write_json(self.root / "catalog.json", {"source_commit": self.reference, "tasks": self.tasks})
        manifest = {"version": 1, "instructions": file_manifest(self.instructions), "tasks": {}}
        for task in self.tasks:
            folder = self.root / "tasks" / task["id"]
            write_json(folder / "source.json", {"base_commit": self.base, "reference_commit": self.reference})
            write_json(folder / "ledger.json", {"commits": [{"commit": self.reference, "pr": 1}]})
            manifest["tasks"][task["id"]] = {
                "baseline_tree": self.base_tree,
                "reference_commit": self.reference,
                "reference_tree": git(self.source, "rev-parse", "HEAD^{tree}"),
                "instruction_sha256": {"AGENTS.md": digest(self.instructions / "AGENTS.md")},
            }
        write_json(self.root / "dataset" / "manifest.json", manifest)

    def tearDown(self):
        self.temporary.cleanup()

    def test_fresh_build_rerun_and_incremental_tasks_preserve_source_and_workspaces(self):
        (self.source / "AGENTS.md").write_text("New local instructions must not affect the frozen dataset\n")
        source_status = git(self.source, "status", "--porcelain")
        bootstrap(self.root, self.source, self.tasks[:1])
        bundle = self.root / "tasks/one/baseline.bundle"
        checksum = digest(bundle)
        workspace = self.root / "workspaces/one"
        self.assertTrue((workspace / "unrelated.txt").exists())
        self.assertFalse((workspace / "solution.txt").exists())
        self.assertEqual((workspace / "AGENTS.md").read_text(), "Repository instructions\n")
        (workspace / "unrelated.txt").write_text("Inspection edits must survive reruns\n")
        bootstrap(self.root, self.source, self.tasks)
        self.assertEqual(digest(bundle), checksum)
        self.assertEqual((workspace / "unrelated.txt").read_text(), "Inspection edits must survive reruns\n")
        self.assertTrue((self.root / "tasks/two/baseline.bundle").exists())
        self.assertEqual(git(self.source, "status", "--porcelain"), source_status)
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), self.reference)
        self.assertEqual(list(self.root.glob(".bootstrap-*")), [])

    def test_packaged_instruction_changes_fail_before_generating_artifacts(self):
        (self.instructions / "AGENTS.md").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Packaged instruction"):
            bootstrap(self.root, self.source, self.tasks)
        self.assertFalse((self.root / "private").exists())

    def test_missing_history_has_actionable_error_and_no_generated_artifacts(self):
        catalog = read_json(self.root / "catalog.json")
        catalog["source_commit"] = "a" * 40
        write_json(self.root / "catalog.json", catalog)
        with self.assertRaisesRegex(ValueError, "Fetch main and retry"):
            bootstrap(self.root, self.source, self.tasks)
        self.assertFalse((self.root / "private").exists())

    def test_shallow_source_is_rejected(self):
        shallow = self.directory / "shallow"
        git(self.directory, "clone", "--depth=1", self.source.as_uri(), str(shallow))
        with self.assertRaisesRegex(ValueError, "history is shallow"):
            bootstrap(self.root, shallow, self.tasks)

    def test_failed_pin_verification_leaves_no_published_artifacts(self):
        manifest = read_json(self.root / "dataset/manifest.json")
        manifest["tasks"]["one"]["baseline_tree"] = "a" * 40
        write_json(self.root / "dataset/manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "baseline_tree differs"):
            bootstrap(self.root, self.source, self.tasks[:1])
        self.assertFalse((self.root / "tasks/one/baseline.bundle").exists())
        self.assertFalse((self.root / "private/history.git").exists())
        self.assertFalse((self.root / "workspaces").exists())
        self.assertEqual(list(self.root.glob(".bootstrap-*")), [])

    def test_partial_existing_outputs_are_not_overwritten(self):
        bundle = self.root / "tasks/one/baseline.bundle"
        bundle.write_text("keep existing output")
        with self.assertRaisesRegex(ValueError, "Incomplete existing snapshot"):
            bootstrap(self.root, self.source, self.tasks)
        self.assertEqual(bundle.read_text(), "keep existing output")

    def test_corrupted_existing_artifacts_are_not_silently_rebuilt(self):
        bootstrap(self.root, self.source, self.tasks[:1])
        reference = self.root / "private/references/one/code/solution.txt"
        reference.write_text("changed")
        with self.assertRaisesRegex(ValueError, "Reference files changed"):
            bootstrap(self.root, self.source, self.tasks[:1])
        self.assertEqual(reference.read_text(), "changed")


if __name__ == "__main__":
    unittest.main()
