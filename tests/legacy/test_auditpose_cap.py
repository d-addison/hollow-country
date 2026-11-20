"""#225 spec/plan/tasks: configurable server-wide pose slots.

Execute authored Enforce on explicit synthetic native/storage ports. Cover a
nondefault cap, zero opt-out, zero-fill defaults, bounds, and release at capacity.
No test establishes DayZ animation, timing, replication or engine behavior.
"""
import json
import unittest
from types import SimpleNamespace as N

from tests.legacy.test_auditpose_riser import POSE, VARIETY, ROOT, admission
from tests.legacy.test_infected_admission import translate


class PoseCap(unittest.TestCase):
    def test_nondefault_cap_is_shared_and_cleanup_does_not_need_a_slot(self):
        logs = []
        state = N(s_HCPosed=0, s_HCLastRefusal='')
        limit = [2]
        env = dict(STATICS=state, MAX_POSED=12, Print=logs.append,
                   g_Game=N(IsServer=lambda: True),
                   HCPostureAdmission=admission(),
                   HCInfectedVariety=N(HCMaxPosed=lambda: limit[0]))
        request = translate(str(POSE), 'bool HCRequestPose(', ('IsAlive', 'HCRefusePose'),
                            statics=('s_HCPosed', 's_HCLastRefusal'), **env)
        release = translate(str(POSE), 'void HCRelease(', (), statics=('s_HCPosed', 's_HCLastRefusal'), **env)
        def actor():
            return N(m_HCPose=0, m_HCHolding=False, m_HCRising=False,
                     m_HCStarted=False, IsAlive=lambda: True, HCRefusePose=lambda p: False)
        first, second, third = actor(), actor(), actor()
        self.assertTrue(request(first, 1))
        self.assertTrue(request(second, 1))
        self.assertFalse(request(third, 1), 'configured cap 2 must refuse the third pose')
        self.assertEqual(2, state.s_HCPosed)
        self.assertFalse(request(third, 1), 'repeated full-budget request remains refused')
        self.assertEqual(1, sum('max_posed_budget=2' in line for line in logs))
        self.assertTrue(request(first, 1), 'existing hold consumes no second slot')
        limit[0] = 0
        self.assertFalse(request(third, 1), 'zero opts out')
        self.assertTrue(request(first, 0), 'cleanup still starts rise with cap zero')
        self.assertEqual(2, state.s_HCPosed, 'rise retains its slot until release')
        release(first)
        release(first)
        self.assertEqual(1, state.s_HCPosed, 'release must be idempotent')
        limit[0] = 2
        self.assertTrue(request(third, 1))
        self.assertEqual(2, state.s_HCPosed)

    def test_missing_key_defaults_but_explicit_zero_and_invalid_values_survive(self):
        defaults = translate(str(VARIETY), 'void HCApplyOptionalDefaults(', (),
            fields=('PosedFreshEvery', 'MaxPosed'),
            HCJsonFields=N(Has=lambda content, key: key in json.loads(content)),
            HCInfectedVarietyPolicy=N(DEFAULT_POSED_FRESH_EVERY=3))
        for data, expected in (({}, 12), ({'MaxPosed': 0}, 0),
                               ({'MaxPosed': 5}, 5), ({'MaxPosed': -1}, -1),
                               ({'MaxPosed': 65}, 65)):
            config = N(PosedFreshEvery=0, MaxPosed=data.get('MaxPosed', 0))
            defaults(config, json.dumps(data), False)
            self.assertEqual(expected, config.MaxPosed)

    def test_bounds_and_live_getter_fail_closed_when_owner_is_inactive(self):
        valid = translate(str(VARIETY), 'bool HCMaxPosedValid(', (), fields=('MaxPosed',))
        for value in (-1, 0, 1, 12, 64, 65):
            self.assertEqual(0 <= value <= 64, valid(N(MaxPosed=value)))
        state = N(s_Running=True, s_Config=N(MaxPosed=7))
        getter = translate(str(VARIETY), 'static int HCMaxPosed(', (),
                           statics=tuple(vars(state)), STATICS=state)
        self.assertEqual(7, getter(None))
        state.s_Running = False
        self.assertEqual(0, getter(None))
        state.s_Running, state.s_Config = True, None
        self.assertEqual(0, getter(None))

    def test_shipped_default_and_named_refusal_are_wired(self):
        data = json.loads((ROOT / 'mission/hollow-country/infected/variety-runtime.json').read_text())
        self.assertEqual(12, data.get('MaxPosed'))
        source = VARIETY.read_text()
        self.assertIn('!config.HCMaxPosedValid()', source)
        self.assertIn('variety_max_posed_out_of_range', source)
        self.assertIn('!HCMaxPosedValid()', source)
        self.assertIn('max_posed=', source)
        self.assertNotIn('MAX_POSED', POSE.read_text())


if __name__ == '__main__':
    unittest.main()
