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


POS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<map>
%s
</map>'''
PROTO = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<prototype>
  <group name="Land_House_Synth">
    <usage name="Village" />
    <container name="lootFloor">
      <point pos="-1.0 -2.6 -0.5" range="0.5" height="1.3" />
      <point pos="-4.0 -2.6 2.5" range="0.5" height="1.3" />
      <point pos="3.5 -2.6 0.3" range="1.0" height="2.0" />
      <point pos="-1.5 -2.6 1.7" range="0.9" height="2.0" />
      <point pos="2.0 -2.6 -2.0" range="0.9" height="2.0" />
    </container>
  </group>
  <group name="Land_Shed_Synth">
    <usage name="Village" />
    <container name="lootFloor"><point pos="0 -1 0" range="0.5" height="1" /></container>
  </group>
</prototype>'''


def group(name, x, z, y=100.0):
    return '<group name="%s" pos="%f %f %f" rpy="0 0 0" a="0" />' % (name, x, y, z)


class SiteGeneratorTests(unittest.TestCase):
    """Synthetic stock-format fixtures; the shipped file is generated from the installed stock data."""
    def setUp(self):
        rows = [group('Land_City_PoliceStation', 1000, 1000), group('Land_Mil_Barracks1', 3000, 3000)]
        rows += [group('Land_Mil_Barracks2', 3000 + dx, 3000 + dz) for dx, dz in ((80, 0), (0, 90), (-70, 20), (10, -85))]
        rows += [group('Land_Misc_Shed', 1000 + dx, 1000 + dz) for dx, dz in ((40, 0), (0, 45), (-40, 5), (5, -42))]
        # A town of houses in four clusters about 250 m apart, and one holdout house near the village anchor.
        for cx, cz in ((5000, 5000), (5250, 5000), (5250, 5250), (5000, 5250)):
            rows += [group('Land_House_Synth', cx + 8 * i, cz + 6 * i) for i in range(4)]
        rows.append(group('Land_House_Synth', 7010, 7005))
        rows.append(group('Land_Shed_Synth', 7000, 7000))
        self.pos, self.proto = POS % '\n'.join(rows), PROTO
        self.spec = dict(
            patrols=[dict(Id='police-synth', Faction='Guards', Anchor=['Land_City_PoliceStation'], Near=[1000, 1000],
                          Around=['Land_'], Radius=120),
                     dict(Id='mil-synth', Faction='East', Anchor=['Land_Mil_Barracks1'], Near=[3000, 3000],
                          Around=['Land_Mil_'], Radius=250)],
            scavengers=[dict(Id='scav-synth', Near=[5125, 5125], Radius=500)],
            holdouts=[dict(Id='holdout-synth', Near=[7000, 7000], Radius=300, CacheClass='WoodenCrate',
                           Loot=[['Rag', 2], ['TunaCan', 1]])])

    def test_generated_policy_takes_positions_from_the_stock_files(self):
        policy = ai_patrols.generate_sites(self.pos, self.proto, self.spec)
        sites = {s['Id']: s for s in policy['Sites']}
        self.assertEqual(set(sites), {'police-synth', 'mil-synth', 'scav-synth', 'holdout-synth'})
        police = sites['police-synth']
        self.assertEqual(police['Kind'], 'patrol')
        self.assertGreaterEqual(len(police['Waypoints']), 3)
        for x, _, z in police['Waypoints']:
            self.assertLess(((x - 1000) ** 2 + (z - 1000) ** 2) ** 0.5, 120)
        scav = sites['scav-synth']
        self.assertEqual((scav['Kind'], scav['Faction']), ('scavenger', 'Raiders'))
        self.assertGreaterEqual(len(scav['Waypoints']), 3)
        legs = [((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
                for a, b in zip(scav['Waypoints'], scav['Waypoints'][1:] + scav['Waypoints'][:1])]
        self.assertLessEqual(max(legs), policy['MaxLegLength'])
        hold = sites['holdout-synth']
        self.assertEqual((hold['Kind'], hold['HouseClass'], hold['Faction']), ('holdout', 'Land_House_Synth', 'Guards'))
        self.assertEqual(hold['HousePosition'], [7010.0, 100.0, 7005.0])
        floor = {(-1.0, -2.6, -0.5), (-4.0, -2.6, 2.5), (3.5, -2.6, 0.3), (-1.5, -2.6, 1.7), (2.0, -2.6, -2.0)}
        self.assertTrue({tuple(p) for p in hold['LocalPoints']} <= floor)
        self.assertIn(tuple(hold['CacheLocal']), floor)
        self.assertNotIn(tuple(hold['CacheLocal']), {tuple(p) for p in hold['LocalPoints']})
        self.assertEqual(hold['CacheLoot'], [{'ClassName': 'Rag', 'Quantity': 2}, {'ClassName': 'TunaCan', 'Quantity': 1}])
        self.assertEqual(hold['Waypoints'], [])

    def test_generator_refuses_dtd_and_missing_anchors(self):
        with self.assertRaises(ValueError):
            ai_patrols.generate_sites('<!DOCTYPE x [<!ENTITY a "b">]>' + self.pos, self.proto, self.spec)
        self.spec['patrols'][0]['Near'] = [9000, 9000]
        with self.assertRaises(ValueError):
            ai_patrols.generate_sites(self.pos, self.proto, self.spec)

    def test_shipped_sites_are_the_generator_output_shape(self):
        shipped = json.loads((ROOT / 'mission/hollow-country/ai/sites.json').read_text())
        # HC-43 adds authored candidate metadata beside the unchanged live
        # generator policy; these rows are not admitted routes or native proof.
        manifest = shipped.pop('HC43')
        self.assertEqual(('HC-43', 'pending_integration', 'PENDING'),
                         (manifest['Package'], manifest['State'], manifest['Runtime']))
        # Explicit worker-local policy fixture. The generator is read-only in
        # this area; lead adds these defaults to its shared POLICY_DEFAULTS.
        generated = ai_patrols.generate_sites(self.pos, self.proto, self.spec)
        generated.update(AIRespawnSeconds=900, PatrolRespawnSeconds=0,
                         HoldoutRespawnSeconds=0, MilitaryRespawnSeconds=0,
                         MemberReplaceSeconds=600)
        self.assertEqual(set(shipped), set(generated))
        for key in ('AIRespawnSeconds', 'PatrolRespawnSeconds', 'HoldoutRespawnSeconds',
                    'MilitaryRespawnSeconds', 'MemberReplaceSeconds'):
            self.assertEqual(generated[key], shipped[key])
        self.assertLessEqual(len((ROOT / 'mission/hollow-country/ai/sites.json').read_bytes()), 65536)
        authored_checkpoints = {'checkpoint-komarovo-east', 'checkpoint-novaya-south'}
        self.assertTrue(all(s['Id'] in {x['Id'] for k in ai_patrols.SITE_SPEC.values() for x in k} | authored_checkpoints
                            for s in shipped['Sites']))
