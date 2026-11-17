"""Synthetic data contract tests; route geometry needs native acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools.package import ai_patrols

ROOT=Path(__file__).resolve().parents[2]


class PatrolTests(unittest.TestCase):
    def setUp(self):
        self.sites={'Sites':[{'Id':'synthetic-site','Position':[100,10,200],'Reviewed':True}]}
        self.route=dict(SiteId='synthetic-site',MissionId='synthetic-site-5',Anchor=[100,10,200],
                        GroupSize=2,Spawns=[[102,10,200],[104,10,200]],
                        Waypoints=[[110,10,200],[110,10,210]],ActorClass='eAI_SurvivorM_Mirek',
                        FactionName='Raiders',SurveySha256='',LoadoutSha256='',
                        Equipment=[dict(ClassName='MakarovIJ70',InHands=True,IsMagazine=False,AmmoCount=0),
                                   dict(ClassName='Mag_IJ70_8Rnd',InHands=False,IsMagazine=True,AmmoCount=8)])
        self.route['LoadoutSha256']=ai_patrols.loadout_hash(self.route['Equipment'])
        self.data={'SchemaVersion':1,'Missions':[self.route]}

    def test_matching_contract_is_valid_but_unsurveyed(self):
        result=ai_patrols.validate(self.data,self.sites)
        self.assertEqual(['synthetic-site'],result['site_ids'])
        self.assertFalse(result['qualified'])

    def test_reject_missing_duplicate_unreviewed_or_drifted_site(self):
        for change in (lambda s:s['Sites'].clear(),
                       lambda s:s['Sites'].append(copy.deepcopy(s['Sites'][0])),
                       lambda s:s['Sites'][0].update(Reviewed=False),
                       lambda s:s['Sites'][0].update(Position=[101,10,200])):
            sites=copy.deepcopy(self.sites);change(sites)
            with self.assertRaises(ValueError):ai_patrols.validate(self.data,sites)

    def test_reject_mismatched_group_ammo_hash_route_or_duplicate_patrol(self):
        for change in (lambda d:d['Missions'][0].update(GroupSize=3),
                       lambda d:d['Missions'][0]['Equipment'][1].update(AmmoCount=-1),
                       lambda d:d['Missions'][0]['Spawns'][0].__setitem__(0,float('nan')),
                       lambda d:d['Missions'][0].update(LoadoutSha256='0'*64),
                       lambda d:d['Missions'][0].update(MissionId='other'),
                       lambda d:d['Missions'].append(copy.deepcopy(d['Missions'][0]))):
            data=copy.deepcopy(self.data);change(data)
            with self.assertRaises(ValueError):ai_patrols.validate(data,self.sites)

    def test_reader_rejects_duplicate_keys_nonfinite_oversized_or_wrong_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'data.json'
            for value in ('{"Sites":[],"Sites":[]}','{"x":NaN}','[]',' '*65537):
                path.write_text(value)
                with self.assertRaises(ValueError):ai_patrols.read_json(path)

    def test_shipped_patrols_cover_every_published_site_contract(self):
        folder=ROOT/'mission/hollow-country/ai'
        sites=ai_patrols.read_json(folder/'event-sites.contract.json')
        data=ai_patrols.read_json(folder/'patrols.example.json')
        result=ai_patrols.validate(data,sites)
        self.assertEqual(sorted(s['Id'] for s in sites['Sites']),result['site_ids'])
        self.assertFalse(result['qualified'])
