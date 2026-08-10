# Dart Coverage Delta grouping

## Goal

Make file-level Dart coverage changes scannable by splitting the existing mixed
table into outcome-based groups, matching the presentation of Nightly Rebuild
Timing.

## Behaviour

`build_coverage_delta_section` will keep its existing section header and total
coverage summary. It will classify file entries into these non-empty groups:

1. **New**: entries without a previous line-coverage percentage.
2. **Coverage Increased**: entries with a positive percentage-point delta.
3. **Coverage Decreased**: entries with a negative percentage-point delta.

Entries with a zero delta are omitted. Empty groups are not rendered.

## Ordering and presentation

- New files retain their source order unless an existing stable path order is
  already provided by the data.
- Increased and decreased groups sort by absolute delta descending, so the
  largest changes appear first.
- Each group uses the current file/previous/current/delta table columns and
  applies the existing row cap independently, including its `+N more` note.
- New uses the existing neutral or blue visual treatment; increased uses green;
  decreased uses red.

## Error handling

The section remains absent when coverage-delta data is unavailable. If there
are no New, Increased, or Decreased entries, it renders the current no-change
message rather than an empty section.

## Tests

Add focused tests for grouping, sorting, empty-group suppression, zero-delta
omission, and per-group row caps. The rendering test asserts the group labels
and expected files appear in the generated HTML.
