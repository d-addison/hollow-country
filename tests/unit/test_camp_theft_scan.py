"""#209: the camp theft scan continues past candidate-specific refusals.

Executes the authored HCCampTheft.Step with explicit synthetic ports; nothing
here establishes DayZ behaviour.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_admin_test_kit import base_scope, compile_authored
from tests.unit.test_debug_map_layers import EArray

THEFT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Camps/HCCampTheft.c'


class CampTheftScan(unittest.TestCase):
    def run_step(self, crates, eligible, pickup, budget=99):
        refusals, picked = [], []
        work = [budget]
        def take(cost):
            work[0] -= cost
            return work[0] >= 0
        def pick(module, camp, crate, now, limit):
            picked.append(crate)
            return pickup.get(crate, '')
        trip = N(m_IO=N(HCTheftCamp=None, HCTheftNear=lambda crate: True), m_Ready=True,
                 m_State=N(Phase='leaving'), HCTheftPickup=pick)
        scope = base_scope(HCPickers=N(Get=lambda: N(HCTrip=lambda: trip)),
                           HCServer=N(HCTickWork=lambda: N(HCTake=take)))
        step = compile_authored(THEFT, 'HCCampTheft', 'Step', scope,
                                ('HCEnabled', 'Due', 'HCRefuse', 'HCAllowed', 'Candidate', 'HCCandidateRefusal'),
                                modded=False, fields=('s_Config',))
        receiver = N(HCEnabled=lambda: True, Due=lambda now, last: True, HCRefuse=refusals.append,
                     HCAllowed=lambda *args: True, Candidate=lambda crate, *args: crate in eligible,
                     s_Config=N(MaxAttemptsPerDay=1))
        candidate = compile_authored(THEFT, 'HCCampTheft', 'HCCandidateRefusal', scope, modded=False)
        receiver.HCCandidateRefusal = lambda reason: candidate(None, reason)
        camp = N(LastTheft=0)
        step(receiver, N(), camp, N(Crates=EArray(crates)), 86400)
        return refusals, picked

    def test_ineligible_first_crate_does_not_hide_a_later_valid_crate(self):
        refusals, picked = self.run_step(['locked', 'open'], eligible={'open'}, pickup={})
        self.assertEqual(['open'], picked)
        self.assertEqual([''], refusals)

    def test_empty_or_home_crates_are_skipped_but_global_faults_stop(self):
        refusals, picked = self.run_step(['empty', 'home', 'good'], eligible={'empty', 'home', 'good'},
                                         pickup={'empty': 'THEFT_SAFE_STOCK_ABSENT', 'home': 'THEFT_SOURCE_IS_HOME'})
        self.assertEqual(['empty', 'home', 'good'], picked)
        self.assertEqual([''], refusals)
        refusals, picked = self.run_step(['a', 'b'], eligible={'a', 'b'}, pickup={'a': 'THEFT_DAILY_CAP'})
        self.assertEqual(['a'], picked)
        self.assertEqual(['THEFT_DAILY_CAP'], refusals)

    def test_scan_stays_bounded_by_shared_work_and_reports_last_candidate_refusal(self):
        refusals, picked = self.run_step(['x', 'y'], eligible=set(), pickup={})
        self.assertEqual([], picked)
        self.assertEqual(['THEFT_CAMP_INELIGIBLE'], refusals)
        refusals, picked = self.run_step(['x', 'y', 'z'], eligible={'z'}, pickup={}, budget=2)
        self.assertEqual([], picked)
        self.assertEqual(['THEFT_WORK_BUDGET'], refusals)


if __name__ == '__main__':
    unittest.main()
