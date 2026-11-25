import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import get_nightly_report_data as fetcher


def published_status():
    return {
        'operation': 'full',
        'run': {'taipei_date': '2026-11-06', 'workflow_run_id': '123',
                'workflow_run_attempt': '1'},
        'publish': {'state': 'published', 'published_at': '2026-11-07T10:30:00Z'},
        'coverage': {'complete': False},
        'alerts': [{'reason': 'test_failures'}],
    }


class RebuildStatusTests(unittest.TestCase):
    def test_friday_without_status_stops(self):
        with self.assertRaisesRegex(ValueError, 'rebuild'):
            fetcher.validate_rebuild_status(None, '2026-11-06')

    def test_friday_requires_matching_full_published_run(self):
        for section, key, value in [
            ('run', 'taipei_date', '2026-10-30'),
            (None, 'operation', 'daily'),
            ('publish', 'state', 'failed'),
            ('publish', 'published_at', ''),
            ('publish', 'published_at', 'invalid'),
            ('run', 'workflow_run_id', ''),
            ('run', 'workflow_run_attempt', ''),
        ]:
            with self.subTest(key=key, value=value):
                status = copy.deepcopy(published_status())
                (status[section] if section else status)[key] = value
                with self.assertRaises(ValueError):
                    fetcher.validate_rebuild_status(status, '2026-11-06')

    def test_malformed_status_stops(self):
        for status in [[], {}, {'run': []}, {'publish': 'published'}]:
            with self.subTest(status=status), self.assertRaises(ValueError):
                fetcher.validate_rebuild_status(status, '2026-11-06')

    def test_published_failures_and_incomplete_coverage_are_reportable(self):
        fetcher.validate_rebuild_status(published_status(), '2026-11-06')

    def test_weekday_remains_compatible_without_status(self):
        fetcher.validate_rebuild_status(None, '2026-11-09')
