"""Aggregate a complete local Backblaze quarter ZIP. Output contains no drive identifiers."""
from argparse import ArgumentParser
from collections import Counter
from csv import DictReader, DictWriter
from datetime import date, timedelta
from io import TextIOWrapper
from pathlib import PurePosixPath
import re
import sys
import zipfile
from refresh import bounds


def aggregate(archive, period):
    start, end = map(date.fromisoformat, bounds(period))
    expected = {(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)}
    files = {}
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if '__MACOSX' in path.parts or not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv', path.name):
            continue
        day = path.stem
        if day in expected:
            if day in files:
                raise ValueError(f'Duplicate daily file: {day}')
            files[day] = member
    missing = sorted(expected - files.keys())
    if missing:
        raise ValueError('Incomplete quarter, missing ' + ', '.join(missing))
    days, failures, end_count = Counter(), Counter(), Counter()
    for day in sorted(files):
        seen = set()
        with archive.open(files[day]) as raw, TextIOWrapper(raw, encoding='utf-8-sig', newline='') as text:
            reader = DictReader(text)
            required = {'date', 'model', 'failure', 'serial_number'}
            if not required.issubset(reader.fieldnames or ()):
                raise ValueError(f'{day}: missing raw data columns')
            for row in reader:
                model = row['model'].strip()
                key = (model, row['serial_number'].strip())
                if row['date'] != day or not model or not key[1] or row['failure'] not in ('0','1') or key in seen:
                    raise ValueError(f'{day}: inconsistent or duplicate drive observation')
                seen.add(key)
                days[model] += 1
                failures[model] += int(row['failure'])
                if day == end.isoformat():
                    end_count[model] += 1
        if not seen:
            raise ValueError(f'{day}: no observations')
    return [dict(period=period,model=model,drives=end_count[model],days=days[model],failures=failures[model],
                 afr=round(failures[model]*36500/days[model], 2)) for model in sorted(days)]


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument('period', help='Example: 2025-Q2')
    p.add_argument('zip', help='Backblaze daily CSV archive for this quarter')
    args = p.parse_args()
    if not re.fullmatch(r'20\d{2}-Q[1-4]', args.period):
        p.error('Expected a quarter such as 2025-Q2')
    with zipfile.ZipFile(args.zip) as archive:
        rows = aggregate(archive,args.period)
    writer = DictWriter(sys.stdout, fieldnames=rows[0].keys(), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)

if __name__ == '__main__':
    main()
