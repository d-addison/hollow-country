"""#185.3: the HC-36 caravan status publisher must not retry a full owner registry
every tick, yet must keep observing so HC-1 freshness does not go stale.

Synthetic fixture: the authored HCXAIOperationalAdapters.c publisher runs through
the shared translator with fake ports. Nothing observed in DayZ yet.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_hc_scavenge import bind

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXOperationalAdapters.c'


class CaravanStatusPublish(unittest.TestCase):
    def run_ticks(self, full):
        registrations, observations = [], []
        values = ['refused', 'CARAVAN_PROVIDER_CALLBACKS_UNVERIFIED']
        status = N(HCState=lambda: values[0], HCReason=lambda: values[1])
        owner = N(m_CaravanOperationalOwner=None, m_CaravanRequested=True,
                  m_CaravanRegistrationTried=False,
                  m_Caravan=N(HCGetOperationalStatus=lambda: status, m_Ready=False,
                              m_ProviderRefusal=values[1], HCActive=lambda: False))

        def register(name):
            registrations.append(name)
            if full:
                return None
            return N(HCObserve=lambda *args: observations.append(tuple(values)))

        source = SOURCE.read_text().replace('    protected ref HCOperationalOwner',
            '    ref HCAICaravan m_Caravan;\n    bool m_CaravanRequested;\n    protected ref HCOperationalOwner', 1)
        bind(source, 'HCXAIAdapter', owner, ('HCPublishCaravanStatus',),
             dict(HCOperationalContributors=N(HCRegisterOwner=register),
                  GetGame=lambda: N(GetTickTime=lambda: 100), Print=lambda line: None, str=str))
        owner.HCPublishCaravanStatus(True)
        for _ in range(100):
            owner.HCPublishCaravanStatus(False)
        values[1] = 'CARAVAN_JOURNAL_UNCERTAIN'
        owner.HCPublishCaravanStatus(False)
        return registrations, observations

    def test_full_registry_is_tried_once_per_boot_not_every_tick(self):
        registrations, observations = self.run_ticks(full=True)
        self.assertEqual(1, len(registrations), 'a full owner registry must not be retried every tick')
        self.assertEqual([], observations)

    def test_registered_owner_is_observed_every_tick_so_freshness_holds(self):
        registrations, observations = self.run_ticks(full=False)
        self.assertEqual(1, len(registrations))
        self.assertEqual(102, len(observations), 'HC-1 freshness needs an observation every tick')
        self.assertEqual(('refused', 'CARAVAN_JOURNAL_UNCERTAIN'), observations[-1])


if __name__ == '__main__':
    unittest.main()
