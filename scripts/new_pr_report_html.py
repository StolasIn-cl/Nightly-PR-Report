#!/usr/bin/env python3
"""
new_pr_report_html.py  (v3 — PDF-first design)
Generate a polished HTML report from nightly-report-data.json.
Designed for weasyprint PDF output (landscape A4, modern CSS).
The per-author summary section is left as <!-- AUTHOR_SUMMARY --> for LLM fill-in.

Usage:
    python3 new_pr_report_html.py [--data FILE] [--out FILE]
"""

import argparse
import html as htmllib
import json
import os
import subprocess
import sys


# ── Helpers ──────────────────────────────────────────────────────────────────

def esc(s):
    return htmllib.escape(str(s)) if s else ""


def fmt_ms(ms):
    if ms is None:
        return "—"
    s = int(float(ms) / 1000)
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s"


def fmt_duration(seconds):
    """Format a non-negative duration in seconds as '3h 07m' / '12m 00s' / '45s'."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_duration_delta(seconds):
    """Format a signed duration delta in seconds as '+12m 00s' / '-45s'."""
    sign = "+" if seconds >= 0 else "-"
    return f"{sign}{fmt_duration(abs(seconds))}"


def fmt_test_seconds(seconds):
    """Format a single test's own duration in seconds as '12.3s'."""
    return f"{seconds:.1f}s"


TIMING_ROW_CAP = 30


def _timing_rows(current_timings, previous_timings, direction):
    """Rows (path, prev, curr, delta) where |delta| > 20s, filtered to
    direction='slower' (delta > 0) or direction='faster' (delta < 0), sorted
    by |delta| descending. Tests missing from either snapshot are skipped."""
    rows = []
    for path, curr in current_timings.items():
        prev = previous_timings.get(path)
        if prev is None:
            continue
        delta = curr - prev
        if abs(delta) <= 20:
            continue
        if direction == "slower" and delta > 0:
            rows.append((path, prev, curr, delta))
        elif direction == "faster" and delta < 0:
            rows.append((path, prev, curr, delta))
    rows.sort(key=lambda r: abs(r[3]), reverse=True)
    return rows


def _timing_table(rows, header_bg):
    TH = (
        f"padding:9px 11px;background:{header_bg};color:#fff;text-align:left;"
        "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;"
        "white-space:nowrap;"
    )
    TD = "padding:8px 11px;border-bottom:1px solid #f1f3f4;vertical-align:top;font-size:12px;"
    shown = rows[:TIMING_ROW_CAP]
    trs = []
    for i, (path, prev, curr, delta) in enumerate(shown):
        row_bg = "#fafafa" if i % 2 == 0 else "#ffffff"
        delta_color = "#c62828" if delta > 0 else "#2e7d32"
        trs.append(
            f"<tr style='background:{row_bg}'>"
            f"<td style='{TD}font-family:monospace;font-size:11px'>{esc(path)}</td>"
            f"<td style='{TD}text-align:right'>{fmt_test_seconds(prev)}</td>"
            f"<td style='{TD}text-align:right'>{fmt_test_seconds(curr)}</td>"
            f"<td style='{TD}text-align:right;color:{delta_color};font-weight:700'>"
            f"{fmt_duration_delta(delta)}</td>"
            f"</tr>"
        )
    table = (
        f"<table style='border-collapse:collapse;width:100%;font-family:inherit'>"
        f"<thead><tr>"
        f"<th style='{TH}'>Test File</th>"
        f"<th style='{TH}width:90px;text-align:right'>Previous</th>"
        f"<th style='{TH}width:90px;text-align:right'>Current</th>"
        f"<th style='{TH}width:80px;text-align:right'>Delta</th>"
        f"</tr></thead>"
        f"<tbody>{''.join(trs)}</tbody>"
        f"</table>"
    )
    if len(rows) > TIMING_ROW_CAP:
        table += (
            f"<div style='font-size:10px;color:#9e9e9e;font-style:italic;"
            f"padding:6px 11px'>+{len(rows) - TIMING_ROW_CAP} more</div>"
        )
    return table


def build_timing_section(current, previous):
    """Return the Nightly Rebuild Timing HTML block, or '' if either snapshot
    is missing (e.g. the first night after this feature is rolled out)."""
    if not current or not previous:
        return ""

    curr_timings = current.get("test_timings") or {}
    prev_timings = previous.get("test_timings") or {}

    curr_wall = (current.get("metadata") or {}).get("rebuild_wall_seconds")
    prev_wall = (previous.get("metadata") or {}).get("rebuild_wall_seconds")
    wall_html = ""
    if curr_wall is not None and prev_wall is not None:
        wall_html = (
            f"{fmt_duration(curr_wall)}"
            f" <span style='color:#9e9e9e;font-weight:400'>"
            f"(vs last: {fmt_duration_delta(curr_wall - prev_wall)})</span>"
        )

    slower_rows = _timing_rows(curr_timings, prev_timings, "slower")
    faster_rows = _timing_rows(curr_timings, prev_timings, "faster")

    if not slower_rows and not faster_rows and not wall_html:
        return ""

    slower_html = ""
    if slower_rows:
        slower_html = (
            f"<div style='margin-bottom:14px'>"
            f"<div class=\"section-label\" style=\"color:#c62828;padding-left:0;"
            f"border-bottom:none\">&#9650; Slower &mdash; {len(slower_rows)} test(s)</div>"
            f"{_timing_table(slower_rows, '#c62828')}"
            f"</div>"
        )
    faster_html = ""
    if faster_rows:
        faster_html = (
            f"<div>"
            f"<div class=\"section-label\" style=\"color:#2e7d32;padding-left:0;"
            f"border-bottom:none\">&#9660; Faster &mdash; {len(faster_rows)} test(s)</div>"
            f"{_timing_table(faster_rows, '#2e7d32')}"
            f"</div>"
        )

    header = "Nightly Rebuild Timing"
    if wall_html:
        header += f" &mdash; {wall_html}"

    return (
        f"\n  <!-- Timing changes -->\n"
        f"  <div class=\"section\" style=\"margin-top:14px;border-radius:8px\">\n"
        f"    <div class=\"section-label\">{header}</div>\n"
        f"    <div style=\"padding:12px 16px\">\n"
        f"      {slower_html}\n"
        f"      {faster_html}\n"
        f"    </div>\n"
        f"  </div>"
    )


def fmt_cov(cov, failed_step, outcome):
    if cov is None:
        return "<span style='color:#bdbdbd'>—</span>"
    if cov.get("num_lines", 0) == 0:
        return "<span style='color:#9e9e9e;font-style:italic'>—</span>"
    pct   = round(cov.get("percent", 0), 1)
    color = "#2e7d32" if pct >= 80 else ("#e65100" if pct >= 50 else "#c62828")
    bg    = "#e8f5e9" if pct >= 80 else ("#fff3e0" if pct >= 50 else "#ffebee")
    return (
        f"<span style='background:{bg};color:{color};border-radius:4px;"
        f"padding:2px 8px;font-size:11px;font-weight:700'>"
        f"{pct}%</span>"
    )


def outcome_badge(outcome):
    # Use HTML entities (&#10003; = ✓, &#10007; = ✗, &#8213; = ―) instead of
    # colour emoji so weasyprint renders them without a colour emoji font.
    if outcome == "pass":
        return "&#10003; pass",  "#e8f5e9", "#2e7d32"
    if outcome == "fail":
        return "&#10007; fail",  "#ffebee", "#c62828"
    if outcome == "skipped":
        return "&#8213; skip",   "#f5f5f5", "#757575"
    return esc(outcome) or "?", "#ffffff", "#9e9e9e"


def outcome_accent(outcome):
    if outcome == "pass":    return "#2e7d32"
    if outcome == "fail":    return "#c62828"
    if outcome == "skipped": return "#9e9e9e"
    return "#bdbdbd"


def build_rebuild_section(rft):
    """Return the Nightly Rebuild Failures HTML block, or '' if no data."""
    if not rft:
        return ""
    failed_count = rft.get("failed_count", len(rft.get("failed_tests") or []))
    if not failed_count or not rft.get("failed_tests"):
        return ""

    gen_at   = rft.get("generated_at", "")
    date_str = f" (as of {esc(gen_at[:10])})" if gen_at else ""

    TH_R = (
        "padding:9px 11px;background:#c62828;color:#fff;text-align:left;"
        "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;"
        "white-space:nowrap;"
    )
    TD_R = "padding:8px 11px;border-bottom:1px solid #f1f3f4;vertical-align:top;font-size:12px;"

    rows = []
    for i, t in enumerate(rft["failed_tests"]):
        author_obj  = t.get("author") or {}
        # Strip Windows domain prefix (CLT\ or CLT/)
        raw_name    = author_obj.get("name") or ""
        author_name = raw_name.split("\\")[-1].split("/")[-1] if ("\\" in raw_name or "/" in raw_name) else raw_name
        sha         = author_obj.get("sha") or ""
        short_sha   = sha[:7] if sha else "—"
        path        = t.get("path", "")
        row_bg      = "#fff8f8" if i % 2 == 0 else "#fafafa"
        rows.append(
            f"<tr style='background:{row_bg}'>"
            f"<td style='{TD_R}font-family:monospace;font-size:11px'>{esc(path)}</td>"
            f"<td style='{TD_R}'>{esc(author_name)}</td>"
            f"<td style='{TD_R}font-family:monospace;font-size:11px;color:#757575'>{esc(short_sha)}</td>"
            f"</tr>"
        )

    table = (
        f"<table style='border-collapse:collapse;width:100%;font-family:inherit'>"
        f"<thead><tr>"
        f"<th style='{TH_R}'>Test File</th>"
        f"<th style='{TH_R}width:130px'>Last Author</th>"
        f"<th style='{TH_R}width:64px'>Commit</th>"
        f"</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table>"
    )

    return (
        f"\n  <!-- Rebuild failures -->\n"
        f"  <div class=\"section rebuild-section\">\n"
        f"    <div class=\"section-label\" style=\"color:#c62828\">"
        f"&#9888; Nightly Rebuild Failures &mdash; {failed_count} test(s){date_str}</div>\n"
        f"    {table}\n"
        f"  </div>"
    )


def fmt_failed_tests(failed_tests):
    if not failed_tests:
        return ""
    chips = []
    for t in failed_tests[:5]:
        label = t.get("label", "")
        parts = label.replace("\\", "/").rstrip("/").split("/")
        # Show last 3 path segments so the filename is identifiable
        short = "/".join(parts[-3:]) if len(parts) >= 3 else label
        chips.append(
            f"<div style='background:#fff0f0;"
            f"border:1px solid #ffcdd2;border-radius:3px;padding:2px 6px;"
            f"font-size:10px;font-family:monospace;margin:2px 0;"
            f"word-break:break-all;overflow-wrap:anywhere;"
            f"color:#b71c1c' title='{esc(label)}'>{esc(short)}</div>"
        )
    if len(failed_tests) > 5:
        chips.append(
            f"<div style='font-size:10px;color:#9e9e9e;font-style:italic;margin-top:2px'>"
            f"+{len(failed_tests) - 5} more</div>"
        )
    return "".join(chips)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="", help="Path to nightly-report-data.json")
    parser.add_argument("--out",  default="", help="Output HTML path")
    args = parser.parse_args()

    if args.data and args.out:
        data_file = args.data
        out_file  = args.out
    else:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, cwd=os.getcwd())
        if r.returncode != 0:
            print("Not inside a git repository.", file=sys.stderr)
            sys.exit(1)
        git_root = r.stdout.strip()
        data_file = args.data or os.path.join(git_root, "coverage", "nightly-report-data.json")
        out_file  = args.out  or os.path.join(git_root, "coverage", "nightly-report.html")

    if not os.path.exists(data_file):
        print(f"Data file not found: {data_file}", file=sys.stderr)
        sys.exit(1)

    with open(data_file, "rb") as f:
        raw = f.read().rstrip(b'\x00')
    data = json.loads(raw.decode("utf-8"))

    date      = data.get("date", "")
    prs       = data.get("prs", [])
    pr_count  = data.get("pr_count", len(prs))

    pass_count  = sum(1 for p in prs if (p.get("summary") or {}).get("outcome") == "pass")
    fail_count  = sum(1 for p in prs if (p.get("summary") or {}).get("outcome") == "fail")
    skip_count  = sum(1 for p in prs if (p.get("summary") or {}).get("outcome") == "skipped")
    total_tests = sum((p.get("summary") or {}).get("selected_test_count") or 0 for p in prs)

    cc      = data.get("codebase_coverage")
    cov_pct = round(cc.get("line_pct", 0), 2) if cc else None

    # ── Stats pills ──────────────────────────────────────────────────────────

    pills_html = ""
    if pass_count:
        pills_html += (
            f"<span style='background:rgba(255,255,255,.18);color:#fff;"
            f"border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;"
            f"margin-right:6px'>&#10003; {pass_count} passed</span>"
        )
    if fail_count:
        pills_html += (
            f"<span style='background:#c62828;color:#fff;"
            f"border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;"
            f"margin-right:6px'>&#10007; {fail_count} failed</span>"
        )
    if skip_count:
        pills_html += (
            f"<span style='background:rgba(255,255,255,.12);color:rgba(255,255,255,.75);"
            f"border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;"
            f"margin-right:6px'>&#8213; {skip_count} skipped</span>"
        )
    if total_tests:
        pills_html += (
            f"<span style='background:rgba(255,255,255,.12);color:rgba(255,255,255,.75);"
            f"border-radius:20px;padding:3px 12px;font-size:12px;font-weight:700;"
            f"margin-right:6px'>&#9654; {total_tests} tests selected</span>"
        )

    cov_html = ""
    if cov_pct is not None:
        cov_bar_color = "#4caf50" if cov_pct >= 80 else ("#ff9800" if cov_pct >= 50 else "#f44336")
        cov_html = (
            f"<span style='color:rgba(255,255,255,.65);font-size:12px;margin-left:8px'>"
            f"· Coverage <strong style='color:#fff'>{cov_pct}%</strong>"
            f" ({cc.get('line_hit','?')}/{cc.get('line_total','?')} lines)</span>"
        )

    # ── PR rows ──────────────────────────────────────────────────────────────

    TH = (
        "padding:9px 11px;background:#1e88e5;color:#fff;text-align:left;"
        "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;"
        "white-space:nowrap;"
    )
    TD      = "padding:8px 11px;border-bottom:1px solid #f1f3f4;vertical-align:top;font-size:12px;"
    TD_NB   = TD + "white-space:nowrap;"
    TD_TITL = TD + "max-width:280px;word-break:break-word;line-height:1.4;"
    TD_FAIL = TD + "min-width:160px;max-width:220px;word-break:break-all;overflow-wrap:anywhere;white-space:normal;"

    rows = []
    for i, pr in enumerate(prs):
        s           = pr.get("summary") or {}
        pr_num      = s.get("pr_number")
        run_url     = s.get("run_url", "")
        outcome     = s.get("outcome", "")
        failed_step = s.get("failed_step")
        accent      = outcome_accent(outcome)
        row_bg      = "#fafbfc" if i % 2 == 1 else "#ffffff"

        pr_link = (
            f"<a href='{esc(run_url)}' style='color:#1565c0;font-weight:700;"
            f"text-decoration:none'>#{pr_num}</a>"
            if pr_num and run_url else "—"
        )

        badge_html, badge_bg, badge_fg = outcome_badge(outcome)
        result_cell = (
            f"<span style='background:{badge_bg};color:{badge_fg};border-radius:4px;"
            f"padding:3px 9px;font-size:11px;font-weight:700;white-space:nowrap'>"
            f"{badge_html}</span>"
        )

        test_count = s.get("selected_test_count")
        test_cell = (
            f"<span style='font-weight:600;color:#1565c0'>{test_count}</span>"
            if test_count is not None else
            "<span style='color:#bdbdbd'>—</span>"
        )

        fail_cell = ""
        if outcome == "fail":
            if failed_step:
                fail_cell += (
                    f"<div style='color:#c62828;font-size:11px;font-weight:700;"
                    f"margin-bottom:4px'>{esc(failed_step)}</div>"
                )
            fail_cell += fmt_failed_tests(s.get("failed_tests") or [])

        rows.append(
            f"<tr style='background:{row_bg};page-break-inside:avoid'>"
            f"<td style='{TD_NB}border-left:3px solid {accent}'>{pr_link}</td>"
            f"<td style='{TD_NB}'><span style='color:#202124;font-weight:500'>"
            f"{esc(s.get('author',''))}</span></td>"
            f"<td style='{TD_TITL}'>{esc(s.get('title',''))}</td>"
            f"<td style='{TD_NB}text-align:center'>{result_cell}</td>"
            f"<td style='{TD_NB}text-align:center'>{test_cell}</td>"
            f"<td style='{TD_NB}text-align:center'>"
            f"{fmt_cov(s.get('dart_diff_coverage'), failed_step, outcome)}</td>"
            f"<td style='{TD_NB}text-align:center'>"
            f"{fmt_cov(s.get('cpp_diff_coverage'), failed_step, outcome)}</td>"
            f"<td style='{TD_NB}text-align:center;color:#5f6368'>"
            f"{fmt_ms(s.get('total_ms'))}</td>"
            f"<td style='{TD_FAIL}'>{fail_cell}</td>"
            f"</tr>"
        )

    pr_table = (
        f"<table style='border-collapse:collapse;width:100%;font-family:inherit'>"
        f"<thead><tr>"
        f"<th style='{TH}width:44px'>PR</th>"
        f"<th style='{TH}width:90px'>Author</th>"
        f"<th style='{TH}'>Title</th>"
        f"<th style='{TH}width:70px;text-align:center'>Result</th>"
        f"<th style='{TH}width:52px;text-align:center'>Tests</th>"
        f"<th style='{TH}width:48px;text-align:center'>Dart</th>"
        f"<th style='{TH}width:44px;text-align:center'>C++</th>"
        f"<th style='{TH}width:52px;text-align:center'>Time</th>"
        f"<th style='{TH}width:200px'>Failure</th>"
        f"</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table>"
    )

    # ── Rebuild failures section ─────────────────────────────────────────────

    rebuild_section = build_rebuild_section(data.get("rebuild_failed_tests"))
    timing_section = build_timing_section(data.get("test_timings"), data.get("test_timings_previous"))

    # ── Footer ───────────────────────────────────────────────────────────────

    footer = ""
    if cc:
        footer = (
            f"<div style='font-size:10px;color:#9e9e9e;border-top:1px solid #f1f3f4;"
            f"padding-top:8px;margin-top:14px;text-align:right'>"
            f"Codebase coverage: <strong style='color:#5f6368'>{cov_pct}%</strong>"
            f" ({cc.get('line_hit','?')}&thinsp;/&thinsp;{cc.get('line_total','?')} lines)"
            f"&nbsp;&middot;&nbsp;Generated {esc(data.get('generated_at',''))}"
            f"</div>"
        )

    # ── Full HTML ─────────────────────────────────────────────────────────────

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    /* ── Reset & base ── */
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #f0f2f5;
      color: #202124;
      font-size: 13px;
      line-height: 1.5;
    }}
    a {{ color: #1565c0; text-decoration: none; }}

    /* ── Page layout (PDF) ── */
    @page {{
      size: A4 landscape;
      margin: 12mm 14mm;
    }}

    .page {{
      max-width: 100%;
      padding: 0;
    }}

    /* ── Header card ── */
    .report-header {{
      background: linear-gradient(135deg, #1565c0 0%, #1e88e5 100%);
      border-radius: 8px 8px 0 0;
      padding: 22px 28px 18px;
      color: white;
    }}
    .report-header h1 {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.3px;
      margin-bottom: 12px;
    }}
    .report-header .meta {{
      font-size: 12px;
      color: rgba(255,255,255,.65);
      margin-top: 10px;
    }}

    /* ── Section cards ── */
    .section {{
      background: white;
      border: 1px solid #e8eaed;
      page-break-inside: auto;
    }}
    .section + .section {{
      border-top: none;
    }}
    .section-label {{
      padding: 9px 16px;
      font-size: 10px;
      font-weight: 700;
      color: #9e9e9e;
      text-transform: uppercase;
      letter-spacing: .7px;
      border-bottom: 1px solid #f1f3f4;
    }}

    /* ── Author notes section ── */
    .author-section {{
      border-top: 3px solid #1565c0 !important;
      border-radius: 0 0 8px 8px;
    }}
    .author-section-inner {{
      padding: 14px 18px 12px;
    }}

    /* ── Author cards ── */
    .author-card {{
      margin-bottom: 12px;
      border: 1px solid #e8eaed;
      border-radius: 6px;
      overflow: hidden;
      page-break-inside: avoid;
    }}
    .author-card-header {{
      padding: 7px 14px;
      background: #f5f7ff;
      border-bottom: 1px solid #e8eaed;
    }}
    .author-card-header .name {{
      font-weight: 700;
      font-size: 13px;
      color: #1565c0;
    }}
    .author-card-body {{
      padding: 10px 14px 12px;
    }}

    /* ── PR entry inside author card ── */
    .pr-entry {{
      margin-bottom: 10px;
    }}
    .pr-entry .pr-link {{
      font-size: 12px;
      color: #202124;
      margin-bottom: 3px;
    }}
    .pr-entry p {{
      font-size: 12px;
      color: #5f6368;
      line-height: 1.55;
    }}

    /* ── High-risk callout ── */
    .risk-callout {{
      margin-top: 6px;
      display: flex;
      border-radius: 4px;
      overflow: hidden;
    }}
    .risk-callout .bar {{
      width: 3px;
      background: #f57c00;
      flex-shrink: 0;
    }}
    .risk-callout .content {{
      background: #fff8f0;
      padding: 6px 10px;
      font-size: 11px;
    }}
    .risk-callout .label {{
      color: #e65100;
      font-weight: 700;
    }}
    .review-unavailable {{
      font-size: 11px;
      color: #bdbdbd;
      font-style: italic;
      margin-top: 4px;
    }}
  </style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="report-header">
    <h1>PR Daily Report &mdash; {esc(date)}</h1>
    <div>
      {pills_html}
      {cov_html}
    </div>
    <div class="meta">{esc(data.get('generated_at',''))}</div>
  </div>

  <!-- PR table -->
  <div class="section">
    <div class="section-label">Pull Requests &mdash; {pr_count} total</div>
    {pr_table}
  </div>

  {rebuild_section}

  <!-- Author notes -->
  <div class="section author-section">
    <div class="author-section-inner">
      <div class="section-label" style="padding-left:0;border-bottom:none;margin-bottom:14px">
        Author Notes
      </div>
      <!-- AUTHOR_SUMMARY -->
      {footer}
    </div>
  </div>

  {timing_section}

</div>
</body>
</html>"""

    out_dir = os.path.dirname(out_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"HTML written -> {out_file}")


if __name__ == "__main__":
    main()
