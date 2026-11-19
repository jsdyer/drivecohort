from datetime import date,timedelta
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from refresh import checked, discover
from aggregate_raw import aggregate


class DataTests(unittest.TestCase):
    def test_published_snapshot_and_probes(self):
        snapshot=json.loads((ROOT/'web/data/cohorts.json').read_text())
        status=json.loads((ROOT/'web/data/status.json').read_text())
        self.assertEqual(status,snapshot['status'])
        self.assertEqual(sum(len(q['rows']) for q in snapshot['quarters']),status['rows'])
        self.assertGreaterEqual(status['models'],34)
        for q in snapshot['quarters']:
            self.assertTrue(q['source'].startswith('https://www.backblaze.com/blog/'))
            rows=q['rows']
            self.assertEqual(len(rows),len({r['model'] for r in rows}))
            checked(rows,sum(r['days'] for r in rows),sum(r['failures'] for r in rows))

    def test_discover_includes_annual_quarterly_report(self):
        self.assertEqual(discover('/blog/backblaze-drive-stats-for-2025/ /blog/backblaze-drive-stats-for-q2-2026/'),{'2025-Q4','2026-Q2'})

    def test_raw_aggregation_requires_complete_quarter(self):
        stream=BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            with self.assertRaisesRegex(ValueError,'Incomplete'): aggregate(z,'2025-Q1')
            for i in range(90):
                day=(date(2025,1,1)+timedelta(days=i)).isoformat()
                data=f'date,model,serial_number,failure\n{day},A,private,0\n'
                if i==0: data+=f'{day},B,also-private,1\n'
                z.writestr(day+'.csv',data)
            rows=aggregate(z,'2025-Q1')
            self.assertEqual(rows,[dict(period='2025-Q1',model='A',drives=1,days=90,failures=0,afr=0),
                                   dict(period='2025-Q1',model='B',drives=0,days=1,failures=1,afr=36500)])
