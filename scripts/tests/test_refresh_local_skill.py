import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import refresh_local_skill as refresher


class RefreshLocalSkillTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name) / "Nightly-PR-Report"
        self.repo.mkdir()
        self.template = self.repo / "SKILL.md"
        self.template.write_text(
            "root={{NR_DIR_WINDOWS}}\n"
            "script={{SCRIPT_SOURCE_WINDOWS}}\n"
            "recipients={{RECIPIENTS_PATH_WINDOWS}}\n"
            "pdf={{PDF_PATH_WINDOWS}}\n",
            encoding="utf-8",
        )
        (self.repo / "recipients.json").write_text(
            json.dumps({"recipients": ["nightly@example.com"]}), encoding="utf-8"
        )
        (self.repo / "SKILL.local.md").write_text("previous local skill\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def local_text(self):
        return (self.repo / "SKILL.local.md").read_text(encoding="utf-8")

    def test_refresh_renders_all_tokens_and_writes_hashes(self):
        source_hash, local_hash = refresher.render_local_skill(self.repo)
        self.assertEqual(len(source_hash), 64)
        self.assertEqual(len(local_hash), 64)
        self.assertEqual(source_hash, hashlib.sha256(self.template.read_bytes()).hexdigest())
        self.assertEqual(
            local_hash,
            hashlib.sha256((self.repo / "SKILL.local.md").read_bytes()).hexdigest(),
        )
        self.assertNotIn("{{NR_DIR_WINDOWS}}", self.local_text())
        self.assertNotIn("{{SCRIPT_SOURCE_WINDOWS}}", self.local_text())
        self.assertNotIn("{{RECIPIENTS_PATH_WINDOWS}}", self.local_text())
        self.assertNotIn("{{PDF_PATH_WINDOWS}}", self.local_text())
        self.assertIn(str(self.repo.resolve()), self.local_text())

    def test_missing_recipients_preserves_existing_local_skill(self):
        previous = self.local_text()
        (self.repo / "recipients.json").unlink()
        with self.assertRaises(refresher.RefreshError):
            refresher.render_local_skill(self.repo)
        self.assertEqual(self.local_text(), previous)

    def test_unresolved_token_preserves_existing_local_skill(self):
        self.template.write_text("{{UNKNOWN_TOKEN}}", encoding="utf-8")
        with self.assertRaises(refresher.RefreshError):
            refresher.render_local_skill(self.repo)
        self.assertEqual(self.local_text(), "previous local skill\n")

    def test_cli_prints_hashes_after_refresh(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "refresh_local_skill.py"), "--repo-dir", str(self.repo)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Source SHA-256: ", result.stdout)
        self.assertIn("Local SHA-256: ", result.stdout)

    def test_cli_failure_keeps_existing_local_skill(self):
        (self.repo / "SKILL.md").unlink()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "refresh_local_skill.py"), "--repo-dir", str(self.repo)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.local_text(), "previous local skill\n")

    def test_template_requires_refresh_then_continue_at_step_one(self):
        template = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("refresh_local_skill.py", template)
        self.assertIn("continue at Step 1", template)


if __name__ == "__main__":
    unittest.main()
