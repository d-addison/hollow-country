"""One smoke test of authored scene guards with explicit synthetic coordinates.

Reuses the existing restricted translator unchanged; this is not DayZ evidence.
"""
from pathlib import Path
from types import SimpleNamespace as N
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


if __name__ == '__main__':
    unittest.main()
