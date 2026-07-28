import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)
import new_pr_report_html as rpt  # noqa: E402


class DurationFormattingTests(unittest.TestCase):
    def test_fmt_duration_hours(self):
        self.assertEqual(rpt.fmt_duration(3 * 3600 + 7 * 60), "3h 07m")

    def test_fmt_duration_minutes(self):
        self.assertEqual(rpt.fmt_duration(12 * 60), "12m 00s")

    def test_fmt_duration_seconds(self):
        self.assertEqual(rpt.fmt_duration(45), "45s")

    def test_fmt_duration_delta_positive(self):
        self.assertEqual(rpt.fmt_duration_delta(720), "+12m 00s")

    def test_fmt_duration_delta_negative(self):
        self.assertEqual(rpt.fmt_duration_delta(-45), "-45s")


class TimingSectionTests(unittest.TestCase):
    def setUp(self):
        self.previous = {
            "metadata": {"rebuild_wall_seconds": 10000},
            "test_timings": {
                "test/a_test.dart": 100.0,
                "test/b_test.dart": 50.0,
                "test/c_test.dart": 30.0,
                "test/removed_test.dart": 40.0,
            },
        }
        self.current = {
            "metadata": {"rebuild_wall_seconds": 10720},
            "test_timings": {
                "test/a_test.dart": 100.0,        # unchanged -> excluded
                "test/b_test.dart": 50.0 + 20.01,  # +20.01s -> slower
                "test/c_test.dart": 30.0 - 25.0,   # -25s -> faster
                "test/new_test.dart": 5.0,         # no baseline -> excluded
            },
        }

    def test_missing_previous_returns_empty(self):
        self.assertEqual(rpt.build_timing_section(self.current, None), "")

    def test_missing_current_returns_empty(self):
        self.assertEqual(rpt.build_timing_section(None, self.previous), "")

    def test_exact_20_second_delta_excluded(self):
        current = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {"test/x_test.dart": 40.0}}
        previous = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {"test/x_test.dart": 20.0}}
        html = rpt.build_timing_section(current, previous)
        self.assertNotIn("x_test.dart", html)

    def test_20_01_second_delta_included(self):
        current = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {"test/x_test.dart": 40.01}}
        previous = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {"test/x_test.dart": 20.0}}
        html = rpt.build_timing_section(current, previous)
        self.assertIn("x_test.dart", html)

    def test_new_and_removed_tests_excluded(self):
        html = rpt.build_timing_section(self.current, self.previous)
        self.assertNotIn("new_test.dart", html)
        self.assertNotIn("removed_test.dart", html)

    def test_slower_and_faster_grouped_separately(self):
        html = rpt.build_timing_section(self.current, self.previous)
        self.assertIn("b_test.dart", html)     # slower
        self.assertIn("c_test.dart", html)     # faster
        self.assertNotIn("a_test.dart", html)  # unchanged, excluded

        slower_idx = html.index("Slower")
        faster_idx = html.index("Faster")
        b_idx = html.index("b_test.dart")
        c_idx = html.index("c_test.dart")
        self.assertTrue(slower_idx < b_idx < faster_idx < c_idx)

    def test_total_time_delta_shown(self):
        html = rpt.build_timing_section(self.current, self.previous)
        self.assertIn("+12m", html)  # 10720 - 10000 = 720s = 12m

    def test_row_cap_shows_more_indicator(self):
        current = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {}}
        previous = {"metadata": {"rebuild_wall_seconds": 100}, "test_timings": {}}
        for i in range(35):
            key = f"test/slow_{i}_test.dart"
            previous["test_timings"][key] = 10.0
            current["test_timings"][key] = 10.0 + 25.0 + i
        html = rpt.build_timing_section(current, previous)
        self.assertIn("+5 more", html)  # 35 rows, cap 30 -> 5 more


class CoverageSectionTests(unittest.TestCase):
    def test_coverage_section_shows_measured_dart_and_incomplete_cpp(self):
        html = rpt.build_coverage_section({
            "complete": False,
            "dart": {"status": "measured", "percent": 64.12,
                     "covered_lines": 8298, "eligible_source_lines": 12942},
            "cpp": {"status": "measured", "measurement_complete": False,
                    "percent": 2.02, "covered_lines": 811,
                    "eligible_source_lines": 40196},
            "combined": {"status": "incomplete", "percent": None},
        })
        self.assertIn("Dart", html)
        self.assertIn("64.12%", html)
        self.assertIn("C++", html)
        self.assertIn("incomplete", html)
        self.assertNotIn("0%", html)


class CppFailureSectionTests(unittest.TestCase):
    def test_cpp_failures_show_package_and_reason_without_author(self):
        html = rpt.build_cpp_failures_section({
            "failed_package_count": 1,
            "failures": [{"package_name": "ai_generator",
                          "reason": "test executable is missing"}],
        })
        self.assertIn("ai_generator", html)
        self.assertIn("test executable is missing", html)
        self.assertNotIn("Author", html)


class MalformedTimingDataDoesNotCrashReportTests(unittest.TestCase):
    """End-to-end guard for the final-review finding: a non-numeric value in
    the upstream test-timings data must not crash the whole nightly report
    (PR table, coverage, etc.) -- only the timing section should be omitted.
    """

    def test_non_numeric_test_timing_does_not_crash_main(self):
        data = {
            "date": "2026-07-03",
            "generated_at": "2026-07-03T00:00:00Z",
            "prs": [],
            "pr_count": 0,
            "dart_test_timings": {
                "metadata": {"rebuild_wall_seconds": 10720},
                "test_timings": {
                    # Malformed: a string instead of a number. This makes
                    # `curr - prev` inside _timing_rows raise TypeError.
                    "test/a_test.dart": "not-a-number",
                },
            },
            "dart_test_timings_previous": {
                "metadata": {"rebuild_wall_seconds": 10000},
                "test_timings": {
                    "test/a_test.dart": 100.0,
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "nightly-report-data.json")
            out_path = os.path.join(tmpdir, "nightly-report.html")
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            script_path = os.path.join(SCRIPTS_DIR, "new_pr_report_html.py")
            result = subprocess.run(
                [sys.executable, script_path, "--data", data_path, "--out", out_path],
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode, 0,
                msg=f"script crashed instead of degrading gracefully.\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertTrue(os.path.exists(out_path), "report HTML was not produced")
            self.assertIn("build_timing_section failed", result.stderr)

            with open(out_path, encoding="utf-8") as f:
                html_out = f.read()
            self.assertIn("<html", html_out)


if __name__ == "__main__":
    unittest.main()
