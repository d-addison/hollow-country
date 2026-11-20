"""#190: caravan provider handles are dropped on every non-active leg.

Synthetic ports execute the authored HCXAIAdapter.HCDropCaravanHandles body.
Dropping a handle only clears script references; no entity is deleted, moved or
duplicated. Nothing observed in DayZ yet.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_hc_scavenge import bind

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIAdapter.c'
ACTIVE = ('outbound', 'fleeing_outbound', 'return_pending', 'fleeing_return_pending',
          'returning', 'fleeing_returning')
INACTIVE = ('idle', 'quarantined', 'lost')


def fixture(leg, held=True):
    logs, deleted = [], []
    port = N(LeftActor='actor' if held else None, RightActor=None,
             LeftItem='item' if held else None, RightItem=None)

    def clear():
        port.LeftActor = port.RightActor = port.LeftItem = port.RightItem = None
    port.HCClear = clear
    caravan = N(m_IO=port, m_State=N(Leg=leg), HCActive=lambda: leg in ACTIVE)
    owner = N(m_Caravan=caravan)
    bind(ADAPTER.read_text(), 'HCXAIAdapter', owner, ('HCDropCaravanHandles',),
         dict(Print=logs.append, str=str))
    return owner, port, logs, deleted


class CaravanHandleRelease(unittest.TestCase):
    def test_every_inactive_leg_drops_held_handles(self):
        for leg in INACTIVE:
            with self.subTest(leg=leg):
                owner, port, logs, _ = fixture(leg)
                owner.HCDropCaravanHandles()
                self.assertEqual((None, None), (port.LeftActor, port.LeftItem))
                self.assertEqual(1, len(logs))
                self.assertIn('runtime=PENDING', logs[0])

    def test_active_leg_keeps_the_handles_it_needs(self):
        for leg in ACTIVE:
            with self.subTest(leg=leg):
                owner, port, logs, _ = fixture(leg)
                owner.HCDropCaravanHandles()
                self.assertEqual(('actor', 'item'), (port.LeftActor, port.LeftItem))
                self.assertEqual([], logs)

    def test_returned_leg_keeps_handles_for_the_unload_check(self):
        # HCConfirmedReturn needs LeftActor on Leg == "returned"; dropping
        # it in the same tick would make the unload unreachable.
        owner, port, logs, _ = fixture('returned')
        owner.HCDropCaravanHandles()
        self.assertEqual(('actor', 'item'), (port.LeftActor, port.LeftItem))
        self.assertEqual([], logs)

    def test_idle_tick_without_handles_is_a_silent_no_op(self):
        owner, port, logs, _ = fixture('idle', held=False)
        port.HCClear = lambda: self.fail('nothing held, nothing to clear')
        for _ in range(5): owner.HCDropCaravanHandles()
        self.assertEqual([], logs)

    def test_missing_caravan_port_or_state_is_tolerated(self):
        owner, port, logs, _ = fixture('idle')
        owner.m_Caravan.m_IO = None
        owner.HCDropCaravanHandles()
        owner.m_Caravan = None
        owner.HCDropCaravanHandles()
        self.assertEqual([], logs)

    def test_tick_releases_after_step_and_never_deletes(self):
        source = ADAPTER.read_text()
        self.assertIn('m_Caravan.Step();\n            this.HCDropCaravanHandles();', source)
        start = source.index('void HCDropCaravanHandles')
        body = source[start:source.index('override string GetName', start)]
        for forbidden in ('Delete', 'SetPosition', 'CreateObject', 'ServerDrop', 'TakeTo'):
            self.assertNotIn(forbidden, body)


if __name__ == '__main__':
    unittest.main()
