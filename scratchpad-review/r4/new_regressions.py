"""Failing review expectations. Explicit synthetic census only, no DayZ claims."""
from pathlib import Path
import sys,unittest,tempfile,json,contextlib,io
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tests.unit import test_interior_points as f
from tools.audit import interior_points as p
class ReviewRegressions(unittest.TestCase):
 def test_failed_or_missing_selected_control_never_authorizes_treatment(self):
  for source in ('strict','player'):
   for state in ('control-failed','unavailable',None):
    d=f.full_census()
    for row in d['placements']:
     row['player_codes']=[h[5] for h in row['hits']]
     row['reach']['player']={'state':'tested'}
     if row['class'] in p.TENEMENT_CLASSES:
      target=row['reach'] if source=='strict' else row['reach']['player']
      if state is None:target.pop('state',None)
      else:target['state']=state
    with self.subTest(source=source,state=state),self.assertRaises(ValueError):
     p.build_treatment(f.encode(d),f.STOCK,.4,reach_source=source)
 def test_refusal_for_valid_legacy_census_missing_player_codes_writes_report(self):
  with tempfile.TemporaryDirectory(dir=HERE/'tmp') as tmp:
   root=Path(tmp);c=root/'census.json';s=root/'stock.xml';out=root/'treatment.xml';report=root/'report.json'
   c.write_bytes(f.encode(f.full_census()));s.write_bytes(f.STOCK)
   rc=p.main(['--census',str(c),'--stock-proto',str(s),'--output',str(out),'--report',str(report),'--reach-source','player'])
   self.assertEqual(1,rc)
   self.assertFalse(out.exists())
   self.assertTrue(report.exists(),'refusal report missing')
if __name__=='__main__':unittest.main(verbosity=2)
