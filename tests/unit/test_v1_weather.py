"""#35 explicit synthetic weather/native collaborators; never DayZ acceptance.

Scalar tests execute the authored policy with the fuel translator's binary32
rounding. Hook tests translate authored control flow, with native calls supplied
as explicit fixtures. Neither is an Enforce compiler or replication evidence.
"""
import ast
from itertools import product
import math
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_crafting_completion import body
from tests.unit.test_core_lifecycle import tokens
from tests.unit.test_fuel_transfer import Binary32, FLOAT_MAX, f32
from tests.unit.build_identity_support import translate as build_identity

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
        value = re.sub(r'\b(?:bool|float|int|string|HCSettings|HCServer|NoiseSystem|ChernarusPlusData|Mission|FileHandle) (\w+) =', r'\1 =', value)
        # Explicit native out-string and in-place string operations, without
        # replacing any authored admission decisions.
        value = re.sub(r'^string (\w+)$', r'\1 = ""', value)
        value = re.sub(r'^GetGame\(\)\.(GetVersion|GetWorldName)\((\w+)\)$',
                       r'\2 = GetGame().\1()', value)
        value = re.sub(r'^(\w+)\.ToLower\(\)$', r'\1 = \1.lower()', value)
        value = re.sub(r'^ReadFile\((\w+), (\w+), (\d+)\)$', r'\2 = ReadFile(\1, \3)', value)
        value = re.sub(r'(\w+)\.Length\(\)', r'len(\1)', value)
        value = re.sub(r'(\w+)\.IndexOf\(', r'\1.find(', value)
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

    def test_exact_cycle_bands_and_scalar_constants(self):
        p = self.policy
        for seconds, expected in ((-1, 0), (0, 0), (7199, 7199), (7200, 0),
                                  (7201, 1), (14401, 1), (31536000, 0), (31536004, 0)):
            self.assertEqual(expected, p.CyclePosition(seconds))
        for phase, expected in ((0, .35), (2699, .35), (2700, .72), (3599, .72),
                                (3600, .95), (5399, .95), (5400, .25), (7199, .25)):
            self.assertEqual(f32(expected), p.CloudTarget(phase, 12))
        # Owner decision 2026-11-17: never dark nights. Dusk to dawn (20..5) caps cloud
        # at .55; day bands are untouched and out-of-range hours count as day.
        for hour in (0, 4.5, 20, 23, 23.9):
            self.assertEqual(f32(.35), p.CloudTarget(0, hour))
            self.assertEqual(f32(.55), p.CloudTarget(3600, hour))
            self.assertEqual(f32(.55), p.CloudTarget(2700, hour))
            self.assertEqual(f32(.25), p.CloudTarget(5400, hour))
        for hour in (-1, 5, 5.5, 12, 19.5, 24, math.inf, math.nan):
            self.assertEqual(f32(.35), p.CloudTarget(0, hour))
            self.assertEqual(f32(.72), p.CloudTarget(2700, hour))
            self.assertEqual(f32(.95), p.CloudTarget(3600, hour))
            self.assertEqual(f32(.25), p.CloudTarget(5400, hour))
        for cloud, rain, wind in ((-.1, 0, 4), (0, 0, 4), (.6, 0, 4), (.65, .25, 8),
                                  (.84, .25, 8), (.85, .85, 14), (1, .85, 14), (1.1, 0, 4)):
            self.assertEqual(f32(rain), p.RainTarget(cloud))
            self.assertEqual(wind, p.WindTarget(cloud))
        for phase, direction in ((0, -1.2), (3599, -1.2), (3600, .8), (5399, .8), (5400, -1.2)):
            self.assertEqual(f32(direction), p.WindDirectionTarget(phase))
        for hour, weight in ((4.5, 0), (5, 0), (6, .5), (7, 1), (7.5, .75),
                              (8, .5), (9, 0), (9.5, 0)):
            self.assertEqual(weight, p.MorningWeight(hour))
            self.assertAlmostEqual(.04 + weight * .20, p.FogTarget(hour), places=7)
            self.assertEqual(50 + 40 * weight, p.HeightBias(hour))
        for cloud in (-1, 0, .5, 1, 2, math.nan):
            for wind in (-1, 0, 8, 16, 20, math.inf, math.nan):
                clean_cloud = cloud if 0 <= cloud <= 1 else 0
                clean_wind = min(wind, 16) if math.isfinite(wind) and wind >= 0 else 16
                expected = (.015 + .04 + .01 * clean_cloud) * (1 - clean_wind / 20)
                self.assertAlmostEqual(expected, p.DistanceDensity(7, cloud, wind), places=7)
        for request, expected in ((-1, 300), (0, 0), (300, 300), (900, 900), (1000, 900), (math.inf, 300)):
            self.assertEqual(expected, p.TransitionTime(request))
        for value in (math.nan, math.inf, -math.inf):
            self.assertFalse(p.Finite(value))

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
        # Daytime storms are unchanged; the night storm band is capped below rain.
        for hour in (5., 12., 19.9):
            self.assertEqual(f32(.95), p.CloudTarget(3600., hour))
            self.assertEqual(f32(.85), p.RainTarget(p.CloudTarget(3600., hour)))
        for hour in (0., 3., 4.9, 20., 23., 23.9):
            for seconds in (0., 2700., 3600., 4499., 5399., 5400., 7199.):
                cloud = p.CloudTarget(seconds, hour)
                self.assertLessEqual(cloud, f32(.55), (seconds, hour))
                self.assertEqual(0., p.RainTarget(cloud))
                self.assertEqual(4, p.WindTarget(cloud))
            for seconds in (0., 2699., 5400., 7199.):
                self.assertEqual(p.CloudTarget(seconds, 12.), p.CloudTarget(seconds, hour))
        # Lagging actual cloud (storm cloud still present at dusk) is capped too.
        for hour in (0., 4.9, 20., 23.):
            self.assertEqual(f32(.55), p.NightCapped(.95, hour))
            self.assertEqual(f32(.35), p.NightCapped(.35, hour))
            self.assertEqual(0., p.RainTarget(p.NightCapped(.95, hour)))
        for hour in (5., 12., 19.9, 24., -1.):
            self.assertEqual(f32(.95), p.NightCapped(.95, hour))

    def test_night_window_and_cap_constants(self):
        p = self.policy
        self.assertEqual(f32(.55), p.NightCloudCap())
        for hour in (0., 4.99, 20., 23.99):
            self.assertTrue(p.IsNight(hour), hour)
        for hour in (5., 12., 19.99, 24., -1., math.inf, math.nan):
            self.assertFalse(p.IsNight(hour), hour)

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
    def native_context(self, world='chernarusplus', build='1.30.164289.70',
                       document=None, missing=False, server=True):
        from tools.package.atmosphere import SCRIPT_XML_PREFIX
        events = []
        if document is None:
            document = SCRIPT_XML_PREFIX.decode() + '</weather>'
        core = NS(IsStarted=lambda: True, GetSettings=lambda: NS(EnableAtmosphere=True))
        game = NS(IsServer=lambda: server, GetWorldName=lambda: world,
                  GetVersion=lambda: events.append(('version',)) or build)
        context = dict(GetGame=lambda: game, HCBuildIdentity=build_identity(), HCServer=NS(Get=lambda: core),
                       FileExist=lambda path: False, FileMode=NS(READ=1),   # no atmosphere.disable file: default open
                       OpenFile=lambda *args: events.append(('open', args)) or (0 if missing else 1),
                       ReadFile=lambda handle, limit: events.append(('read', limit)) or document[:limit],
                       CloseFile=lambda handle: events.append(('close', handle)),
                       Print=lambda msg: events.append(('log', msg)))
        for flag in ('Probed', 'OptIn', 'Reported', 'WeatherProbed', 'Delegated', 'WorldProbed', 'WorldSupported'):
            context['s_' + flag] = False
        gate = NS()
        for name in ('Qualified', 'SupportedWorld', 'LocalOptIn', 'DelegatedWeather', 'Enabled'):
            setattr(gate, name, lambda name=name: authored(GATE, name, context, None))
        context['HCAtmosphereQualification'] = gate
        return gate, context, events

    def test_authored_world_and_exact_engine_build_gate_are_cached(self):
        for world in ('chernarusplus', 'ChernarusPlus', 'enoch', 'sakhal', ''):
            for build in ('1.30.164289', '1.30.164289.70', '', '1.30.164289.71',
                          '1.30.164289.70extra', '1.30.1642890', '1.31.164289'):
                with self.subTest(world=world, build=build):
                    gate, _, events = self.native_context(world=world, build=build)
                    expected = world.lower() == 'chernarusplus' and build in ('1.30.164289', '1.30.164289.70')
                    for _ in range(3):
                        self.assertEqual(expected, gate.SupportedWorld())
                    self.assertEqual(1, events.count(('version',)))

    def test_enabled_executes_delegation_and_server_guards(self):
        from tools.package.atmosphere import SCRIPT_XML_PREFIX
        for missing, document, expected in ((True, '', False), (False, '', False),
                (False, '<weather enable="1" reset="0"></weather>', False),
                (False, SCRIPT_XML_PREFIX.decode() + '</weather>', True)):
            gate, _, events = self.native_context(document=document, missing=missing)
            for _ in range(3):
                self.assertEqual(expected, gate.Enabled())
            self.assertEqual(1, sum(e[0] == 'open' for e in events))
            self.assertEqual(0 if missing else 1, sum(e[0] == 'read' for e in events))
        gate, _, events = self.native_context(server=False)
        self.assertFalse(gate.LocalOptIn())
        self.assertFalse(gate.Enabled())
        self.assertEqual([], events)

    def test_lifecycle_calls_super_first_and_starts_only_supported_world_data(self):
        for world in ('chernarusplus', 'ChernarusPlus', 'enoch', 'sakhal', ''):
            for enabled, mission_present, castable in ((False, True, True), (True, True, True),
                                                       (True, False, True), (True, True, False)):
                with self.subTest(world=world, enabled=enabled, mission=mission_present, castable=castable):
                    calls = []
                    data = NS(HCStartAtmosphere=lambda: calls.append('atmosphere'))
                    mission = NS(GetWorldData=lambda: calls.append('world-data') or data) if mission_present else None
                    game = NS(GetWorldName=lambda: world, GetMission=lambda: calls.append('mission') or mission)
                    context = dict(GetGame=lambda: game, base=NS(Start=lambda: calls.append('super')),
                        HCAtmosphereQualification=NS(Enabled=lambda: calls.append('enabled') or enabled),
                        ChernarusPlusData=NS(Cast=lambda value: value if castable else None),
                        Print=lambda msg: None)
                    authored(WEATHER / 'HCAtmosphereLifecycle.c', 'Start', context, NS())
                    expected = ['super', 'enabled']
                    if enabled and world.lower() == 'chernarusplus':
                        expected += ['mission']
                        if mission_present:
                            expected += ['world-data']
                            if castable:
                                expected += ['atmosphere']
                    self.assertEqual(expected, calls)

    def context(self, enabled=True, server=True, started=True, disabled=False, supported_world=True):
        events = []
        settings = NS(EnableAtmosphere=enabled)
        core = NS(IsStarted=lambda: started, GetSettings=lambda: settings)
        game = NS(IsServer=lambda: server)
        context = {'GetGame': lambda: game, 'HCBuildIdentity': build_identity(), 'HCServer': NS(Get=lambda: core),
                   'FileExist': lambda path: events.append(('probe', path)) or disabled,   # True = atmosphere.disable exists
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

    def test_qualification_stays_false_and_default_open_disable_probe_is_once(self):
        for disabled in (False, True):
            gate, context, events = self.context(disabled=disabled)
            self.assertFalse(gate.Qualified())
            for _ in range(3):
                self.assertEqual(not disabled, gate.Enabled())      # default with no marker is OPEN
            probes = [e for e in events if e[0] == 'probe']
            self.assertEqual([('probe', '$profile:HollowCountry/acceptance/atmosphere.disable')], probes)
            self.assertTrue(any(('PENDING' if disabled else 'EXPERIMENTAL') in e[1]
                                for e in events if e[0] == 'log'))
            context['FileExist'] = lambda path: not disabled
            self.assertEqual(not disabled, gate.Enabled(), 'marker changes require process restart')

    def test_disabled_client_or_unstarted_core_never_probes_or_mutates(self):
        for change in ({'enabled': False}, {'server': False}, {'started': False}, {'supported_world': False}):
            gate, _, events = self.context(**change)
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
            expected = dict(OVERCAST=(f32(.95), 300, 300), RAIN=(f32(.85), 180, 120),
                            FOG=(f32(f32(.04) + f32(.20)), 300, 0), WIND_MAGNITUDE=(14, 180, 120),
                            WIND_DIRECTION=(f32(.8), 300, 300), SNOWFALL=(0, 300, 300))
            self.assertEqual(expected[kind], calls[0][1])
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

    def test_night_forecasts_cap_cloud_rain_and_wind_even_with_lagging_storm_cloud(self):
        enum_names = ('OVERCAST', 'RAIN', 'FOG', 'WIND_MAGNITUDE', 'WIND_DIRECTION',
                      'SNOWFALL', 'VOLFOG_HEIGHT_DENSITY', 'VOLFOG_DISTANCE_DENSITY', 'VOLFOG_HEIGHT_BIAS')
        kinds = NS(**{name: name for name in enum_names})
        calls = []
        def phenomenon(name):
            return NS(GetActual=lambda: .95, Set=lambda *args: calls.append((name, args)))
        weather = NS(GetTime=lambda: 4000., GetWindSpeed=lambda: 14.)
        for name in ('Overcast', 'Rain', 'Fog', 'WindMagnitude', 'WindDirection', 'Snowfall'):
            setattr(weather, 'Get' + name, lambda name=name: phenomenon(name))
        context = {'GetGame': lambda: NS(GetDayTime=lambda: 22.),
                   'HCAtmospherePolicy': authored_policy(), 'EWeatherPhenomenon': kinds,
                   'm_Weather': weather, 'CalculateVolFog': lambda *args: calls.append(('volfog', args))}
        for kind, expected in (('OVERCAST', (f32(.55), 300, 300)), ('RAIN', (0, 180, 120)),
                               ('WIND_MAGNITUDE', (4, 180, 120))):
            calls.clear()
            self.assertTrue(authored(WORLD, 'HCForecast', context, NS(), kind))
            self.assertEqual(expected, calls[0][1], kind)

    def night_world(self, daytime, actual, server=True, started=True):
        """Synthetic native collaborators; never evidence of DayZ clamp timing."""
        state = NS(day=daytime, actual=actual)
        calls = []
        overcast = NS(GetActual=lambda: state.actual,
                      SetLimits=lambda low, high: calls.append(('limits', low, high)),
                      Set=lambda *args: calls.append(('set',) + args))
        context = {'GetGame': lambda: NS(GetDayTime=lambda: state.day, IsServer=lambda: server),
                   'HCAtmospherePolicy': authored_policy(),
                   'm_Weather': NS(GetOvercast=lambda: overcast)}
        actor = NS(m_HCAtmosphereStarted=started, m_HCNightLimited=False)
        def apply(force):
            return authored(WORLD, 'HCApplyNightLimits', context, actor, force)
        return state, calls, actor, apply

    def test_startup_at_night_during_a_storm_caps_actual_overcast_natively(self):
        state, calls, actor, apply = self.night_world(22., .95)
        apply(True)
        self.assertEqual([('limits', 0, f32(.55)), ('set', f32(.55), 60, 60)], calls)
        self.assertTrue(actor.m_HCNightLimited)

    def test_startup_at_night_with_clear_sky_limits_without_forcing_a_change(self):
        state, calls, actor, apply = self.night_world(2., .35)
        apply(True)
        self.assertEqual([('limits', 0, f32(.55))], calls)

    def test_dusk_boundary_caps_storm_cloud_once_and_is_idempotent(self):
        state, calls, actor, apply = self.night_world(19.99, .95)
        apply(True)
        self.assertEqual([('limits', 0, 1)], calls)
        calls.clear()
        apply(False)
        self.assertEqual([], calls)
        state.day = 20.
        apply(False)
        self.assertEqual([('limits', 0, f32(.55)), ('set', f32(.55), 60, 60)], calls)
        calls.clear()
        for hour in (20., 22., 1., 4.99):
            state.day = hour
            apply(False)
        self.assertEqual([], calls)

    def test_dawn_boundary_restores_daytime_limits_once(self):
        state, calls, actor, apply = self.night_world(4.99, .5)
        apply(True)
        calls.clear()
        state.day = 5.
        apply(False)
        self.assertEqual([('limits', 0, 1)], calls)
        self.assertFalse(actor.m_HCNightLimited)
        calls.clear()
        state.day = 12.
        apply(False)
        self.assertEqual([], calls)

    def test_daytime_start_leaves_limits_full_and_never_forces_a_forecast(self):
        state, calls, actor, apply = self.night_world(12., .95)
        apply(True)
        self.assertEqual([('limits', 0, 1)], calls)
        self.assertFalse(actor.m_HCNightLimited)

    def test_night_limits_are_server_only_and_need_the_started_chernarus_owner(self):
        for server, started in ((False, True), (True, False), (False, False)):
            state, calls, actor, apply = self.night_world(22., .95, server=server, started=started)
            apply(True)
            apply(False)
            self.assertEqual([], calls)
            self.assertFalse(actor.m_HCNightLimited)

    def stop_world(self, daytime=22., actual=.95):
        """Queue-aware synthetic fixture: Remove drops the queued callback."""
        state, calls, actor, apply = self.night_world(daytime, actual)
        queue = []
        context = {'GetGame': lambda: NS(GetDayTime=lambda: state.day, IsServer=lambda: True,
                       GetCallQueue=lambda category: NS(Remove=lambda fn: queue.remove(fn) if fn in queue else None,
                                                        category=category)),
                   'CALL_CATEGORY_SYSTEM': 1,
                   'HCAtmospherePolicy': authored_policy(), 'm_Weather': NS(GetOvercast=lambda: NS(
                       GetActual=lambda: state.actual, SetLimits=lambda *a: calls.append(('limits',) + a),
                       Set=lambda *a: calls.append(('set',) + a)))}
        def callback(force):
            return authored(WORLD, 'HCApplyNightLimits', context, actor, force)
        queue.append(callback)
        context['HCApplyNightLimits'] = callback
        stop = lambda: authored(WORLD, 'HCStopAtmosphere', context, actor)
        return state, calls, actor, queue, callback, stop, context

    def test_stopped_owner_removes_the_dusk_callback_and_a_late_run_writes_nothing(self):
        state, calls, actor, queue, callback, stop, context = self.stop_world(19.99, .95)
        stop()
        self.assertEqual([], queue)
        self.assertFalse(actor.m_HCAtmosphereStarted)
        state.day = 20.
        callback(False)
        callback(True)
        self.assertEqual([], calls)
        stop()
        self.assertEqual([], queue)

    def test_dusk_callback_does_nothing_without_a_game_instance(self):
        state, calls, actor, queue, callback, stop, context = self.stop_world(22., .95)
        context['GetGame'] = lambda: None
        callback(True)
        self.assertEqual([], calls)

    def test_stop_uses_the_queue_category_that_scheduled_the_callback(self):
        source = WORLD.read_text()
        self.assertEqual(1, source.count('GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCApplyNightLimits'))
        self.assertEqual(1, source.count('GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCApplyNightLimits)'))

    def test_server_stop_stops_atmosphere_then_super_and_tolerates_other_worlds(self):
        for mission_present, castable in ((True, True), (False, True), (True, False)):
            calls = []
            data = NS(HCStopAtmosphere=lambda: calls.append('atmosphere-stop'))
            mission = NS(GetWorldData=lambda: data) if mission_present else None
            game = NS(GetMission=lambda: mission)
            context = dict(GetGame=lambda: game, base=NS(Stop=lambda: calls.append('super')),
                           ChernarusPlusData=NS(Cast=lambda value: value if castable else None))
            authored(WEATHER / 'HCAtmosphereLifecycle.c', 'Stop', context, NS())
            expected = ['atmosphere-stop', 'super'] if mission_present and castable else ['super']
            self.assertEqual(expected, calls, (mission_present, castable))
        context = dict(GetGame=lambda: None, base=NS(Stop=lambda: calls.append('late')),
                       ChernarusPlusData=NS(Cast=lambda value: value))
        calls.clear()
        authored(WEATHER / 'HCAtmosphereLifecycle.c', 'Stop', context, NS())
        self.assertEqual(['late'], calls)

    def test_startup_registers_one_boundary_check_and_non_chernarus_registers_none(self):
        source = WORLD.read_text()
        self.assertEqual(1, source.count('CallLater(HCApplyNightLimits, 10000, true, false)'))
        self.assertNotIn('SetLimits(0, 1);\n        m_Weather.GetFog', source)
        lifecycle = (WEATHER / 'HCAtmosphereLifecycle.c').read_text()
        self.assertNotIn('CallLater', lifecycle)

    def test_startup_blocks_foreign_drivers_and_uses_synced_native_lighting_once(self):
        for (mission, frozen), lighting, personal, daytime in product(
                ((True, False), (False, True), (False, False)), (0, 1, 2, 3, 7), (False, True), (12., 22.)):
            calls, logs, later = [], [], []
            weather = NS(GetMissionWeather=lambda: mission, GetWeatherUpdateFrozen=lambda: frozen,
                         SetWindMaximumSpeed=lambda *args: calls.append(('maxwind', args)),
                         SetStorm=lambda *args: calls.append(('storm', args)),
                         SetRainThresholds=lambda *args: calls.append(('rain-thresholds', args)),
                         GetWindSpeed=lambda: 4., IsDynVolFogEnabled=lambda: True)
            for name in ('Overcast', 'Rain', 'Fog', 'WindMagnitude', 'WindDirection', 'Snowfall'):
                setattr(weather, 'Get' + name, lambda name=name: NS(
                    SetLimits=lambda *args: calls.append(('limits-' + name, args)), GetActual=lambda: .35))
            data = NS(WorldsData=NS(lightingConfig=lighting, environmentMinTemps=[-3.]*12),
                      PlayerData=NS(disablePersonalLight=personal))
            context = {'m_Weather': weather,
                       'm_WeatherDefaultSettings': NS(m_StormThreshold=.85, m_RainThreshold=.65),
                       'HCAtmosphereQualification': NS(Enabled=lambda: True),
                       'HCConfigureAtmosphereDefaults': lambda: calls.append(('defaults', ())),
                       'HCForecast': lambda kind: calls.append(('forecast', kind)),
                       'CalculateVolFog': lambda *args: calls.append(('volfog', args)),
                       'GetGame': lambda: NS(GetDayTime=lambda: daytime, IsServer=lambda: True,
                           GetCallQueue=lambda category: NS(CallLater=lambda *args: later.append(args))),
                       'CALL_CATEGORY_SYSTEM': 1, 'HCAtmospherePolicy': authored_policy(),
                       'CfgGameplayHandler': NS(m_Data=data), 'Print': lambda msg: None,
                       'PrintFormat': lambda fmt, value: logs.append((fmt, value)),
                       'EWeatherPhenomenon': NS(**{name: name for name in
                           ('OVERCAST', 'RAIN', 'FOG', 'WIND_MAGNITUDE', 'WIND_DIRECTION', 'SNOWFALL')})}
            context['HCConfigureAtmosphereDefaults'] = lambda: (calls.append(('defaults', ())),
                authored(WORLD, 'HCConfigureAtmosphereDefaults', context, None))
            actor = NS(m_HCAtmosphereStarted=False, m_HCNightLimited=False)
            context['HCApplyNightLimits'] = lambda force: authored(
                WORLD, 'HCApplyNightLimits', context, actor, force)
            result = authored(WORLD, 'HCStartAtmosphere', context, actor)
            self.assertEqual(not (mission or frozen), result)
            if mission or frozen:
                self.assertEqual([], calls)
                self.assertEqual([], later)
                self.assertEqual(lighting, data.WorldsData.lightingConfig)
                self.assertEqual(personal, data.PlayerData.disablePersonalLight)
                self.assertEqual([], logs)
            else:
                # Owner rule: never dark nights; lightingConfig is forced to 0 whatever
                # the operator value is. The personal light is never written.
                self.assertEqual(0, data.WorldsData.lightingConfig)
                self.assertEqual(personal, data.PlayerData.disablePersonalLight)
                self.assertEqual(2, len(logs))
                self.assertEqual('[HollowCountry][Atmosphere] lightingConfig previous=%1; forcing 0 (bright nights, owner rule)', logs[0][0])
                self.assertNotIn('retained', logs[0][0])
                self.assertEqual(lighting, logs[0][1])
                self.assertIn('disablePersonalLight', logs[1][0])
                self.assertIn('untouched', logs[1][0])
                self.assertNotIn('applying true', logs[1][0])
                self.assertEqual(personal, logs[1][1])
                self.assertEqual(dict(m_RainThreshold=.65, m_StormThreshold=.85,
                    m_OvercastMinTime=300, m_OvercastMaxTime=300,
                    m_OvercastMinLength=300, m_OvercastMaxLength=300,
                    m_CalmAfterStormTimeMin=1800, m_CalmAfterStormTimeMax=1800,
                    m_DefaultHeigthBias=50, m_GlobalSuddenChance=0, m_BadWeatherSuddenChance=0),
                    vars(context['m_WeatherDefaultSettings']))
                self.assertEqual([('limits-Overcast', (0, 1 if daytime == 12. else f32(.55))), ('limits-Fog', (0, .25)),
                    ('limits-Rain', (0, .9)), ('limits-Snowfall', (0, 0)),
                    ('limits-WindMagnitude', (0, 16)), ('limits-WindDirection', (-3.14159, 3.14159)),
                    ('maxwind', (16,)), ('storm', (1, .85, 90)), ('rain-thresholds', (.65, 1, 90))],
                    [row for row in calls if row[0] not in ('defaults', 'forecast', 'volfog')])
                self.assertEqual(['OVERCAST', 'RAIN', 'FOG', 'WIND_MAGNITUDE', 'WIND_DIRECTION', 'SNOWFALL'],
                    [row[1] for row in calls if row[0] == 'forecast'])
                self.assertEqual([-3.]*12, data.WorldsData.environmentMinTemps)
                self.assertEqual([(context['HCApplyNightLimits'], 10000, True, False)], later)
                count = len(calls)
                self.assertTrue(authored(WORLD, 'HCStartAtmosphere', context, actor))
                self.assertEqual(1, len(later))
                self.assertEqual(count, len(calls))
                self.assertEqual(2, len(logs))

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
        actor.m_HCAtmosphereStarted = False
        calls.clear()
        authored(WORLD, 'CalculateVolFog', context, actor, .5, 0., 100.)
        self.assertEqual([('vanilla', (.5, 0., 100.))], calls)
        actor.m_HCAtmosphereStarted = True
        calls.clear()
        authored(WORLD, 'CalculateVolFog', context, actor, .5, 0., math.inf)
        self.assertEqual(['distance', 'height', 'bias'], [row[0] for row in calls])
        self.assertAlmostEqual(.06, calls[0][1][0], places=5)
        self.assertEqual(.95, calls[1][1][0])
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

    def test_missing_noise_system_preserves_vanilla_and_logs_once(self):
        logs = []
        scope = dict(HCAtmosphereQualification=NS(Enabled=lambda: True),
                     GetGame=lambda: NS(GetNoiseSystem=lambda: None),
                     HCAtmospherePolicy=authored_policy(), s_NoiseReported=False,
                     Print=logs.append)
        relay = WEATHER / 'HCAtmosphereRelay.c'
        for radius in (7.5, 0, 15):
            self.assertEqual(radius, authored(relay, 'RangeAtSource', scope, None, radius, (1, 2, 3)))
        self.assertEqual(1, len(logs))
        self.assertIn('vanilla', logs[0])

    def test_available_noise_system_keeps_relay_range_guards(self):
        scope = dict(HCAtmosphereQualification=NS(Enabled=lambda: True),
                     GetGame=lambda: NS(GetNoiseSystem=lambda: NS(GetEnvironmentNoiseReduction=lambda pos: 1)),
                     HCAtmospherePolicy=authored_policy())
        for radius in (-1, math.nan, math.inf, -math.inf):
            self.assertEqual(0, authored(WEATHER / 'HCAtmosphereRelay.c', 'RangeAtSource', scope, None, radius, (1, 2, 3)))

    def test_source_wiring_limits_scope_and_uses_native_sync(self):
        settings = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        self.assertEqual(1, settings.count('bool EnableAtmosphere = true;'))
        alert = (ROOT / 'mods/HollowCountry/scripts/4_World/Infected/HCAlertChain.c').read_text()
        self.assertIn('radius = HCAtmosphereRelay.RangeAtSource(radius, emission.Clue.Origin);', alert)
        # #61 adds a separately admitted V2 module; keep this v1 ownership pin.
        source = '\n'.join(p.read_text() for p in WEATHER.glob('*.c')
                           if not p.name.startswith('HCWeatherDays'))
        for unwanted in ('extends HCModule', 'RegisterModules', 'SetBrightness(', 'LoadNewLightingCfg(', 'AddNoiseTarget('):
            self.assertNotIn(unwanted, source)
        self.assertIn('CfgGameplayHandler.m_Data.WorldsData.lightingConfig = 0;', source)
        self.assertNotIn('lightingConfig = 1;', source)
        self.assertNotIn('operator-set; retained', source)
        self.assertNotIn('disablePersonalLight = true;', source)
        self.assertNotIn('PlayerData.disablePersonalLight =', source)
        self.assertIn('GetMissionWeather()', source)
        self.assertIn('GetWeatherUpdateFrozen()', source)
        self.assertIn('$mission:cfgweather.xml', source)
        self.assertIn('ReadFile(', source)
        self.assertIn('65537', source)
        self.assertIn('modded class ChernarusPlusData', source)
        self.assertNotIn('override void SetupWeatherSettings()', source)
        self.assertIn('override void CalculateVolFog(float lerpValue, float windMagnitude, float changeTime)', source)


if __name__ == '__main__':
    unittest.main()
