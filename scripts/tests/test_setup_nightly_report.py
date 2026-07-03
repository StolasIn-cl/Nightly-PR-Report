import os
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETUP_SCRIPT = os.path.join(REPO_ROOT, "scripts", "setup_nightly_report.py")
SKILL_TEMPLATE = os.path.join(REPO_ROOT, "SKILL.md")


def run_git(args, cwd):
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def create_test_workspace(tmpdir):
    workspace = os.path.join(tmpdir, "Nightly-PR-Report")
    scripts_dir = os.path.join(workspace, "scripts")
    os.makedirs(scripts_dir)
    shutil.copy2(SETUP_SCRIPT, os.path.join(scripts_dir, "setup_nightly_report.py"))
    shutil.copy2(SKILL_TEMPLATE, os.path.join(workspace, "SKILL.md"))

    remote_repo = os.path.join(tmpdir, "remote.git")
    source_repo = os.path.join(tmpdir, "source")
    os.makedirs(source_repo)

    run_git(["init", "--bare", remote_repo], cwd=tmpdir)
    run_git(["init"], cwd=source_repo)
    run_git(["config", "user.name", "Test User"], cwd=source_repo)
    run_git(["config", "user.email", "test@example.com"], cwd=source_repo)

    with open(os.path.join(source_repo, "seed.txt"), "w", encoding="utf-8") as file:
        file.write("seed\n")

    run_git(["add", "seed.txt"], cwd=source_repo)
    run_git(["commit", "-m", "seed"], cwd=source_repo)
    run_git(["branch", "data/test-mapping"], cwd=source_repo)
    run_git(["remote", "add", "origin", remote_repo], cwd=source_repo)
    run_git(["push", "origin", "data/test-mapping"], cwd=source_repo)
    return workspace, scripts_dir, remote_repo


class SetupNightlyReportTests(unittest.TestCase):
    def test_setup_script_renders_local_skill_and_preserves_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace, scripts_dir, remote_repo = create_test_workspace(tmpdir)
            with open(os.path.join(workspace, "SKILL.md"), encoding="utf-8") as file:
                template_before = file.read()

            report_email = "nightly@example.com"
            result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(scripts_dir, "setup_nightly_report.py"),
                    "--remote-url",
                    remote_repo,
                    "--git-name",
                    "Test User",
                    "--git-email",
                    "test@example.com",
                    "--report-email",
                    report_email,
                ],
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            local_skill_path = os.path.join(workspace, "SKILL.local.md")
            self.assertTrue(os.path.exists(local_skill_path), "setup should create SKILL.local.md")
            self.assertIn("[OK] Wrote local skill file", result.stdout)

            with open(os.path.join(workspace, "SKILL.md"), encoding="utf-8") as file:
                template_after = file.read()
            self.assertEqual(template_after, template_before, "template SKILL.md should remain unchanged")
            self.assertIn("{{REPORT_EMAIL}}", template_after)
            self.assertIn("{{NR_DIR_WINDOWS}}", template_after)

            with open(local_skill_path, encoding="utf-8") as file:
                local_skill_text = file.read()
            self.assertIn(report_email, local_skill_text)
            self.assertNotIn("{{REPORT_EMAIL}}", local_skill_text)
            self.assertIn(workspace, local_skill_text)
            self.assertIn(os.path.join(workspace, "nightly-report.pdf"), local_skill_text)

    def test_setup_script_runs_under_cp950_console_encoding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace, scripts_dir, remote_repo = create_test_workspace(tmpdir)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "cp950"
            report_email = "nightly@example.com"

            result = subprocess.run(
                [
                    sys.executable,
                    os.path.join(scripts_dir, "setup_nightly_report.py"),
                    "--remote-url",
                    remote_repo,
                    "--git-name",
                    "Test User",
                    "--git-email",
                    "test@example.com",
                    "--report-email",
                    report_email,
                ],
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="cp950",
                errors="replace",
                env=env,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"setup script should succeed under cp950.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}",
            )
            self.assertTrue(os.path.isdir(os.path.join(workspace, ".git")))
            self.assertTrue(os.path.exists(os.path.join(workspace, "SKILL.local.md")))


if __name__ == "__main__":
    unittest.main()
