"""C2 config behavioral checks. JSON/native ports are explicit synthetic fixtures.
No DayZ weather, display, audio or replication evidence.
"""
import functools
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
from tests.legacy.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'
CONFIG = ROOT / '4_World/Weather/HCWeatherConfig.c'
PRESENTATION = ROOT / '3_Game/Atmosphere/c2_AtmosConfig.c'


def config_fixture(kind, path=None, image='{}'):
    path = path or (CONFIG if kind == 'HCWeatherConfig' else PRESENTATION)
    source = path.read_text()
    start = source.index('class ' + kind + '\n')
    source = source[start:]
    source = source[:source.find('\nclass ', 1)] if '\nclass ' in source[1:] else source
    values = {k: json.loads(v) for _, k, v in re.findall(r'^    (float|int|bool) (\w+) = ([^;]+);', source, re.M)}
    config = N(**values)
    loaded = N(**{k: 0 for k in values})  # native missing fields zero-fill
    loaded.__dict__.update(json.loads(image))
    logs = []
    env = dict(Print=logs.append, HCJsonFields=N(Has=lambda text, key: key in json.loads(text)))
    config.HCApply = lambda text, raw: translate(source, 'HCApply', env, kind, member=True)(config, text, raw)
    config.HCApply(image, loaded)
    return config, logs


@functools.lru_cache(maxsize=1)
def defaults_env():
    return {kind: N(HCGet=lambda config=config_fixture(kind)[0]: config) for kind in
            ('HCWeatherConfig', 'HCc2PresentationConfig', 'HCc2SeasonTuning')}


class AtmosConfigBehavior(unittest.TestCase):
    def test_profile_override_changes_weather_and_invalid_falls_back(self):
        self.assertTrue(CONFIG.is_file(), 'weather profile override has no authored config path')
        source = (ROOT / '4_World/Weather/HCWeatherDays.c').read_text()
        for image, expected in (('{"BadDayBuckets":5}', 'bad'), ('{"BadDayBuckets":-1}', 'plain')):
            config, logs = config_fixture('HCWeatherConfig', image=image)
            policy = N()
            env = dict(HCWeatherDays=policy, HCWeatherConfig=N(HCGet=lambda: config),
                       HCAtmospherePolicy=N(IsNight=lambda hour: False, Finite=math.isfinite))
            for name in ('Seed', 'Profile'):
                setattr(policy, name, translate(source, name, env, 'HCWeatherDays'))
            day = next(day for day in range(20000, 20100) if policy.Seed(day) % 5 == 4)
            self.assertEqual(expected, policy.Profile(day, 12, 0))
            self.assertEqual(bool(logs), expected == 'plain')

    def test_optional_weather_profile_loader_and_bad_json_fallback(self):
        # Explicit synthetic native out-parameter adaptation: no filesystem or
        # JsonSerializer behavior is claimed. Authored HCLoad controls admission.
        original = CONFIG.read_text()
        source = original.replace('HCWeatherConfig', 'HCEventWeatherConfig')
        source = source.replace('string image;', 'string image = fixture_image;')
        source = source.replace('HCEventWeatherConfig loaded;', 'HCEventWeatherConfig loaded = fixture_loaded;')
        source = source.replace('JsonFileLoader<HCEventWeatherConfig>.LoadData(image, loaded, error)', 'fixture_parse(image)')
        for exists, parse_ok, expected in ((False, True, .55), (True, True, .3), (True, False, .55)):
            image = '{"NightCloudCap":0.3}'
            defaults, _ = config_fixture('HCWeatherConfig')
            loaded = N(**{key: 0 for key in vars(defaults) if key != 'HCApply'})
            loaded.NightCloudCap = .3
            reads, logs = [], []
            factory = lambda: config_fixture('HCWeatherConfig')[0]
            factory.READ_LIMIT = 8192  # fixed IO cap, never a tunable
            env = dict(HCEventWeatherConfig=factory,
                       FileExist=lambda path: exists,
                       HCGroupIO=N(Read=lambda path, cap, text: reads.append((path, cap)) or True),
                       fixture_image=image, fixture_loaded=loaded,
                       fixture_parse=lambda text: parse_ok, Print=logs.append)
            result = translate(source, 'HCLoad', env, 'HCEventWeatherConfig')()
            self.assertEqual(expected, result.NightCloudCap)
            self.assertEqual([('$profile:HollowCountry/weather.json', 8192)] if exists else [], reads)
            self.assertEqual(1 if exists and not parse_ok else 0, len(logs))

    def test_native_weather_defaults_use_the_same_threshold_override(self):
        from tests.legacy.test_v1_weather import authored
        config, _ = config_fixture('HCWeatherConfig', image='{"RainCloudThreshold":0.7,"StormCloudThreshold":0.9}')
        target = N(m_WeatherDefaultSettings=N())
        authored(ROOT / '4_World/Weather/HCChernarusAtmosphere.c', 'HCConfigureAtmosphereDefaults',
                 dict(HCWeatherConfig=N(HCGet=lambda: config), m_WeatherDefaultSettings=target.m_WeatherDefaultSettings), target)
        self.assertEqual(.7, target.m_WeatherDefaultSettings.m_RainThreshold)
        self.assertEqual(.9, target.m_WeatherDefaultSettings.m_StormThreshold)

    def test_all_tunables_preserve_missing_fields_and_reject_out_of_range(self):
        self.assertTrue(PRESENTATION.is_file(), 'presentation and season tuning DTOs missing')
        for kind in ('HCWeatherConfig', 'HCc2PresentationConfig', 'HCc2SeasonTuning'):
            baseline, _ = config_fixture(kind)
            numeric = {key: value for key, value in vars(baseline).items() if type(value) in (int, float)}
            self.assertGreater(len(numeric), 10)
            for key, value in numeric.items():
                with self.subTest(kind=kind, field=key):
                    changed, logs = config_fixture(kind, image=json.dumps({key: -999999}))
                    self.assertEqual(value, getattr(changed, key))
                    self.assertEqual(1, len(logs))
            unchanged, logs = config_fixture(kind)
            self.assertFalse(logs)
            for key, value in numeric.items():
                self.assertEqual(value, getattr(unchanged, key))

    def test_client_sound_schedule_and_grade_strength_override(self):
        from tests.legacy.test_v1_weather import authored
        cfg, _ = config_fixture('HCc2PresentationConfig', image='{"SoundStartupSeconds":12,"HowlGapMinSeconds":30,"HowlGapMaxSeconds":40,"GradeDesaturation":0.4}')
        env = dict(HCc2PresentationConfig=N(HCGet=lambda: cfg),
                   GetGame=lambda: N(GetTickTime=lambda: 100),
                   Math=N(RandomFloatInclusive=lambda lo, hi: lo,
                          Clamp=lambda value, lo, hi: max(lo, min(hi, value))))
        sound = N()
        translate((ROOT / '5_Mission/Atmosphere/HCEnvSound.c').read_text(),
                  'HCEnvSound', env, 'HCEnvSound', member=True)(sound)
        self.assertEqual(112, sound.m_NextLayer)
        self.assertEqual(130, sound.m_NextHowl)
        result = N()
        authored(ROOT / '3_Game/Atmosphere/HCGradePolicy.c', 'Evaluate', env,
                 None, 12, 0, 0, 0, 1, result)
        self.assertEqual(.4, result.Desaturation)

    def test_inverted_windows_and_equal_blend_edges_fall_back_once(self):
        for kind, image, keys in (
            ('HCWeatherConfig', '{"FogStartHour":10,"FogEndHour":6}', ('FogStartHour', 'FogEndHour')),
            ('HCWeatherConfig', '{"StormStartSeconds":6000}', ('StormStartSeconds',)),
            ('HCc2SeasonTuning', '{"SNAPSHOT_TTL_SECONDS":10}', ('SNAPSHOT_TTL_SECONDS',)),
            ('HCc2PresentationConfig', '{"LightDawnStart":6}', ('LightDawnStart',)),
            ('HCc2PresentationConfig', '{"HowlGapMinSeconds":1000}', ('HowlGapMinSeconds',)),
            ('HCc2PresentationConfig', '{"GradeDesaturation":1,"GradeDampDesaturation":1}', ('GradeDesaturation', 'GradeDampDesaturation')),
            ('HCc2PresentationConfig', '{"StormWeightBase":1}', ('StormWeightBase',))):
            config, logs = config_fixture(kind, image=image)
            baseline, _ = config_fixture(kind)
            self.assertEqual(1, len(logs))
            for key in keys:
                self.assertEqual(getattr(baseline, key), getattr(config, key))

    def test_season_and_client_overrides_reach_authored_policies(self):
        self.assertTrue(PRESENTATION.is_file(), 'presentation and season tuning DTOs missing')
        season, _ = config_fixture('HCc2SeasonTuning', image='{"AUTUMN_FOG_MIN":0.4}')
        source = (ROOT / '3_Game/Atmosphere/HCSeasonVisualPolicy.c').read_text()
        env = dict(HCc2SeasonTuning=N(HCGet=lambda: season))
        policy = N()
        env['HCSeasonVisualPolicy'] = policy
        for name in ('HCUnit', 'HCFog'):
            setattr(policy, name, translate(source, name, env, 'HCSeasonVisualPolicy'))
        self.assertEqual(.4, policy.HCFog('autumn', .04, False, False))
        cfg, _ = config_fixture('HCc2PresentationConfig', image='{"LightDawnStart":7,"LightDawnEnd":8}')
        source = (ROOT / '3_Game/Atmosphere/HCLightingBlend.c').read_text()
        daylight = translate(source, 'Daylight', dict(HCc2PresentationConfig=N(HCGet=lambda: cfg)), 'HCLightingBlend')
        self.assertEqual(0, daylight(6))
        self.assertEqual(.5, daylight(7.5))

if __name__ == '__main__':
    unittest.main()
