import os
import sys
import unittest


SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)
import validate_author_notes as validator  # noqa: E402


RUN_URL = "https://example.com/actions/runs/123"
TITLE = "Fix title & escaping"
FIXTURE_DATA = {
    "prs": [{
        "summary": {"run_url": RUN_URL, "title": TITLE},
        "review_markdown": "[P1] Guard the new path\n[P2] Add the regression test",
    }],
}
AUTHOR_HTML_WITH_P1 = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p><span class="priority-label priority-p1">P1</span> Guard the new path before release.</p>
  <p><span class="priority-label priority-p2">P2</span> Add the regression test.</p>
</div>
"""
TITLE_ONLY_AUTHOR_HTML = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p>This PR addresses Fix title &amp; escaping.</p>
</div>
"""
TITLE_ONLY_AUTHOR_HTML_WITH_LABELS = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p><span class="priority-label priority-p1">P1</span>
     <span class="priority-label priority-p2">P2</span>
     This PR addresses Fix title &amp; escaping.</p>
</div>
"""
AUTHOR_HTML_WITHOUT_P2 = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p><span class="priority-label priority-p1">P1</span> Guard the new path before release.</p>
</div>
"""


class ValidateAuthorNotesTests(unittest.TestCase):
    def test_accepts_review_summary_with_p1_label(self):
        self.assertEqual(validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITH_P1), [])

    def test_rejects_title_only_summary_for_reviewed_pr(self):
        self.assertIn("title-only", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, TITLE_ONLY_AUTHOR_HTML)
        ))

    def test_rejects_title_only_summary_when_it_has_required_priority_labels(self):
        self.assertIn("title-only", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, TITLE_ONLY_AUTHOR_HTML_WITH_LABELS)
        ))

    def test_rejects_missing_p2_label_for_explicit_p2_finding(self):
        self.assertIn("P2", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITHOUT_P2)
        ))

    def test_rejects_unsupported_invented_priority_label(self):
        html = """
        <div class="pr-entry"><a href="https://example.com/actions/runs/123">#123</a>
          <p><span class="priority-label priority-p1">P1</span> First finding.</p>
          <p><span class="priority-label priority-p2">P2</span> Second finding.</p>
          <p><span class="priority-label priority-p3">P3</span> Invented finding.</p>
        </div>
        """
        self.assertIn("Unsupported", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, html)
        ))

    def test_rejects_priority_label_after_prose(self):
        html = """
        <div class="pr-entry"><a href="https://example.com/actions/runs/123">#123</a>
          <p>First finding. <span class="priority-label priority-p1">P1</span></p>
          <p><span class="priority-label priority-p2">P2</span> Second finding.</p>
        </div>
        """
        self.assertIn("first meaningful content", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, html)
        ))

    def test_rejects_collapsed_same_priority_findings(self):
        data = {
            "prs": [{
                "summary": {"run_url": RUN_URL, "title": TITLE},
                "review_markdown": "[P1] First finding\n[P1] Second finding",
            }],
        }
        html = """
        <div class="pr-entry"><a href="https://example.com/actions/runs/123">#123</a>
          <p><span class="priority-label priority-p1">P1</span> Both findings.</p>
        </div>
        """
        self.assertIn("2 P1", "\n".join(
            validator.validate_author_notes(data, html)
        ))

    def test_rejects_multiple_priority_labels_in_one_paragraph(self):
        html = """
        <div class="pr-entry"><a href="https://example.com/actions/runs/123">#123</a>
          <p><span class="priority-label priority-p1">P1</span>
             <span class="priority-label priority-p2">P2</span> Both findings.</p>
        </div>
        """
        self.assertIn("multiple priority labels", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, html)
        ))

    def test_required_priorities_finds_unique_priority_labels_case_insensitively(self):
        self.assertEqual(validator.required_priorities("[p1] One\n[P2] Two\n[P1] Again"), {"P1", "P2"})

    def test_uses_run_url_to_match_duplicate_prs(self):
        data = {
            "prs": [
                {"summary": {"run_url": "https://example.com/runs/one", "title": "Same title"},
                 "review_markdown": "[P1] First finding"},
                {"summary": {"run_url": "https://example.com/runs/two", "title": "Same title"},
                 "review_markdown": "[P2] Second finding"},
            ],
        }
        html = """
        <div class="pr-entry"><a href="https://example.com/runs/one">#1</a>
          <p><span class="priority-label priority-p1">P1</span> First finding</p></div>
        <div class="pr-entry"><a href="https://example.com/runs/two">#1</a>
          <p><span class="priority-label priority-p2">P2</span> Second finding</p></div>
        """
        self.assertEqual(validator.validate_author_notes(data, html), [])


if __name__ == "__main__":
    unittest.main()
