"""Explicit synthetic JSON/Enforce scalar fixtures; no DayZ runtime evidence.
Spec/plan/tasks: migrate audited infected knobs, preserve defaults, validate each
field, exercise profile overrides and fallbacks through shipped policy bodies.
"""
import json
from functools import lru_cache
import math
import re
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / 'mods/HollowCountry/scripts/4_World/Infected'
TUNING = AREA / 'c1InfectedTunables.c'


def config_fixture(profile='{}', variety=False):
    """Synthetic native zero-fill for present blocks, omitted blocks are null."""
    text = TUNING.read_text()
    data = json.loads(profile)
    classes = {}
    for name, body in re.findall(r'class (HCC1\w+)\s*\{(.*?)\n\}', text, re.S):
        fields = re.findall(r'^    (int|float) (\w+) = ([\d.]+);', body, re.M)
        if not fields:
            continue
        values = {key: float(value) if typ == 'float' else int(value) for typ, key, value in fields}
        classes[name] = (body, values)
    logs = []
    guard = N(s_Invalid=False)
    env = dict(HCC1Range=guard, Print=logs.append, Math=N(Min=min, Max=max, Clamp=lambda x,a,b: max(a,min(b,x)), Floor=math.floor, Round=lambda x: math.floor(x+.5)))
    guard.Value = translate(text.replace('s_Invalid = true;', 'HCC1Range.s_Invalid = true;'), 'Value', env, 'HCC1Range')
    config = N()
    blocks = ('GroupScaling', 'Variety') if variety else ('Doors', 'Reach', 'Vision', 'Memory', 'Chain', 'Navigation', 'LOD')
    for block in blocks:
        body, defaults = classes['HCC1' + block]
        supplied = data.get('LevelOfDetail' if block == 'LOD' else block)
        obj = N(**defaults)
        if supplied is not None:
            for key in defaults:
                setattr(obj, key, supplied.get(key, 0))
        normalized = body
        for key in defaults:
            normalized = re.sub(r'(?<![\w.])' + key + r'\b', 'self.' + key, normalized)
        normalizer = translate(normalized, 'Normalize', env, member=True)
        obj.Normalize = lambda target=obj, fn=normalizer: fn(target)
        obj.Normalize()
        setattr(config, 'LevelOfDetail' if block == 'LOD' else block, obj)
    config.HordeCooldownSeconds = guard.Value(data.get('HordeCooldownSeconds', 180), 1, 86400, 180)
    return config, logs


@lru_cache(maxsize=16)
def tuning_fixture(profile='{}', variety_profile='{}'):
    # Reader fixtures share immutable tuning; mutation tests use config_fixture().
    config, _ = config_fixture(profile)
    variety, _ = config_fixture(variety_profile, True)
    return N(Get=lambda: config, Variety=lambda: variety)


class InfectedConfigTests(unittest.TestCase):
    def test_profile_changes_horde_reuse_and_invalid_falls_back(self):
        text = (AREA / 'HCInfectedPolicy.c').read_text()
        for value, expected in ((45, 45), (-2, 180), (0, 180), (999999, 180)):
            tuning = tuning_fixture(json.dumps({'HordeCooldownSeconds': value}))
            policy = N()
            env = dict(HCInfectedTuning=tuning, HCInfectedPolicy=policy)
            policy.HordeCooldownSeconds = translate(text, 'HordeCooldownSeconds', env, 'HCInfectedPolicy')
            policy.MayReuseHorde = translate(text, 'MayReuseHorde', env, 'HCInfectedPolicy')
            self.assertEqual(expected, policy.HordeCooldownSeconds())
            self.assertFalse(policy.MayReuseHorde(5, True, 100, 100 + expected - 1))
            self.assertTrue(policy.MayReuseHorde(5, True, 100, 100 + expected))

    def test_profile_changes_perception_memory_and_group_scaling(self):
        tuning = tuning_fixture('{"Vision":{"DarkFactor":0.5},"Memory":{"DecaySeconds":100}}', '{"GroupScaling":{"Solo":0.9}}')
        env = dict(HCInfectedTuning=tuning, Math=N(Clamp=lambda x,a,b: max(a,min(b,x))))
        vision = N(Finite=lambda x: math.isfinite(x))
        env['HCInfectedVisionPolicy'] = vision
        dark = translate((AREA/'HCInfectedVision.c').read_text(), 'DarknessFactor', env, 'HCInfectedVisionPolicy')
        self.assertEqual(.5, dark(1))
        decay = translate((AREA/'HCInfectedMemory.c').read_text(), 'Decayed', env, 'HCInfectedMemory')
        self.assertEqual(.5, decay(1, 50))
        scale = translate((AREA/'Variety/HCInfectedVarietyPolicy.c').read_text(), 'GroupScale', env)
        self.assertEqual(.9, scale(1))

    def test_profile_changes_door_reach_chain_and_conservative_lod_decisions(self):
        tuning = tuning_fixture(json.dumps({'Doors': {'WatchRadius': 3},
            'Reach': {'ElevatedMax': 1.8}, 'Chain': {'Attenuation': .25},
            'LevelOfDetail': {'ObserverSpeed': 90}}))
        env = dict(HCInfectedTuning=tuning)
        door = translate((AREA/'Doors/HCInfectedDoorPolicy.c').read_text(), 'PlayerQualifies', env)
        self.assertFalse(door(16, -1))
        elevated = translate((AREA/'Reach/HCInfectedReachPolicy.c').read_text(), 'Elevated', env)
        self.assertFalse(elevated(2))
        attenuate = translate((AREA/'HCInfectedPolicy.c').read_text(), 'Attenuate', env)
        self.assertEqual(.125, attenuate(.5))
        far = translate((AREA.parent/'Core/HCLODPolicy.c').read_text(), 'SafelyFar', env)
        self.assertFalse(far(190, 1, 100))
        env['HCInfectedTuning'] = tuning_fixture()
        self.assertTrue(door(16, -1))
        self.assertTrue(elevated(2))
        self.assertEqual(.25, attenuate(.5))
        self.assertTrue(far(190, 1, 100))

    def test_every_numeric_field_has_fallback_and_range(self):
        text = TUNING.read_text()
        for name, body in re.findall(r'class (HCC1\w+)\s*\{(.*?)\n\}', text, re.S):
            for field in re.findall(r'^    (?:int|float) (\w+) = ', body, re.M):
                self.assertRegex(body, rf'{field} = HCC1Range.Value\({field},', name + '.' + field)
        cfg, _ = config_fixture('{"Doors":{"WatchRadius":-1},"Reach":{"ElevatedMin":99999}}')
        self.assertEqual(8, cfg.Doors.WatchRadius)
        self.assertEqual(.8, cfg.Reach.ElevatedMin)

    def test_all_blocks_default_invalid_numeric_overrides(self):
        text = TUNING.read_text()
        for block, body in re.findall(r'class HCC1(\w+)\s*\{(.*?)\n\}', text, re.S):
            fields = re.findall(r'^    (?:int|float) (\w+) = ([\d.]+);', body, re.M)
            if not fields:
                continue
            variety = block in ('Variety', 'GroupScaling')
            for field, default in fields:
                for invalid in (-1, 0, 1e20):
                    with self.subTest(block=block, field=field, invalid=invalid):
                        config, _ = config_fixture(json.dumps({'LevelOfDetail' if block == 'LOD' else block: {field: invalid}}), variety)
                        member = 'LevelOfDetail' if block == 'LOD' else block
                        self.assertEqual(float(default), getattr(getattr(config, member), field))

    def test_owner_normalization_publishes_and_logs_bad_input_once(self):
        config, _ = config_fixture()
        config.Doors.WatchRadius = -2
        config.s_HCTuningInvalidLogged = False
        text = (AREA / 'HCInfectedState.c').read_text()
        fields = ('HordeCooldownSeconds', 'Doors', 'Reach', 'Vision', 'Memory',
                  'Chain', 'Navigation', 'LevelOfDetail', 's_HCTuningInvalidLogged')
        for field in fields:
            text = re.sub(r'(?<![\w.])' + field + r'\b', 'self.' + field, text)
        logs, published = [], []
        guard = N(s_Invalid=False)
        env = dict(HCC1Range=guard, HCInfectedTuning=N(Set=published.append), Print=logs.append)
        guard.Value = translate(TUNING.read_text().replace('s_Invalid = true;', 'HCC1Range.s_Invalid = true;'), 'Value', env, 'HCC1Range')
        # Block normalizers share their explicit scalar guard, just as native statics do.
        block_guard = config.Doors.Normalize.__defaults__[1].__globals__['HCC1Range']
        env['HCC1Range'] = block_guard
        normalizer = translate(text, 'HCNormalizeTunables', env, member=True)
        normalizer(config)
        self.assertEqual(8, config.Doors.WatchRadius)
        self.assertEqual(['[HC Infected] tunables=invalid_fields_defaulted runtime=PENDING'], logs)
        self.assertIs(config, published[-1])
        config.Doors.WatchRadius = -2
        normalizer(config)
        self.assertEqual(1, len(logs))


if __name__ == '__main__':
    unittest.main()
