"""Nightly producer: validate report date, render dated PDF, publish project-owned email."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT.parent / 'Report-Delivery'
sys.path.insert(0, str(SHARED))
from delivery import Store, attachment, now, read_json, validate, write_json, key


def preflight(root, day):
    root = Path(root)
    data = read_json(root / 'nightly-report-data.json')
    dt.date.fromisoformat(day)
    if data.get('date') != day:
        raise ValueError(f'Report data date {data.get("date")} differs from requested {day}; fetch incomplete or stale')
    if not isinstance(data.get('prs'), list) or data.get('pr_count') != len(data['prs']):
        raise ValueError('Invalid or incomplete PR data')
    return data


def build_manifest(root, day, pdf, sender):
    root = Path(root)
    data = preflight(root, day)
    count = data['pr_count']
    counts = {name:sum(1 for p in data['prs'] if (p.get('summary') or {}).get('outcome') == name)
              for name in ('pass', 'fail', 'skipped')}
    m = dict(schema_version=1, report_id='nightly-pr-report', report_date=day,
        generation=uuid.uuid4().hex, generated_at=now(), sender_account=sender,
        recipients=read_json(root / 'recipients.json')['recipients'], attachments=[])
    m['project_metadata'] = dict(pr_count=count, pass_count=counts['pass'], fail_count=counts['fail'], skip_count=counts['skipped'])
    if count == 0:
        m.update(subject=f'No PR activity today — {day}', body=f'No PR activity today — {day}',
            no_attachment_reason='no_pr_activity')
    else:
        if not pdf:
            raise ValueError('Current report PDF required')
        pdf = Path(pdf)
        if pdf.stat().st_mtime_ns < (root / 'nightly-report-data.json').stat().st_mtime_ns:
            raise ValueError('PDF predates the current report data')
        m.update(subject=f'PR Daily Report — {day} ({count} PRs, {counts["fail"]} failed)',
            body=f'PR Daily Report — {day}\n\n✅ {counts["pass"]} passed   ❌ {counts["fail"]} failed   ⏭ {counts["skipped"]} skipped\n\nFull report attached as PDF.',
            attachments=[attachment(pdf)])
    return validate(m)


def sync(root, day, store, sender):
    job = store.get(key('nightly-pr-report', day, sender))
    if job['status'] != 'sent' or not job.get('email_sent'):
        raise ValueError('Shared delivery is not confirmed sent')
    if job.get('legacy'):
        return dict(action='legacy_already_sent', id=job['id'])
    m = job['manifest']
    if m['report_id'] != 'nightly-pr-report' or m['report_date'] != day or m['sender_account'].lower() != sender.lower():
        raise ValueError('Receipt identity mismatch')
    counts = m['project_metadata']
    status = dict(last_run=now(), date=day, **counts, email_sent=True,
        delivery_id=job['id'], delivery_evidence=job['evidence'],
        pdf_path=m['attachments'][0]['path'] if m['attachments'] else None)
    write_json(Path(root) / 'output' / day / 'delivery-receipt.json', status)
    latest_path = Path(root) / 'run-status.json'
    latest = read_json(latest_path) if latest_path.exists() else {}
    if latest.get('date', '') <= day:
        write_json(latest_path, status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'prepare', 'submit', 'sync'])
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    sender = read_json(SHARED / 'config.local.json')['sender_account']
    store = Store()
    if args.action == 'sync':
        result = sync(ROOT, args.date, store, sender)
    else:
        data = preflight(ROOT, args.date)
        if args.action == 'preflight':
            result = dict(action='report_data_ready', date=args.date, pr_count=data['pr_count'])
        else:
            old = next((j for j in store.list() if j['id'] == key('nightly-pr-report', args.date, sender)), None)
            if old:
                # Existing queued/unknown jobs must be resumed from the immutable spool.
                result = dict(action='existing_delivery', **old)
            elif args.action == 'submit':
                result = store.submit(read_json(ROOT / 'output' / args.date / 'delivery-manifest.json'))
            else:
                pdf = None
                if data['pr_count']:
                    html = ROOT / 'nightly-report.html'
                    if html.stat().st_mtime_ns < (ROOT / 'nightly-report-data.json').stat().st_mtime_ns:
                        raise ValueError('HTML predates current data; generate and validate Author Notes first')
                    subprocess.run([sys.executable, str(ROOT / 'scripts/validate_author_notes.py'),
                        '--data', str(ROOT / 'nightly-report-data.json'), '--html', str(ROOT / 'author-summary.html')],
                        check=True, cwd=ROOT)
                    text = html.read_text(encoding='utf-8')
                    if (ROOT / 'author-summary.html').read_text(encoding='utf-8') not in text:
                        raise ValueError('Validated Author Notes are not present in HTML')
                    if args.date not in text or '<!-- AUTHOR_SUMMARY -->' in text:
                        raise ValueError('HTML date mismatch or Author Notes not inserted')
                    pdf = ROOT / 'output' / args.date / f'PR-Daily-Report-{args.date}.pdf'
                    subprocess.run(['node', str(ROOT / 'scripts/render_report.cjs'), str(html), str(pdf)],
                        check=True, cwd=ROOT)
                m = build_manifest(ROOT, args.date, pdf, sender)
                path = ROOT / 'output' / args.date / 'delivery-manifest.json'
                write_json(path, m)
                result = dict(action='report_ready', manifest=str(path), **m)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
