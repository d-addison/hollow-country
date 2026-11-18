"""One smoke scenario over authored bodies; synthetic players/time, no DayZ proof."""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, block


SOURCE = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World/Infected/HCObserverTransitionGate.c"


class ObserverGateSmoke(unittest.TestCase):
    def test_distance_cache_and_continuous_quiet(self):
        source = SOURCE.read_text()
        self.assertTrue("static bool CanTransition(vector pos, float farDistance)" in source,
                        "distance-only CanTransition API is missing")
        start = source.index("{", source.index("class HCObserverTransitionRuntime")) + 1
        runtime = block(source, start)
        player = N(alive=True, pos=(9., 0., 0.))
        player.IsAlive = lambda: player.alive
        player.GetPosition = lambda: player.pos
        clock = N(now=0, server=True, reads=0)
        logs = []

        def players(out):
            clock.reads += 1
            out.extend([player])

        game = N(IsServer=lambda: clock.server, GetTime=lambda: clock.now, GetPlayers=players)
        env = dict(A=A, GetGame=lambda: game, Print=logs.append,
                   vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
                   string=N(Format=lambda fmt, a, b: fmt.replace("%1", str(a)).replace("%2", str(b))),
                   HCObserverTransitionGate=N(Finite=math.isfinite),
                   HCObserverTransitionSite=lambda: N(ClearSince=-1, Position=(0., 0., 0.),
                                                      FarDistance=0., GraceSeconds=0.))
        authored = Authored(runtime, env)
        gate = N(m_Players=A(), m_Positions=A(), m_Sites=A(), m_SnapshotAt=-1,
                 m_LastNow=-1, m_SnapshotValid=False, m_Checks=0, m_Refused=0, m_LastLog=-1)
        for name in re.findall(r"^\s*(?:bool|int|HCObserverTransitionSite) (\w+)\(", runtime, re.M):
            setattr(gate, name, lambda *args, name=name: authored.call(name, gate, *args))
        pos = (0., 0., 0.)
        self.assertFalse(gate.CanTransition(pos, 10.))
        self.assertFalse(gate.Quiet("scene", pos, 10., 3.))
        player.pos = (11., 0., 0.)
        clock.now = 999
        self.assertFalse(gate.CanTransition(pos, 10.))
        self.assertEqual(1, clock.reads)
        clock.now = 1000
        self.assertTrue(gate.CanTransition(pos, 10.))
        self.assertFalse(gate.Quiet("scene", pos, 10., 3.))
        clock.now = 2000
        player.pos = (10., 0., 0.)  # Exact boundary refuses and resets the site.
        self.assertFalse(gate.CanTransition(pos, 10.))
        player.pos = (11., 0., 0.)
        for at in (3000, 4000, 5000):
            clock.now = at
            self.assertFalse(gate.Quiet("scene", pos, 10., 3.))
        clock.now = 6000
        self.assertTrue(gate.Quiet("scene", pos, 10., 3.))
        clock.now = 10000  # Missing samples cannot count toward continuous quiet.
        self.assertFalse(gate.Quiet("scene", pos, 10., 3.))
        player.alive = False
        player.pos = pos
        clock.now = 11000
        self.assertTrue(gate.CanTransition(pos, 10.))
        clock.server = False
        self.assertFalse(gate.CanTransition(pos, 10.))
        clock.server = True
        self.assertFalse(gate.CanTransition(pos, math.nan))
        self.assertEqual([], logs)
        clock.now = 600000
        self.assertTrue(gate.CanTransition(pos, 10.))
        gate.CanTransition(pos, 10.)
        self.assertEqual(1, len(logs))
        self.assertRegex(logs[0], r"^\[HollowCountry\] V2 observer gate checks=\d+ refused=\d+$")


if __name__ == "__main__":
    unittest.main()
