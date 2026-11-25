import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)
import get_nightly_report_data as fetcher  # noqa: E402
from test_rebuild_status import published_status


def fake_git_show(ref, path, git_root):
    artifacts = {
        "codebase-coverage.json": '{"overall": 87.5}',
        "full-coverage-summary.json": '{"schema_version": 1}',
        "dart-failed-tests.json": '{"failed_test_count": 2}',
        "cpp-failed-tests.json": '{"failed_package_count": 1}',
        "unsafe-merge-folders.json": '{"generated_at": "2026-09-07T06:04:29Z", "folders": ["lib/example"]}',
        "dart-test-timings.json": '{"metadata": {"test_count": 2}}',
        "dart-test-timings-previous.json": '{"metadata": {"test_count": 1}}',
        "quality-metrics-history.json": '{"schema_version": 1, "entries": []}',
    }
    return artifacts.get(path)


class BranchArtifactTests(unittest.TestCase):
    def run_fetch(self, root, day, status):
        def fake_git(args, cwd, capture=True):
            result = root if args == ['rev-parse', '--show-toplevel'] else 'a' * 40 if args == ['rev-parse', '--verify', 'FETCH_HEAD^{commit}'] else ''
            return subprocess.CompletedProcess(args, 0, str(result), '')

        def show(ref, path, cwd):
            self.assertEqual(ref, 'a' * 40, 'All artifacts must use the pinned fetched commit')
            return json.dumps(status) if path == 'rebuild-status.json' else None

        with mock.patch.object(sys, 'argv', ['fetch', '--date', day, '--out', str(Path(root) / 'out.json')]), mock.patch.object(fetcher, 'git', side_effect=fake_git), mock.patch.object(fetcher, 'git_show', side_effect=show):
            fetcher.main()

    def test_friday_unpublished_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'out.json'
            output.write_text('previous output')
            with self.assertRaises(SystemExit) as stopped:
                self.run_fetch(root, '2026-11-06', None)
            self.assertNotEqual(stopped.exception.code, 0)
            self.assertEqual(output.read_text(), 'previous output')

    def test_published_friday_fetch_includes_status_and_pinned_commit(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_fetch(root, '2026-11-06', published_status())
            data = json.loads((Path(root) / 'out.json').read_text())
            self.assertEqual(data['rebuild_status'], published_status())
            self.assertEqual(data['data_commit'], 'a' * 40)

    def test_fetch_failure_raises_instead_of_using_stale_remote_ref(self):
        failed = subprocess.CompletedProcess(
            args=["git", "fetch"],
            returncode=128,
            stdout="",
            stderr="network unavailable",
        )
        with mock.patch.object(fetcher, "git", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "network unavailable"):
                fetcher.fetch_data_branch("data/test-mapping", "repo")

    def test_load_branch_artifacts_uses_current_names(self):
        with mock.patch.object(fetcher, "git_show", side_effect=fake_git_show) as show:
            artifacts = fetcher.load_branch_artifacts("origin/data/test-mapping", "repo")

        self.assertEqual(artifacts["full_coverage_summary"]["schema_version"], 1)
        self.assertEqual(artifacts["cpp_failed_tests"]["failed_package_count"], 1)
        self.assertEqual(artifacts["unsafe_merge_folders"]["folders"], ["lib/example"])
        self.assertEqual(artifacts["dart_test_timings"]["metadata"]["test_count"], 2)
        self.assertEqual(artifacts["quality_metrics_history"]["schema_version"], 1)
        requested = [call.args[1] for call in show.call_args_list]
        self.assertNotIn("rebuild-failed-tests.json", requested)
        self.assertNotIn("cpp-coverage-failures.json", requested)
        self.assertNotIn("test-timings.json", requested)

    def test_load_branch_artifacts_returns_none_for_missing_optional_artifact(self):
        with mock.patch.object(fetcher, "git_show", return_value=None):
            artifacts = fetcher.load_branch_artifacts("origin/data/test-mapping", "repo")

        self.assertIsNone(artifacts["full_coverage_summary"])


if __name__ == "__main__":
    unittest.main()
