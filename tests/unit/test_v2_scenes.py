"""One smoke test of authored scene guards with explicit synthetic coordinates.

Reuses the existing restricted translator unchanged; this is not DayZ evidence.
"""
from pathlib import Path
from types import SimpleNamespace as N
import json
import re
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray

SCENES = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Scenes'


class SceneSmoke(unittest.TestCase):
    def test_successful_scene_clears_refusal_after_optional_note_attempt(self):
        # Explicit synthetic director/placement/note ports. Optional note
        # refusal must not leave the successfully placed scene marked refused.
        source = (SCENES / 'HCScenesModule.c').read_text()
        adapted = re.sub(r'\bHCScene(\w+)\b', r'HCEventScene\1', source)
        adapted = adapted.replace('array<vector> positions;', 'HCEventPositions positions;')

        class Reasons(dict):
            def Remove(self, key):
                self.pop(key, None)

        for note_refused in (False, True):
            with self.subTest(note_refused=note_refused):
                chain = N(Id='scene-kamenka', Stage=0, EventId=1, Director=N(),
                          Cancelled=False, Complete=False, DueAt=100, BeganAt=100)
                stage = N(Kit='synthetic-kit', HoldSeconds=1000)
                plan = N(Stages=EArray([stage]), SiteId='synthetic-site')
                reasons = Reasons({chain.Id: 'slope'})
                published = []

                def publish(row, site):
                    published.append(row.Id)
                    if note_refused:
                        reasons[row.Id] = 'note-slope'

                env = {
                    'Print': lambda message: None,
                    'HCEventStatus': N(ANNOUNCED=1, COMPLETED=4),
                    'HCEventDirector': N(FindRecord=lambda director, event: N(Status=1)),
                    'HCEventSceneChains': N(ResumeAfterGap=lambda state, now: 0,
                                           CancelExpired=lambda *args: False,
                                           Site=lambda site: N(Position=[1, 0, 2])),
                    'HCEventSceneKits': N(Find=lambda kit: N(), Preflight=lambda *args: True,
                                         Place=lambda *args: True, Healthy=lambda lease: True,
                                         HCPlacementComplete=lambda lease: True),
                    'HCEventSceneLease': lambda: N(Objects=EArray([N()]), ViewEventId=1),
                }
                work = translate(adapted, 'Work', env, 'HCEventScenesModule', member=True)
                owner = N(m_State=N(Chains=EArray([chain]), Catalog=N(Chains=EArray([plan]))),
                          m_Cursor=0, m_Leases=EArray(), m_Placed=0, m_Refused=0,
                          m_PreflightReasons=reasons, m_Stories=N(HCReady=lambda: True),
                          SiteAvailable=lambda anchor: True,
                          PublishSceneStory=publish)
                owner.Lease = lambda key: next(iter(owner.m_Leases), None)
                work(owner, 100)
                self.assertEqual({}, reasons)
                self.assertEqual([chain.Id], published)
                work(owner, 101)
                self.assertEqual([chain.Id], published)
                self.assertEqual(1, len(owner.m_Leases))
                self.assertEqual(1, owner.m_Placed)

    def test_expired_stage_cancels_and_door_keepout_rejects(self):
        env = {}
        failed = translate((SCENES / 'HCSceneChains.c').read_text(), 'StageFailed', env)
        outside = translate((SCENES / 'HCSceneKits.c').read_text(), 'OutsideDoor', env)
        # Status values are the existing director enum: announced=1, completed=4,
        # expired=5, cancelled=6. Exact deadline cancels even before placement.
        self.assertFalse(failed(99, 100, 1))
        self.assertTrue(failed(100, 100, 1))
        self.assertTrue(failed(50, 100, 5))
        self.assertTrue(failed(50, 100, 6))
        self.assertFalse(failed(101, 100, 4))
        # Execute the same cancellation entry point used by the server loop.
        # A queued stage has no event/engine handles, but still expires alone.
        owner = N(StageFailed=failed)
        env['HCSceneChains'] = owner
        source = (SCENES / 'HCSceneChains.c').read_text()
        owner.Cancel = translate(source, 'Cancel', env, 'HCSceneChains')
        cancel_expired = translate(source, 'CancelExpired', env, 'HCSceneChains')
        chain = N(ExpiresAt=100, EventId=0, Cancelled=False)
        self.assertFalse(cancel_expired(chain, 99, 1))
        self.assertFalse(chain.Cancelled)
        self.assertTrue(cancel_expired(chain, 100, 1))
        self.assertTrue(chain.Cancelled)
        # 4 m door clearance PLUS the full authored prop footprint; height does
        # not permit a prop through a doorway. Boundary itself is a keepout.
        self.assertFalse(outside([0., 0., 0.], [0., 20., 0.], 2.))
        self.assertFalse(outside([6., 0., 0.], [0., 0., 0.], 2.))
        self.assertTrue(outside([6.01, 0., 0.], [0., 0., 0.], 2.))
        # Authored content smoke: provenance is source evidence, not runtime
        # proof. Each new kit must resolve entirely to reviewed vanilla models.
        events = SCENES.parents[4] / 'mission/hollow-country/events'
        provenance = json.loads((events / 'scene-provenance.json').read_text())
        verified = {row['class']: row for row in provenance['classes']}
        kits = (SCENES / 'HCSceneKits.c').read_text()
        variants = ('supply-drop-opened', 'convoy-roadside',
                    'quarantine-cordon', 'survivor-cold-camp')
        for variant in variants:
            block = re.search(r'if \(kind == "' + variant + r'"\)\s*\{([^}]+)\}', kits)
            self.assertIsNotNone(block, 'Missing new scene kit: ' + variant)
            props = re.findall(r'Add\(kit, "([^"]+)", ([^;]+)\);', block[1])
            self.assertTrue(1 <= len(props) <= 8)
            for kind, args in props:
                row = verified[kind]
                self.assertTrue(row['model_member_present'], kind)
                self.assertTrue(row['parent'] == 'HouseNoDestruct' or args.endswith('true'))
                x, z, yaw, radius = map(float, args.split(',')[:4])
                self.assertGreater(z - radius, 4)
                # Explicit synthetic door directly under this prop: the same
                # guard called by Preflight must refuse the whole placement.
                self.assertFalse(outside([x, 0., z], [x, 20., z], radius))
        catalog = json.loads((events / 'scene-chains.json').read_text())['Chains']
        self.assertEqual(4, len(catalog))
        self.assertEqual(259200, catalog[3]['Stages'][0]['DelaySeconds'])
        referenced = {s['Kit'] for c in catalog for s in c['Stages']}
        self.assertTrue(set(variants) <= referenced)
        # A reused anchor cannot overlap a prior kit, even during cleanup.
        available = translate((SCENES / 'HCScenesModule.c').read_text(),
                              'SiteAvailable', {}, member=True)
        lease_owner = N(m_Leases=[N(Anchor=[1, 0, 2], Closing=True)])
        self.assertFalse(available(lease_owner, [1, 0, 2]))
        self.assertTrue(available(lease_owner, [3, 0, 4]))


    def test_kit_layouts_turn_and_mirror_about_the_anchor(self):
        # Windows release 011: every stage-0 kit was refused on steep ground at its
        # anchor. The same kit may be turned/mirrored, keeping its shape and distance.
        source = (SCENES / 'HCSceneKits.c').read_text()
        env = {'Vector': lambda x, y, z: [x, y, z]}
        offset = translate(source, 'LayoutOffset', env)
        yaw = translate(source, 'LayoutYaw', env)
        self.assertEqual([3, 0, 8], offset([3, 0, 8], 0))
        self.assertEqual(30, yaw(30, 0))
        layouts = [offset([3, 0, 8], v) for v in range(8)]
        self.assertEqual(8, len({tuple(p) for p in layouts}))
        for point in layouts:
            self.assertEqual(73, point[0] ** 2 + point[2] ** 2)
        for variant in range(8):
            self.assertTrue(0 <= yaw(30, variant) < 360)
        # Release 013 review: the world east/west access strip z=-4..4 must stay
        # clear in every layout, so the corridor test uses the turned offset.
        strip = translate(source, 'InAccessStrip', env)
        self.assertFalse(strip(offset([3, 0, 8], 0), 2.5))
        self.assertFalse(strip(offset([3, 0, 8], 2), 2.5))
        self.assertTrue(strip(offset([3, 0, 8], 1), 2.5))
        self.assertTrue(strip(offset([3, 0, 8], 3), 2.5))
        self.assertTrue(strip([0, 0, -5], 1.5))
        self.assertIn('InAccessStrip(offset, prop.Radius)', source)


if __name__ == '__main__':
    unittest.main()
