# Review-led Author Notes Design

## Goal

Make the nightly report's Author Notes useful to developers by summarising the
code-review conclusion for each PR, while keeping the report local-only for
this run (no Outlook activity and no `run-status.json` update).

## Chosen approach

Use a subagent to produce the narrative HTML, but constrain it with an explicit
review-first prompt and validate the returned HTML before it is inserted into
the report. This retains concise natural-language summaries without allowing
the title-only fallback that caused the current issue.

Alternatives considered:

1. Prompt-only change: smallest change, but a generic subagent response can
   silently reach the PDF again.
2. Fully deterministic review parser: predictable, but it cannot reliably
   paraphrase arbitrary review prose.
3. Review-first subagent plus structural validation: selected because it
   combines meaningful summaries with a repeatable failure signal.

## Data flow

1. The existing report-data fetch output is read without modification.
2. The HTML skeleton is generated with its `AUTHOR_SUMMARY` placeholder.
3. A subagent receives the slim PR payload and produces author-card HTML.
4. The validator checks that every PR has a matching entry, that reviewed PRs
   are not title-only echoes, and that explicit P1/P2 findings carry their
   matching leading label.
5. Validated HTML replaces the placeholder and is rendered to the local PDF.
   The workflow stops before email and does not write `run-status.json`.

## Author-note content rules

- Keep every PR under its author and retain the PR link and title.
- For an explicit `[P1]` or `[P2]` finding, begin the summary with a compact
  `P1` or `P2` label only. The remaining sentence stays normal-colour prose
  and paraphrases the concrete impact from `review_markdown`.
- For a review with no actionable finding, state the reviewed behaviour or
  that no actionable regression was found, based only on the review text.
- For a null review, retain `review unavailable`.
- Do not infer security, safety, or product impact that is not explicitly
  supported by the review text.
- Do not include pass/fail/skip outcomes in Author Notes.

## Presentation

Add a small inline priority-label style. P1 uses a dark red label and P2 an
orange label; only the label is coloured. The summary text remains the existing
neutral body colour. The existing author-card layout and page-break rules stay
unchanged.

## Validation and tests

The validator will use the source JSON and generated author-note HTML. It must
reject missing PR entries, title-only fallback sentences for PRs with review
text, and missing P1/P2 labels for reviews containing those explicit findings.
Focused unit tests cover a good P1/P2 example, a reviewed no-finding example,
and each rejection case. The complete report generation is then rendered and
visually checked from the PDF pages containing Author Notes.

## Run constraints

This invocation ends after local HTML/PDF generation and verification. It must
not open Outlook, send email, attach files, or update `run-status.json`.
