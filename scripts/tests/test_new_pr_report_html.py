import importlib.util
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
