"""One source/lifecycle smoke check; synthetic placement is not DayZ evidence.

RED before implementation, command (also GREEN afterward):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_v2_shelters -v
AssertionError: False is not true : missing shelter implementation
GREEN: Ran 1 test in 0.004s / OK.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_core_lifecycle import NativeArray
from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
TRAVEL = ROOT / 'mods/HollowCountry/scripts/4_World/Travel'


class ShelterSmoke(unittest.TestCase):
    def test_catalog_and_repeated_start_stop(self):
        catalog = TRAVEL / 'HCShelterCatalog.c'
        module = TRAVEL / 'HCShelterModule.c'
        self.assertTrue(catalog.is_file() and module.is_file(), 'missing shelter implementation')
        entries = re.findall(r'Add\("([^"]+)", "([\d. ]+)", "([^"]+)"\);', catalog.read_text())
        self.assertTrue(5 <= len(entries) <= 10, entries)
        self.assertEqual(len(entries), len({row[0] for row in entries}))
        self.assertEqual(len(entries), len({tuple(map(float, row[1].split())) for row in entries}))
        self.assertTrue(all(len(row[2]) > 30 for row in entries))
        logs, deleted = [], []
        game = N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus')
        env = dict(GetGame=lambda: game, Print=logs.append, str=str,
                   HCShelterCatalog=N(Count=lambda: len(entries)),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission ' + args[2]))
        source = module.read_text()
        owner = type('SyntheticShelterModule', (), {})
        for method in ('IsEnabled', 'OnStart', 'OnStop'):
            setattr(owner, method, translate(source, method, env, 'HCShelterModule', True))
        state = owner()
        state.m_Started = False
        state.m_Objects = NativeArray()
        state.m_Placed = state.m_Refused = 0

        def synthetic_place(index):
            # Explicit engine seam: three synthetic static handles per shelter.
            for slot in range(3):
                state.m_Objects.Insert((index, slot))
            state.m_Placed += 1

        state.PlaceShelter = synthetic_place
        state.DeleteProp = deleted.append
        off, on = N(EnableTravel=False), N(EnableTravel=True)
        state.OnStart(off)
        self.assertEqual(0, len(logs))
        state.OnStart(on)
        state.OnStart(on)
        self.assertEqual(len(entries) * 3, state.m_Objects.Count())
        self.assertEqual(1, sum('EXP-T5' in line for line in logs))
        self.assertIn(f'[HollowCountry] V2 shelters placed={len(entries)} props={len(entries) * 3} refused=0', logs)
        state.OnStop()
        state.OnStop()
        self.assertEqual(len(entries) * 3, len(deleted))
        self.assertEqual(0, state.m_Objects.Count())
        state.OnStart(on)
        self.assertEqual(len(entries) * 3, state.m_Objects.Count())
        self.assertEqual(0, state.m_Refused)


class ShelterPlacementFallback(unittest.TestCase):
    """Synthetic terrain/vegetation seams only; DayZ placement stays unobserved."""

    BARN = (1000.0, 0.0, 1000.0)

    def owner(self, surface, sea=lambda x, z: False):
        source = (TRAVEL / 'HCShelterModule.c').read_text()
        game = N(SurfaceY=surface, SurfaceIsSea=sea, SurfaceIsPond=lambda x, z: False)
        env = dict(GetGame=lambda: game, Print=lambda text: None, str=str,
                   Vector=lambda x, y, z: [float(x), float(y), float(z)],
                   Math=N(AbsFloat=abs, Cos=math.cos, Sin=math.sin, DEG2RAD=math.pi / 180.0))
        for name, value in re.findall(r'static const (?:int|float) (HC_\w+) = ([-\d.]+);', source):
            env[name] = float(value) if '.' in value else int(value)
        owner = type('SyntheticShelterModule', (), {})
        for method in ('HCRingShift', 'HCRingOffset', 'HCInBarnAccessStrip', 'GroundFlat', 'HCRingRise',
                       'HCScreenRing', 'HCNextRingCandidate', 'HCSoftVegetation'):
            setattr(owner, method, translate(source, method, env, 'HCShelterModule', True))
        state = owner()
        state.m_GroundRise = 0.0
        state.m_BlockingClass = 'none'
        state.m_RingRise = 0.0
        state.m_RingRises = RingArray()
        return state, env

    def house(self):
        bx, _, bz = self.BARN
        return N(ModelToWorld=lambda o: [bx + o[0], 0.0, bz + o[2]])

    def test_steep_authored_yard_falls_back_to_flattest_bounded_ring_candidate(self):
        bx, _, bz = self.BARN

        def surface(x, z):
            # Bor South Rest-like slope (rise 0.6 on the 2.4 m footprint) except two
            # reviewed synthetic patches west of the barn: gentle north, flatter south.
            if x < bx - 20 and z > bz + 2:
                return 0.15 * x
            if x < bx - 20 and z < bz - 2:
                return 0.05 * x
            return 0.5 * x

        state, env = self.owner(surface)
        house = self.house()
        self.assertEqual(16, env['HC_RING_CANDIDATES'])
        radii = sorted({round(math.dist((-13.5, 0.0), (state.HCRingOffset(0, c)[0], state.HCRingOffset(0, c)[2])), 3)
                        for c in range(16)})
        self.assertTrue(len(radii) >= 2 and max(radii) <= 12.0, radii)
        admissible = state.HCScreenRing(house)
        self.assertEqual(16, state.m_RingRises.Count())
        self.assertGreaterEqual(admissible, 2)
        first = state.HCNextRingCandidate()
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(state.m_RingRise, 0.25)
        self.assertAlmostEqual(0.06, state.m_RingRise, places=3)
        for local_z in (-3, 0, 3):
            offset = state.HCRingOffset(local_z, first)
            self.assertLess(offset[0] + 1.5, -10.5, 'never inside the barn/access strip')
            self.assertLess(bz + offset[2], bz - 2, 'flattest (south) patch chosen first')
        second = state.HCNextRingCandidate()
        self.assertNotEqual(first, second)
        self.assertTrue(0 <= state.m_RingRise <= 0.25)
        while state.HCNextRingCandidate() >= 0:
            pass
        self.assertEqual(-1, state.HCNextRingCandidate(), 'bounded: each candidate is tried once')

    def test_all_steep_ring_refuses_and_east_candidates_never_enter_the_barn(self):
        state, _ = self.owner(lambda x, z: 0.5 * x)
        self.assertEqual(0, state.HCScreenRing(self.house()))
        self.assertEqual(-1, state.HCNextRingCandidate())
        flat, _ = self.owner(lambda x, z: 0.0)
        flat.HCScreenRing(self.house())
        for candidate in range(16):
            east = flat.HCRingOffset(0, candidate)[0] + 1.5 >= -10.5
            if east:
                self.assertEqual(-1, flat.m_RingRises[candidate])

    def test_bushes_are_soft_vegetation_but_buildings_items_and_trees_block(self):
        state, _ = self.owner(lambda x, z: 0.0)
        thing = lambda bush=False, item=False: N(IsBush=lambda: bush, IsInventoryItem=lambda: item)
        self.assertTrue(state.HCSoftVegetation(thing(bush=True)))
        self.assertFalse(state.HCSoftVegetation(thing()))
        self.assertFalse(state.HCSoftVegetation(thing(bush=True, item=True)))
        self.assertFalse(state.HCSoftVegetation(None))
        source = (TRAVEL / 'HCShelterModule.c').read_text()
        self.assertNotIn('ObjectDelete(possibleOrphan', source, 'vegetation is never deleted')
        self.assertNotIn('ObjectDelete(blocker', source, 'vegetation is never deleted')


class RingArray(list):
    def Count(self): return len(self)
    def Insert(self, item): self.append(item)
    def Get(self, index): return self[index]
    def Set(self, index, value): self[index] = value
    def Clear(self): self.clear()


if __name__ == '__main__':
    unittest.main()
