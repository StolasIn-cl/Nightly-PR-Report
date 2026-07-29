import os
import sys
import unittest
from unittest import mock


SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)
import get_nightly_report_data as fetcher  # noqa: E402


def fake_git_show(ref, path, git_root):
    artifacts = {
        "codebase-coverage.json": '{"overall": 87.5}',
        "full-coverage-summary.json": '{"schema_version": 1}',
        "dart-failed-tests.json": '{"failed_test_count": 2}',
        "cpp-failed-tests.json": '{"failed_package_count": 1}',
        "dart-test-timings.json": '{"metadata": {"test_count": 2}}',
        "dart-test-timings-previous.json": '{"metadata": {"test_count": 1}}',
    }
    return artifacts.get(path)


class BranchArtifactTests(unittest.TestCase):
    def test_load_branch_artifacts_uses_current_names(self):
        with mock.patch.object(fetcher, "git_show", side_effect=fake_git_show) as show:
            artifacts = fetcher.load_branch_artifacts("origin/data/test-mapping", "repo")

        self.assertEqual(artifacts["full_coverage_summary"]["schema_version"], 1)
        self.assertEqual(artifacts["cpp_failed_tests"]["failed_package_count"], 1)
        self.assertEqual(artifacts["dart_test_timings"]["metadata"]["test_count"], 2)
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
