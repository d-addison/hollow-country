"""One smoke test of authored scene guards with explicit synthetic coordinates.

Reuses the existing restricted translator unchanged; this is not DayZ evidence.
"""
from pathlib import Path
from types import SimpleNamespace as N
import json
import re
import unittest

from tests.unit.test_event_runtime import translate

SCENES = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Scenes'


class SceneSmoke(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
