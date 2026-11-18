"""One synthetic smoke of authored decay/segment logic; no DayZ evidence.

Uses the existing tiny translator unchanged. Synthetic JSON/file and waypoint
collaborators do not establish native persistence, pathing or replication.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import EArray, translate

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World'


class DecaySmoke(unittest.TestCase):
    def test_monotone_persisted_decay_and_population_preserving_segment(self):
        decay = ROOT / 'World/HCSettlementDecay.c'
        self.assertTrue(decay.is_file(), 'missing settlement decay implementation')
        env = dict(Math=N(Min=min, Max=max), HCSettlementDecay=N())
        advance = translate(decay.read_text(), 'RansackAfter', env, 'HCSettlementDecay')
        level = 0
        for day, severity in ((0, 0), (3, 1), (7, 2), (30, 3), (1, 0)):
            result = advance(level, day, severity)
            self.assertGreaterEqual(result, level)
            self.assertLessEqual(result, 3)
            level = result
        self.assertEqual(3, level)
        with TemporaryDirectory(prefix='hc-synthetic-decay-') as tmp:
            image = Path(tmp) / 'decay.json'
            saved = N(Ransack=level, Barricades=2, Remains=1, Notices=1)
            # Explicit synthetic store; the production helper owns native IO.
            def save(row):
                image.write_text(json.dumps(vars(row)))
                return True
            module = N(m_State=saved, m_Store=N(Save=save))
            persist = translate(decay.read_text(), 'Persist', env, 'HCSettlementDecay', member=True)
            self.assertTrue(persist(module))
            self.assertEqual(vars(saved), json.loads(image.read_text()))
        migration = (ROOT / 'Infected/HCHordeMigration.c').read_text()
        members = EArray([object(), object(), object()])
        before = tuple(members)
        pack = N(m_Members=members, m_V2MemberCount=3, m_RoutePlan=EArray(),
                 ActivateWaypoint=lambda now: True)
        env['ActivateWaypoint'] = pack.ActivateWaypoint
        env['BehaviourGroupInfectedPackWaypointParams'] = lambda: lambda end, radius: (end, radius)
        segment = translate(migration, 'V2CommitSegment', env, 'HCNativeInfectedPack', member=True)
        self.assertTrue(segment(pack, [10, 0, 20], 120))
        self.assertEqual(before, tuple(members))
        pack.m_V2MemberCount = 4
        self.assertFalse(segment(pack, [20, 0, 20], 150))
        self.assertEqual(before, tuple(members))


if __name__ == '__main__':
    unittest.main()
