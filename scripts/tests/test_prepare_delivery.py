import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import prepare_delivery as m


class PrepareDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'recipients.json').write_text(json.dumps({'recipients':['rd@example.com']}))
        self.data = {'date':'2026-11-09', 'pr_count':1, 'prs':[{'summary':{'outcome':'pass'}}]}
        (self.root / 'nightly-report-data.json').write_text(json.dumps(self.data))
        self.pdf = self.root / 'PR-Daily-Report-2026-11-09.pdf'
        self.pdf.write_bytes(b'%PDF-1.7\n'+b'x'*1200)

    def tearDown(self): self.temp.cleanup()

    def test_stale_data_stops(self):
        with self.assertRaises(ValueError): m.preflight(self.root, '2026-11-10')

    def test_preserves_project_subject_body_recipients(self):
        result = m.build_manifest(self.root, '2026-11-09', self.pdf, 'stolas_in@cyberlink.com')
        self.assertEqual(result['subject'], 'PR Daily Report — 2026-11-09 (1 PRs, 0 failed)')
        self.assertIn('✅ 1 passed', result['body'])
        self.assertEqual(result['recipients'], ['rd@example.com'])
        self.assertEqual(result['attachments'][0]['filename'], self.pdf.name)

    def test_zero_pr_has_explicit_no_attachment(self):
        self.data.update(pr_count=0, prs=[])
        (self.root / 'nightly-report-data.json').write_text(json.dumps(self.data))
        result = m.build_manifest(self.root, '2026-11-09', None, 'stolas_in@cyberlink.com')
        self.assertEqual(result['subject'], 'No PR activity today — 2026-11-09')
        self.assertEqual(result['attachments'], [])
        self.assertEqual(result['no_attachment_reason'], 'no_pr_activity')

    def test_missing_pdf_and_count_mismatch_stop(self):
        with self.assertRaises(ValueError): m.build_manifest(self.root, '2026-11-09', None, 'stolas_in@cyberlink.com')
        self.data['pr_count']=3
        (self.root / 'nightly-report-data.json').write_text(json.dumps(self.data))
        with self.assertRaises(ValueError): m.preflight(self.root, '2026-11-09')

    def test_delayed_receipt_sync_uses_snapshot_counts_after_next_fetch(self):
        manifest = m.build_manifest(self.root, '2026-11-09', self.pdf, 'stolas_in@cyberlink.com')
        job = dict(id='receipt', status='sent', email_sent=True, manifest=manifest,
            evidence={'kind':'sent_items'})
        class FakeStore:
            def get(self, job_id): return job
        self.data.update(date='2026-11-10', pr_count=0, prs=[])
        (self.root / 'nightly-report-data.json').write_text(json.dumps(self.data))
        result = m.sync(self.root, '2026-11-09', FakeStore(), 'stolas_in@cyberlink.com')
        self.assertEqual(result['pr_count'], 1)
        self.assertEqual(result['pass_count'], 1)


if __name__ == '__main__': unittest.main()
