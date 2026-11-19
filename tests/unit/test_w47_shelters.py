"""Issue 200: offline source survey, never a DayZ access verdict.

The synthetic no-door receipt below models the actual missing evidence shape;
its coordinates and geometry are synthetic and do not qualify a real shelter.
"""
import json
from pathlib import Path
import unittest
from types import SimpleNamespace as N

from tests.unit.test_core_lifecycle import NativeArray
from tests.unit.test_event_runtime import translate
from tools.package.interior_templates import _measure

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c'
MODULE = ROOT / 'mods/HollowCountry/scripts/4_World/Travel/HCShelterModule.c'
SURVEYS = ROOT / 'mission/hollow-country/travel/route-surveys.json'


class RegionalSurvey(unittest.TestCase):
    def test_every_candidate_has_an_auditable_offline_disposition(self):
        manifest = json.loads(SURVEYS.read_text())
        for row in manifest['regional_candidates']:
            with self.subTest(candidate=row['id']):
                survey = row.get('offline_survey')
                self.assertIsNotNone(survey, 'candidate needs stock identity and a specific access evidence gap')
                self.assertEqual('authored-exterior-scene-native-access-pending', survey['result'])
                self.assertEqual(row['building_class'], survey['stock_row']['name'])
                self.assertEqual(row['position'], list(map(float, survey['stock_row']['pos'].split())))
                self.assertEqual('path_pending', survey['class_geometry']['tool_result'])
                self.assertEqual(0, survey['class_geometry']['path_tests'])
                self.assertFalse(survey['class_geometry']['sample_is_candidate'])
                self.assertEqual(['native-site-access-and-clearance-verdict'], survey['missing'])
                self.assertIn(row['reason'], CATALOG.read_text())
                self.assertEqual(3, row['authored_props'])
        self.assertEqual(0, manifest['authored_counts']['safe_additions'])

    def test_no_door_geometry_cannot_be_promoted_to_access_evidence(self):
        # Explicit synthetic receipt: found class with a sane clip, no path verdict.
        row = dict(class_='SyntheticRoof', found=True, box_min=[-2, -2, -2], box_max=[2, 2, 2],
                   hits=[], reach={'state': 'no-door'}, stats={})
        row['class'] = row.pop('class_')
        reason, measured = _measure([{'doc': {'placements': [row]}}], 'SyntheticRoof', 'rot90', 'strict', .6)
        self.assertIsNone(measured)
        self.assertEqual('path_pending', reason)

    def test_startup_reports_each_missing_part_once_without_publishing_discovery(self):
        source = MODULE.read_text().replace('HCShelterSurvey', 'HCEventSurvey').replace('HCShelterRegionalConfig ', 'HCEventConfig ')
        rows = NativeArray([N(Id='synthetic-a', Refusal='site_access_missing'),
                            N(Id='synthetic-b', Refusal='scene_slots_missing')])
        logs = []
        env = dict(HCShelterCatalog=N(HCRegionalConfig=lambda: N(Enabled=True, Scenes=[N(Enabled=True), N(Enabled=True)]), CandidateCount=rows.Count, GetCandidate=lambda i: rows[i]),
                   Print=logs.append)
        owner = type('SyntheticShelter', (), {})
        owner.HCReportCandidateSurveys = translate(source, 'HCReportCandidateSurveys', env, 'HCShelterModule', True)
        state = owner()
        state.m_CandidateSurveyReported = False
        state.HCReportCandidateSurveys()
        state.HCReportCandidateSurveys()
        self.assertEqual(2, len(logs))
        self.assertTrue(all('runtime=PENDING' in line for line in logs))
        self.assertIn('candidate=synthetic-a admission=authored_exterior_scene access=site_access_missing', logs[0])
        self.assertIn('candidate=synthetic-b admission=authored_exterior_scene access=scene_slots_missing', logs[1])
        self.assertIn('if (index == 0) { HCReportCandidateSurveys(); }', source)
        report = source.split('protected void HCReportCandidateSurveys()', 1)[1].split('protected void PlaceShelter', 1)[0]
        self.assertNotIn('.Placed = true', report)
        self.assertNotIn('CreateObject', report)


if __name__ == '__main__':
    unittest.main()
