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
  <p>Guard the new path before release. <span class="priority-label priority-p1">P1</span>
     <span class="priority-label priority-p2">P2</span></p>
</div>
"""
TITLE_ONLY_AUTHOR_HTML = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p>This PR addresses Fix title &amp; escaping.</p>
</div>
"""
AUTHOR_HTML_WITHOUT_P2 = """
<div class="pr-entry">
  <div class="pr-link"><a href="https://example.com/actions/runs/123">#123</a></div>
  <p>Guard the new path before release. <span class="priority-label priority-p1">P1</span></p>
</div>
"""


class ValidateAuthorNotesTests(unittest.TestCase):
    def test_accepts_review_summary_with_p1_label(self):
        self.assertEqual(validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITH_P1), [])

    def test_rejects_title_only_summary_for_reviewed_pr(self):
        self.assertIn("title-only", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, TITLE_ONLY_AUTHOR_HTML)
        ))

    def test_rejects_missing_p2_label_for_explicit_p2_finding(self):
        self.assertIn("P2", "\n".join(
            validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITHOUT_P2)
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
          <p>First finding <span class="priority-label priority-p1">P1</span></p></div>
        <div class="pr-entry"><a href="https://example.com/runs/two">#1</a>
          <p>Second finding <span class="priority-label priority-p2">P2</span></p></div>
        """
        self.assertEqual(validator.validate_author_notes(data, html), [])


if __name__ == "__main__":
    unittest.main()
