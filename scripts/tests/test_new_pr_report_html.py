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
            "metadata": {"rebuild_cpu_seconds": 10000},
            "test_timings": {
                "test/a_test.dart": 100.0,
                "test/b_test.dart": 50.0,
                "test/c_test.dart": 30.0,
                "test/removed_test.dart": 40.0,
            },
        }
        self.current = {
            "metadata": {"rebuild_cpu_seconds": 10720},
            "test_timings": {
                "test/a_test.dart": 100.0,        # unchanged -> excluded
                "test/b_test.dart": 50.0 + 20.01,  # +20.01s -> slower
                "test/c_test.dart": 30.0 - 25.0,   # -25s -> faster
                "test/new_test.dart": 5.0,         # no baseline -> excluded
            },
        }

    def test_legacy_wall_seconds_metadata_still_renders(self):
        current = {"metadata": {"rebuild_wall_seconds": 600}, "test_timings": {}}
        previous = {"metadata": {"rebuild_wall_seconds": 480}, "test_timings": {}}
        html = rpt.build_timing_section(current, previous)
        self.assertIn("Nightly Rebuild Timing", html)
        self.assertIn("+2m 00s", html)

    def test_missing_previous_returns_empty(self):
        self.assertEqual(rpt.build_timing_section(self.current, None), "")

    def test_missing_current_returns_empty(self):
        self.assertEqual(rpt.build_timing_section(None, self.previous), "")

    def test_exact_20_second_delta_excluded(self):
        current = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {"test/x_test.dart": 40.0}}
        previous = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {"test/x_test.dart": 20.0}}
        html = rpt.build_timing_section(current, previous)
        self.assertNotIn("x_test.dart", html)

    def test_20_01_second_delta_included(self):
        current = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {"test/x_test.dart": 40.01}}
        previous = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {"test/x_test.dart": 20.0}}
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
        current = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {}}
        previous = {"metadata": {"rebuild_cpu_seconds": 100}, "test_timings": {}}
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


class CoverageDeltaSectionTests(unittest.TestCase):
    def test_groups_new_increased_and_decreased_and_omits_unchanged(self):
        html = rpt.build_coverage_delta_section({
            "total": {"current_line_pct": 70, "delta_line_pct": 1},
            "files": [
                {"path": "lib/new.dart", "status": "new", "previous_pct": None,
                 "current_pct": 60, "delta_pct": None},
                {"path": "lib/small_gain.dart", "previous_pct": 70,
                 "current_pct": 71, "delta_pct": 1},
                {"path": "lib/large_gain.dart", "previous_pct": 40,
                 "current_pct": 50, "delta_pct": 10},
                {"path": "lib/loss.dart", "previous_pct": 90,
                 "current_pct": 80, "delta_pct": -10},
                {"path": "lib/unchanged.dart", "previous_pct": 50,
                 "current_pct": 50, "delta_pct": 0},
            ],
        })

        self.assertIn("New &mdash; 1 file(s)", html)
        self.assertIn("Coverage Increased &mdash; 2 file(s)", html)
        self.assertIn("Coverage Decreased &mdash; 1 file(s)", html)
        self.assertLess(html.index("large_gain.dart"), html.index("small_gain.dart"))
        self.assertNotIn("unchanged.dart", html)

    def test_caps_each_group_independently(self):
        files = [
            {"path": f"lib/gain_{index}.dart", "previous_pct": 0,
             "current_pct": index + 1, "delta_pct": index + 1}
            for index in range(rpt.COVERAGE_DELTA_ROW_CAP + 1)
        ]
        files.append({"path": "lib/loss.dart", "previous_pct": 100,
                      "current_pct": 99, "delta_pct": -1})

        html = rpt.build_coverage_delta_section({"files": files})

        self.assertIn("Coverage Increased &mdash; 31 file(s)", html)
        self.assertIn("Coverage Decreased &mdash; 1 file(s)", html)
        self.assertIn("+1 more", html)
        self.assertIn("loss.dart", html)


class QualityMetricsHistorySectionTests(unittest.TestCase):
    def setUp(self):
        self.history = {
            "schema_version": 1,
            "entries": [
                {
                    "date": "2026-08-12",
                    "dart_coverage": {"status": "measured", "percent": 20.86},
                    "test_file_count": 1464,
                    "test_case_count": 13268,
                },
                {
                    "date": "2026-08-13",
                    "dart_coverage": {"status": "measured", "percent": 22.32},
                    "test_file_count": 1537,
                    "test_case_count": 13679,
                },
            ],
        }

    def test_renders_three_labeled_sparklines_with_current_values(self):
        html = rpt.build_quality_metrics_history_section(self.history)

        self.assertIn("Quality Metrics History", html)
        self.assertEqual(html.count("<svg"), 3)
        self.assertIn("Dart coverage (%)", html)
        self.assertIn("*_test.dart files", html)
        self.assertIn("Test cases", html)
        self.assertIn("22.32%", html)
        self.assertIn("1,537", html)
        self.assertIn("13,679", html)

    def test_omits_section_when_no_entries_exist(self):
        self.assertEqual(rpt.build_quality_metrics_history_section({"entries": []}), "")

    def test_renders_three_taller_cards_with_x_axis_dates_and_deltas(self):
        html = rpt.build_quality_metrics_history_section(self.history)

        self.assertIn("display:flex;gap:10px", html)
        self.assertEqual(html.count("<svg"), 3)
        self.assertEqual(html.count("data-quality-x-label"), 6)
        self.assertIn("vs previous: +1.46pp", html)
        self.assertIn("vs previous: +73", html)
        self.assertIn("vs previous: +411", html)
        self.assertIn("height='180'", html)
        self.assertNotIn("2026-08-12 &rarr; 2026-08-13", html)
        self.assertEqual(html.count("2026-08-12"), 3)

    def test_renders_compact_axes_for_each_metric_chart(self):
        html = rpt.build_quality_metrics_history_section(self.history)

        self.assertEqual(html.count("data-quality-y-tick"), 15)
        self.assertEqual(html.count("data-quality-x-tick"), 6)
        self.assertEqual(html.count("data-quality-y-minor"), 45)
        self.assertEqual(html.count("data-quality-x-minor"), 12)
        self.assertEqual(html.count("data-quality-point"), 6)


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


class ReportLayoutTests(unittest.TestCase):
    def render_report_with_full_coverage(self):
        data = {
            "date": "2026-07-27",
            "generated_at": "2026-07-27T00:00:00Z",
            "prs": [{
                "summary": {
                    "pr_number": 123,
                    "run_url": "https://example.com/runs/123",
                    "author": "report-author",
                    "title": "Coverage layout regression fixture",
                    "outcome": "pass",
                    "selected_test_count": 5,
                    "dart_diff_coverage": None,
                    "cpp_diff_coverage": None,
                    "total_ms": 1000,
                },
            }],
            "pr_count": 1,
            "codebase_coverage": {
                "line_pct": 13.86,
                "line_hit": 40318,
                "line_total": 290815,
            },
            "full_coverage_summary": {
                "complete": False,
                "dart": {
                    "status": "measured",
                    "percent": 64.12,
                    "covered_lines": 8298,
                    "eligible_source_lines": 12942,
                },
                "cpp": {
                    "status": "measured",
                    "measurement_complete": False,
                    "percent": 2.02,
                    "covered_lines": 811,
                    "eligible_source_lines": 40196,
                },
                "combined": {
                    "status": "incomplete",
                    "percent": None,
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
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            with open(out_path, encoding="utf-8") as f:
                return f.read()

    def test_full_report_places_coverage_before_pr_table_and_omits_header_coverage(self):
        html = self.render_report_with_full_coverage()

        self.assertLess(html.index("<!-- Native coverage -->"), html.index("Pull Requests"))
        self.assertNotIn("Coverage <strong", html)
        self.assertNotIn("40318/290815 lines", html)

    def test_report_styles_priority_labels_without_coloring_note_bodies(self):
        report_html = self.render_report_with_full_coverage()

        self.assertIn(".priority-label", report_html)
        self.assertIn(".priority-p1", report_html)
        self.assertIn(".priority-p2", report_html)


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
                "metadata": {"rebuild_cpu_seconds": 10720},
                "test_timings": {
                    # Malformed: a string instead of a number. This makes
                    # `curr - prev` inside _timing_rows raise TypeError.
                    "test/a_test.dart": "not-a-number",
                },
            },
            "dart_test_timings_previous": {
                "metadata": {"rebuild_cpu_seconds": 10000},
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
