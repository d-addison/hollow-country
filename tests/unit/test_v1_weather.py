"""#35 explicit synthetic weather/native collaborators; never DayZ acceptance.

Scalar tests execute the authored policy with the fuel translator's binary32
rounding. Hook tests translate authored control flow, with native calls supplied
as explicit fixtures. Neither is an Enforce compiler or replication evidence.
"""
import ast
import math
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_crafting_completion import body
from tests.unit.test_core_lifecycle import tokens
from tests.unit.test_fuel_transfer import Binary32, FLOAT_MAX, f32

ROOT = Path(__file__).resolve().parents[2]
WEATHER = ROOT / 'mods/HollowCountry/scripts/4_World/Weather'
POLICY = WEATHER / 'HCAtmospherePolicy.c'
GATE = WEATHER / 'HCAtmosphereQualification.c'
WORLD = WEATHER / 'HCChernarusAtmosphere.c'


def authored_policy():
    source = re.sub(r'//[^\n]*', '', POLICY.read_text())
    namespace = {'__builtins__': {}, 'f32': f32, 'FLOAT_MAX': FLOAT_MAX,
                 'Math': NS(Floor=math.floor)}
    signatures = re.findall(r'static (bool|float) (\w+)\(([^)]*)\)', source)
    if not signatures or len(signatures) != len(re.findall(r'\bstatic\b', source)):
        raise AssertionError('unsupported policy declaration')
    for result, name, parameters in signatures:
        args = [p.strip().split()[-1] for p in parameters.split(',') if p.strip()]
        if any(not re.fullmatch(r'float \w+', p.strip()) for p in parameters.split(',') if p.strip()):
            raise AssertionError('unsupported policy parameter')
        text = re.sub(r'//[^\n]*', '', body(str(POLICY), name))
        if '{' in text or '}' in text:
            raise AssertionError('unsupported policy control flow')
        lines = [f'def {name}({",".join(args)}):']
        lines += [f'    {arg} = f32({arg})' for arg in args]
        for statement in text.split(';'):
            statement = statement.strip()
            if not statement:
                continue
            statement = statement.replace('HCAtmospherePolicy.', '').replace('float.MAX', 'FLOAT_MAX')
            statement = re.sub(r'^float (\w+) =', r'\1 =', statement)
            statement = statement.replace('&&', ' and ').replace('||', ' or ')
            statement = re.sub(r'!(?!=)', 'not ', statement)
            statement = re.sub(r'\btrue\b', 'True', statement)
            statement = re.sub(r'\bfalse\b', 'False', statement)
            statement = re.sub(r'^if \((.*)\)\s+(return .*|\w+ = .*)$',
                               r'if \1: \2', statement, flags=re.S)
            if not re.match(r'^(?:if |return |\w+ = )', statement):
                raise AssertionError('unsupported policy statement: ' + statement)
            if result == 'float':
                statement = re.sub(r'\breturn (.*)$', r'return f32(\1)', statement)
            lines.append('    ' + statement.replace('\n', ' '))
        tree = Binary32().visit(ast.parse('\n'.join(lines)))
        exec(compile(ast.fix_missing_locations(tree), str(POLICY), 'exec'), namespace)
    return NS(**{k: v for k, v in namespace.items() if callable(v)})


def authored(path, name, context, *args):
    """Mechanical language adapter, refusing unrecognized loops/control flow."""
    source = path.read_text()
    match = re.search(r'\b(?:bool|void|float) ' + name + r'\(([^)]*)\)', source)
    parameters = [p.strip().split()[-1] for p in match[1].split(',') if p.strip()]
    text = re.sub(r'//[^\n]*', '', body(str(path), name))
    literals = {}
    def literal(m):
        import json
        key = '_literal_' + str(len(literals))
        literals[key] = json.loads(m[0])
        return key
    text = re.sub(r'"(?:\\.|[^"\\])*"', literal, text)
    context.update(literals)
    def expression(value):
        value = re.sub(r'\b(?:bool|float|int|string|HCSettings|HCServer|NoiseSystem|ChernarusPlusData) (\w+) =', r'\1 =', value)
        value = re.sub(r'\bm_HC\w+\b', lambda m: 'self.' + m[0], value)
        value = value.replace('super.', 'base.')
        value = re.sub(r'(\w+)\.AsciiToString\(\)', r'chr(\1)', value)
        value = value.replace('&&', ' and ').replace('||', ' or ')
        value = re.sub(r'!(?!=)', 'not ', value)
        for old, new in [('true', 'True'), ('false', 'False'), ('null', 'None')]:
            value = re.sub(r'\b' + old + r'\b', new, value)
        return value
    lines, indent = [], 1
    for token in tokens(text):
        if token == '{': indent += 1; continue
        if token == '}': indent -= 1; continue
        conditional = token
        prefix = 'if '
        if token.startswith('else if ('):
            conditional = token[5:]
            prefix = 'elif '
        if conditional.startswith('if ('):
            depth = 0
            for index in range(3, len(conditional)):
                depth += (conditional[index] == '(') - (conditional[index] == ')')
                if depth == 0:
                    line = prefix + expression(conditional[4:index]) + ': ' + expression(conditional[index+1:].strip())
                    break
            else:
                raise AssertionError('unterminated guard')
        else:
            if re.search(r'\b(for|while|foreach|switch|catch)\b', token):
                raise AssertionError('unsupported control flow')
            line = expression(token)
            if line == 'else':
                line = 'else:'
            elif re.match(r'else\s+', line):
                line = 'else: ' + re.sub(r'^else\s+', '', line)
        lines.append('    '*indent + line.replace('\n', ' '))
    statics = sorted(set(re.findall(r'\bs_\w+', text)))
    globals_line = ['    global ' + ','.join(statics)] if statics else []
    exec(compile('def actual(self,' + ','.join(parameters) + '):\n' +
                 '\n'.join(globals_line + lines), str(path) + ':' + name, 'exec'), context)
    return context['actual'](*args)


class V1WeatherPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = authored_policy()

    def test_deterministic_storm_then_dry_calm_window(self):
        p = self.policy
        # Explicit seconds since server start, not invented engine forecasts.
        for seconds in (3600., 4499., 4500., 5399.):
            self.assertGreaterEqual(p.CloudTarget(seconds, 12.), .85)
        for seconds in (5400., 6000., 7199.):
            self.assertLess(p.CloudTarget(seconds, 12.), .65)
            self.assertEqual(0., p.RainTarget(p.CloudTarget(seconds, 12.)))
            self.assertLessEqual(p.WindTarget(p.CloudTarget(seconds, 12.)), 6.)
        self.assertEqual(p.CloudTarget(0., 12.), p.CloudTarget(7200., 12.))
        self.assertGreater(p.CloudTarget(0., 23.), p.CloudTarget(0., 12.))

    def test_morning_fog_is_stronger_and_wind_reduces_it(self):
        p = self.policy
        self.assertGreater(p.FogTarget(7.), p.FogTarget(12.))
        self.assertGreater(p.DistanceDensity(7., .5, 0.), p.DistanceDensity(12., .5, 0.))
        self.assertGreater(p.DistanceDensity(7., .5, 0.), p.DistanceDensity(7., .5, 16.))
        self.assertEqual(90., p.HeightBias(7.))
        self.assertEqual(50., p.HeightBias(12.))
        for hour in (0., 4.99, 5., 7., 8.99, 9., 12., 18., 23.99):
            self.assertLessEqual(p.FogTarget(hour), .25)
            self.assertGreaterEqual(p.DistanceDensity(hour, .5, 16.), 0.)
            self.assertLessEqual(p.DistanceDensity(hour, 1., 0.), .065001)

    def test_noise_reduction_only_shrinks_range_with_documented_floor(self):
        p = self.policy
        radii = [p.RelayRange(7.5, value) for value in (-5., 0., .25, 1., 2., 100., FLOAT_MAX)]
        self.assertEqual(7.5, radii[0])
        self.assertEqual(7.5, radii[1])
        self.assertAlmostEqual(6., radii[2])
        self.assertAlmostEqual(3.75, radii[3])
        self.assertTrue(all(x >= y for x, y in zip(radii, radii[1:])))
        self.assertAlmostEqual(7.5*.35, radii[-1], places=5)
        for bad in (math.nan, math.inf, -math.inf):
            self.assertAlmostEqual(7.5*.35, p.RelayRange(7.5, bad), places=5)
            self.assertEqual(0., p.RelayRange(bad, 0.))
        self.assertEqual(0., p.RelayRange(-1., 0.))

    def test_policy_envelopes_and_invalid_inputs_are_finite(self):
        p = self.policy
        for bad in (math.nan, math.inf, -math.inf, -1.):
            for method, args in [('CloudTarget', (bad, 12.)), ('FogTarget', (bad,)),
                                 ('RainTarget', (bad,)), ('WindTarget', (bad,)),
                                 ('DistanceDensity', (7., bad, 0.)), ('HeightBias', (bad,))]:
                self.assertTrue(math.isfinite(getattr(p, method)(*args)), method)
        for seconds in range(0, 14401, 90):
            for hour in (0., 7., 12., 23.):
                cloud = p.CloudTarget(float(seconds), hour)
                self.assertTrue(0 <= cloud <= 1)
                self.assertTrue(0 <= p.RainTarget(cloud) <= .900001)
                self.assertTrue(0 <= p.WindTarget(cloud) <= 16)


class V1WeatherAdmissionTests(unittest.TestCase):
    def context(self, enabled=True, server=True, started=True, marker=False, supported_world=True):
        events = []
        settings = NS(EnableAtmosphere=enabled)
        core = NS(IsStarted=lambda: started, GetSettings=lambda: settings)
        game = NS(IsServer=lambda: server)
        context = {'GetGame': lambda: game, 'HCServer': NS(Get=lambda: core),
                   'FileExist': lambda path: events.append(('probe', path)) or marker,
                   'Print': lambda text: events.append(('log', text)),
                   's_Probed': False, 's_OptIn': False, 's_Reported': False}
        gate = NS()
        context['HCAtmosphereQualification'] = gate
        gate.Qualified = lambda: authored(GATE, 'Qualified', context, None)
        gate.LocalOptIn = lambda: authored(GATE, 'LocalOptIn', context, None)
        gate.Enabled = lambda: authored(GATE, 'Enabled', context, None)
        gate.DelegatedWeather = lambda: True  # Explicit owned-XML native fixture.
        gate.SupportedWorld = lambda: supported_world
        return gate, context, events

    def test_qualification_stays_false_and_opt_in_is_probed_once(self):
        for marker in (False, True):
            gate, context, events = self.context(marker=marker)
            self.assertFalse(gate.Qualified())
            for _ in range(3):
                self.assertEqual(marker, gate.Enabled())
            probes = [e for e in events if e[0] == 'probe']
            self.assertEqual([('probe', '$profile:HollowCountry/acceptance/atmosphere.enable')], probes)
            self.assertTrue(any(('EXPERIMENTAL' if marker else 'PENDING') in e[1]
                                for e in events if e[0] == 'log'))
            context['FileExist'] = lambda path: not marker
            self.assertEqual(marker, gate.Enabled(), 'marker changes require process restart')

    def test_disabled_client_or_unstarted_core_never_probes_or_mutates(self):
        for change in ({'enabled': False}, {'server': False}, {'started': False}, {'supported_world': False}):
            gate, _, events = self.context(marker=True, **change)
            self.assertFalse(gate.Enabled())
            self.assertFalse(any(e[0] == 'probe' for e in events))

    def test_unadmitted_forecasts_delegate_to_vanilla_without_writes(self):
        calls = []
        context = {'HCAtmosphereQualification': NS(Enabled=lambda: False),
                   'base': NS(WeatherOnBeforeChange=lambda *args: calls.append(args) or False)}
        self.assertFalse(authored(WORLD, 'WeatherOnBeforeChange', context, NS(), 0, .2, .1, 30.))
        self.assertEqual([(0, .2, .1, 30.)], calls)

    def test_owned_forecasts_use_only_the_requested_native_phenomenon(self):
        enum_names = ('OVERCAST', 'RAIN', 'FOG', 'WIND_MAGNITUDE', 'WIND_DIRECTION',
                      'SNOWFALL', 'VOLFOG_HEIGHT_DENSITY', 'VOLFOG_DISTANCE_DENSITY', 'VOLFOG_HEIGHT_BIAS')
        kinds = NS(**{name: name for name in enum_names})
        calls = []
        def phenomenon(name):
            return NS(GetActual=lambda: .95, Set=lambda *args: calls.append((name, args)))
        weather = NS(GetTime=lambda: 4000., GetWindSpeed=lambda: 14.)
        for name in ('Overcast', 'Rain', 'Fog', 'WindMagnitude', 'WindDirection', 'Snowfall'):
            setattr(weather, 'Get' + name, lambda name=name: phenomenon(name))
        context = {'GetGame': lambda: NS(GetDayTime=lambda: 7.),
                   'HCAtmospherePolicy': authored_policy(), 'EWeatherPhenomenon': kinds,
                   'm_Weather': weather, 'CalculateVolFog': lambda *args: calls.append(('volfog', args))}
        for kind, target in [('OVERCAST', 'Overcast'), ('RAIN', 'Rain'), ('FOG', 'Fog'),
                             ('WIND_MAGNITUDE', 'WindMagnitude'), ('WIND_DIRECTION', 'WindDirection'),
                             ('SNOWFALL', 'Snowfall')]:
            calls.clear()
            self.assertTrue(authored(WORLD, 'HCForecast', context, NS(), kind))
            self.assertEqual([target, 'volfog'], [row[0] for row in calls])
            self.assertTrue(all(0 <= x <= 600 for x in calls[0][1][1:]))
        calls.clear()
        self.assertFalse(authored(WORLD, 'HCForecast', context, NS(), 'unknown'))
        self.assertEqual([], calls)

    def test_owned_forecast_does_not_call_the_vanilla_driver(self):
        calls = []
        context = {'HCAtmosphereQualification': NS(Enabled=lambda: True),
                   'HCStartAtmosphere': lambda: True,
                   'HCForecast': lambda kind: calls.append(kind) or True,
                   'base': NS(WeatherOnBeforeChange=lambda *args: self.fail('second driver'))}
        self.assertTrue(authored(WORLD, 'WeatherOnBeforeChange', context, NS(), 'FOG', .2, .1, 30.))
        self.assertEqual(['FOG'], calls)

    def test_startup_blocks_foreign_drivers_and_uses_synced_native_lighting_once(self):
        for mission, frozen in ((True, False), (False, True), (False, False)):
            calls = []
            weather = NS(GetMissionWeather=lambda: mission, GetWeatherUpdateFrozen=lambda: frozen,
                         SetWindMaximumSpeed=lambda *args: calls.append(('maxwind', args)),
                         SetStorm=lambda *args: calls.append(('storm', args)),
                         SetRainThresholds=lambda *args: calls.append(('rain-thresholds', args)),
                         GetWindSpeed=lambda: 4., IsDynVolFogEnabled=lambda: True)
            for name in ('Overcast', 'Rain', 'Fog', 'WindMagnitude', 'WindDirection', 'Snowfall'):
                setattr(weather, 'Get' + name, lambda name=name: NS(
                    SetLimits=lambda *args: calls.append(('limits-' + name, args)), GetActual=lambda: .35))
            data = NS(WorldsData=NS(lightingConfig=0, environmentMinTemps=[-3.]*12),
                      PlayerData=NS(disablePersonalLight=False))
            context = {'m_Weather': weather,
                       'm_WeatherDefaultSettings': NS(m_StormThreshold=.85, m_RainThreshold=.65),
                       'HCAtmosphereQualification': NS(Enabled=lambda: True),
                       'HCConfigureAtmosphereDefaults': lambda: calls.append(('defaults', ())),
                       'HCForecast': lambda kind: calls.append(('forecast', kind)),
                       'CalculateVolFog': lambda *args: calls.append(('volfog', args)),
                       'CfgGameplayHandler': NS(m_Data=data), 'Print': lambda msg: None,
                       'EWeatherPhenomenon': NS(**{name: name for name in
                           ('OVERCAST', 'RAIN', 'FOG', 'WIND_MAGNITUDE', 'WIND_DIRECTION', 'SNOWFALL')})}
            actor = NS(m_HCAtmosphereStarted=False)
            result = authored(WORLD, 'HCStartAtmosphere', context, actor)
            self.assertEqual(not (mission or frozen), result)
            if mission or frozen:
                self.assertEqual([], calls)
                self.assertEqual(0, data.WorldsData.lightingConfig)
                self.assertFalse(data.PlayerData.disablePersonalLight)
            else:
                self.assertEqual(1, data.WorldsData.lightingConfig)
                self.assertTrue(data.PlayerData.disablePersonalLight)
                self.assertEqual([-3.]*12, data.WorldsData.environmentMinTemps)
                count = len(calls)
                self.assertTrue(authored(WORLD, 'HCStartAtmosphere', context, actor))
                self.assertEqual(count, len(calls))

    def test_new_scripts_follow_installed_native_statement_shapes(self):
        from tools.setup.probe_runtime import lint_hook, native_type_names
        from tools.setup.weather_probe import max_plus_per_statement
        cache = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
        names = native_type_names(cache) if cache.is_dir() else frozenset()
        for path in sorted(WEATHER.glob('*.c')):
            with self.subTest(path=path.name):
                self.assertEqual([], lint_hook(path.read_text(), native_types=names, explicit_numbers=True))
                self.assertLessEqual(max_plus_per_statement(path.read_text()), 8)

    def test_volumetric_fog_delegates_when_unadmitted_and_bounds_native_writes(self):
        calls = []
        enabled = [False]
        available = [True]
        weather = NS(IsDynVolFogEnabled=lambda: available[0],
                     SetDynVolFogDistanceDensity=lambda *args: calls.append(('distance', args)),
                     SetDynVolFogHeightDensity=lambda *args: calls.append(('height', args)),
                     SetDynVolFogHeightBias=lambda *args: calls.append(('bias', args)))
        context = {'HCAtmosphereQualification': NS(Enabled=lambda: enabled[0]),
                   'base': NS(CalculateVolFog=lambda *args: calls.append(('vanilla', args))),
                   'm_Weather': weather, 'HCAtmospherePolicy': authored_policy(),
                   'GetGame': lambda: NS(GetDayTime=lambda: 7.)}
        actor = NS(m_HCAtmosphereStarted=True)
        authored(WORLD, 'CalculateVolFog', context, actor, .5, 0., 100.)
        self.assertEqual([('vanilla', (.5, 0., 100.))], calls)
        enabled[0] = True
        calls.clear()
        authored(WORLD, 'CalculateVolFog', context, actor, .5, 0., math.inf)
        self.assertEqual(['distance', 'height', 'bias'], [row[0] for row in calls])
        self.assertAlmostEqual(.06, calls[0][1][0], places=5)
        self.assertEqual(90., calls[2][1][0])
        self.assertTrue(all(row[1][1] == 300 for row in calls))
        calls.clear()
        available[0] = False
        authored(WORLD, 'CalculateVolFog', context, actor, .5, 0., 300.)
        self.assertEqual([], calls)

    def test_delegation_probe_is_bounded_once_and_rejects_comment_spoofing(self):
        from tools.package.atmosphere import SCRIPT_XML_PREFIX
        class NativeText(str):
            def Length(self): return len(self)
            def IndexOf(self, text): return self.find(text)
        # ReadFile's native out parameter is mechanically adapted to a return.
        import tempfile
        for document, expected in ((SCRIPT_XML_PREFIX.decode() + '</weather>', True),
                                   ('<!--' + SCRIPT_XML_PREFIX.decode() + '--><weather enable="1">', False),
                                   (SCRIPT_XML_PREFIX.decode() + ' ' * 65537, False), ('', False)):
            calls = []
            context = {'s_WeatherProbed': False, 's_Delegated': False,
                       'OpenFile': lambda *args: calls.append(('open', args)) or 1,
                       'CloseFile': lambda handle: calls.append(('close', handle)),
                       'ReadFile': lambda handle, limit: calls.append(('read', limit)) or NativeText(document[:limit]),
                       'FileMode': NS(READ=1), 'Print': lambda msg: calls.append(('log', msg))}
            source = GATE.read_text().replace('FileHandle weatherHandle =', 'int weatherHandle =')
            source = source.replace('string weatherDocument;', '')
            source = source.replace('ReadFile(weatherHandle, weatherDocument, 65537);',
                                    'string weatherDocument = ReadFile(weatherHandle, 65537);')
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'gate.c'
                path.write_text(source)
                for _ in range(3):
                    self.assertEqual(expected, authored(path, 'DelegatedWeather', context, None))
            self.assertEqual(1, sum(e[0] == 'open' for e in calls))
            self.assertEqual([65537], [e[1] for e in calls if e[0] == 'read'])

    def test_native_range_is_sampled_at_emission_source_and_disabled_is_identity(self):
        calls = []
        policy = authored_policy()
        noise = NS(GetEnvironmentNoiseReduction=lambda position: calls.append(position) or 1.)
        enabled = [False]
        context = {'HCAtmosphereQualification': NS(Enabled=lambda: enabled[0]),
                   'GetGame': lambda: NS(GetNoiseSystem=lambda: noise),
                   'HCAtmospherePolicy': policy}
        relay = WEATHER / 'HCAtmosphereRelay.c'
        origin = (100., 25., 100.)
        self.assertEqual(7.5, authored(relay, 'RangeAtSource', context, None, 7.5, origin))
        self.assertEqual([], calls)
        enabled[0] = True
        self.assertEqual(3.75, authored(relay, 'RangeAtSource', context, None, 7.5, origin))
        self.assertEqual([origin], calls)

    def test_source_wiring_limits_scope_and_uses_native_sync(self):
        settings = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        self.assertEqual(1, settings.count('bool EnableAtmosphere = true;'))
        alert = (ROOT / 'mods/HollowCountry/scripts/4_World/Infected/HCAlertChain.c').read_text()
        self.assertIn('radius = HCAtmosphereRelay.RangeAtSource(radius, emission.Clue.Origin);', alert)
        source = '\n'.join(p.read_text() for p in WEATHER.glob('*.c'))
        for unwanted in ('extends HCModule', 'RegisterModules', 'SetBrightness(', 'LoadNewLightingCfg(', 'AddNoiseTarget('):
            self.assertNotIn(unwanted, source)
        self.assertIn('CfgGameplayHandler.m_Data.WorldsData.lightingConfig = 1;', source)
        self.assertIn('CfgGameplayHandler.m_Data.PlayerData.disablePersonalLight = true;', source)
        self.assertIn('GetMissionWeather()', source)
        self.assertIn('GetWeatherUpdateFrozen()', source)
        self.assertIn('$mission:cfgweather.xml', source)
        self.assertIn('ReadFile(', source)
        self.assertIn('65537', source)
        self.assertIn('modded class ChernarusPlusData', source)
        self.assertIn('override void SetupWeatherSettings()', source)
        self.assertIn('override void CalculateVolFog(float lerpValue, float windMagnitude, float changeTime)', source)


if __name__ == '__main__':
    unittest.main()
