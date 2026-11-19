"""Verify archived chart transcriptions and refresh the official quarterly HTML tables."""
from argparse import ArgumentParser
from calendar import monthrange
from datetime import date, datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BLOG = 'https://www.backblaze.com/blog/'
ARCHIVE = BLOG + 'category/hard-drive-stats/'
FIELDS = ('maker', 'model', 'tb', 'drives', 'days', 'failures', 'afr')


def report(period):
    year, q = period.split('-Q')
    suffix = year if q == '4' else f'q{q}-{year}'
    return BLOG + f'backblaze-drive-stats-for-{suffix}/'


def bounds(period):
    year, q = (int(s) for s in period.split('-Q'))
    month = 3 * q
    return [date(year, month - 2, 1).isoformat(),
            date(year, month, monthrange(year, month)[1]).isoformat()]


def get(url):
    return subprocess.check_output(['curl', '--fail', '--silent', '--show-error', '--location',
                                    '--retry', '3', '--max-time', '90', url])


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.cell = None
        self.row = []
        self.heading = None
        self.section = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            self.heading = []
        if tag == 'table':
            self.table = (dict(attrs).get('id', ''), self.section, [])
        elif self.table is not None:
            if tag == 'tr':
                self.row = []
            elif tag in ('td', 'th'):
                self.cell = []

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)
        if self.heading is not None:
            self.heading.append(value)

    def handle_endtag(self, tag):
        if tag == 'h2' and self.heading is not None:
            self.section = ' '.join(''.join(self.heading).split()).lower()
            self.heading = None
        if self.table is not None:
            if tag in ('td', 'th') and self.cell is not None:
                self.row.append(''.join(self.cell).strip())
                self.cell = None
            elif tag == 'tr':
                self.table[2].append(self.row)
            elif tag == 'table':
                self.tables.append(self.table)
                self.table = None


def number(text):
    return str(text).replace(',', '').replace('%', '').strip()


def checked(rows, total_days, failures):
    if not rows:
        raise ValueError('Empty report')
    seen = set()
    for r in rows:
        for key in ['tb', 'days', 'failures', 'drives']:
            r[key] = int(number(r[key]))
        r['afr'] = float(number(r['afr']))
        if (not r['model'] or r['model'] in seen or r['drives'] <= 0 or r['days'] <= 0
                or r['tb'] <= 0 or r['failures'] < 0 or r['failures'] > r['days']
                or abs(r['afr'] - r['failures'] * 36500 / r['days']) > 0.0051):
            raise ValueError(f"Check source row for {r['model']}")
        seen.add(r['model'])
    if sum(r['days'] for r in rows) != total_days or sum(r['failures'] for r in rows) != failures:
        raise ValueError('Published quarter totals do not reconcile')
    return rows


def parse_report(page, period):
    tables = Tables()
    tables.feed(page)
    year, quarter = period.split('-')
    for anchor, section, table in tables.tables:
        if not all(s in section for s in (quarter.lower(), year, 'failure rate')):
            continue
        head = [x.lower() for x in table[0]]
        if not all(s in head for s in ('model', 'size (tb)', 'drive count', 'drive days', 'afr (%)')):
            continue
        indices = [head.index(s) for s in ('mfg', 'model', 'size (tb)', 'drive count', 'drive days',
                                             'failures' if 'failures' in head else 'drive failures', 'afr (%)')]
        body, totals = table[1:-1], table[-1]
        if 'totals' not in [s.lower() for s in totals]:
            raise ValueError('Missing quarterly totals')
        rows = [dict(zip(FIELDS, (r[i] for i in indices))) for r in body]
        return checked(rows, int(number(totals[indices[4]])), int(number(totals[indices[5]]))), anchor
    raise ValueError(f'No quarterly production table found for {period}. Review the source format.')


def discover(archive):
    periods = set()
    for match in re.finditer(r'/blog/backblaze-drive-stats-for-(?:(q[1-4])-)?(20\d{2})/', archive, re.I):
        quarter, year = match.groups()
        periods.add(f"{year}-{(quarter or 'q4').upper()}")
    return periods


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, help='Read previously retrieved report HTML and charts locally')
    args = parser.parse_args()
    chart_index = json.loads((ROOT / 'sources/charts.json').read_text())
    data = ROOT / 'web/data'
    prior = json.loads((data / 'cohorts.json').read_text()) if (data / 'cohorts.json').exists() else {'quarters': []}
    periods = set(chart_index) | {s['id'] for s in prior['quarters']} | {'2026-Q1', '2026-Q2'}
    if not args.cache:
        discovered = discover(get(ARCHIVE).decode())
        if not discovered:
            raise ValueError('Drive Stats archive links could not be read')
        periods |= {p for p in discovered if p > max(chart_index)}
    quarters = []
    for period in sorted(periods):
        year, q = period.split('-')
        filename = year if q == 'Q4' else q + '-' + year
        url = report(period)
        if period in chart_index:
            chart = chart_index[period]
            blob = (args.cache / (filename + '.png')).read_bytes() if args.cache else get(chart['chart'])
            if sha256(blob).hexdigest() != chart['sha256']:
                raise ValueError(f'{period} chart changed; review the CSV against the new chart')
            with (ROOT / 'sources' / (period + '.csv')).open() as source:
                rows = checked(list(csv.DictReader(source)), chart['days'], chart['failures'])
            link = chart['chart']
        else:
            page = (args.cache / (filename + '.html')).read_text() if args.cache else get(url).decode()
            rows, anchor = parse_report(page, period)
            link = url + ('#' + anchor if anchor else '')
        start, end = bounds(period)
        quarters.append(dict(id=period, start=start, end=end, article=url, source=link, rows=rows))
    stamp = datetime.now(timezone.utc).date().isoformat()
    status = dict(start=quarters[0]['start'], end=quarters[-1]['end'], retrieved=stamp,
                  rows=sum(len(q['rows']) for q in quarters), quarters=len(quarters),
                  models=len({r['model'] for q in quarters for r in q['rows']}))
    with TemporaryDirectory(dir=data) as tmp:
        for name, payload in [('cohorts', {'quarters': quarters, 'status': status}), ('status', status)]:
            (Path(tmp) / (name + '.json')).write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))+'\n')
        for file in Path(tmp).iterdir():
            file.replace(data / file.name)
    print(status)


if __name__ == '__main__':
    main()
