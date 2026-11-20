"""W1.7 map information layers (known events, visited places, toggles).

Authored static/instance methods are executed through a deliberately small
EnScript-to-Python adapter that only supplies syntax and explicit synthetic
native types (string, arrays, DTO rows). It decides no layer policy itself and
is never DayZ/engine acceptance.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.legacy import test_v1_groups
from tests.legacy.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry'
GROUPS = ROOT / 'scripts/5_Mission/Groups'
INFO = GROUPS / 'HCInfoLayers.c'
LAYOUT = ROOT / 'gui/layouts/hc_info_layers.layout'


class EStr(str):
    """Synthetic native string methods (EnString.c IndexOf/Substring/...)."""
    def IndexOf(self, sample): return self.find(sample)
    def IndexOfFrom(self, start, sample): return self.find(sample, start)
    def Substring(self, start, length): return EStr(self[start:start + length])
    def Length(self): return len(self)
    def Trim(self): return EStr(self.strip())
    def Contains(self, sample): return sample in self
    def Get(self, index): return EStr(self[index])
    def ToFloat(self):
        try:
            return float(self)
        except ValueError:
            return 0.0
    def __add__(self, other): return EStr(str.__add__(self, str(other)))
    def __radd__(self, other): return EStr(str(other) + str(self))


class Row(NS):
    pass


def methods(source, class_name):
    start = re.search(r'\bclass ' + class_name + r'\b[^{]*\{', source)
    if not start:
        raise AssertionError('Missing authored class: ' + class_name)
    text = body(source, start.end())
    found = {}
    fields = re.findall(r'^    (?:ref |protected )*(?:bool|int|float|string|vector|[A-Z]\w*(?:<[^>]*>)?) (\w+)\s*(?:=[^;]+)?;', text, re.M)
    for match in re.finditer(r'^    (static )?(?:ref )?(?:\w+<[^>]*>|\w+) (\w+)\(([^)]*)\)\s*\{', text, re.M):
        found[match[2]] = (bool(match[1]), match[3], body(text, match.end()))
    return found, fields


def translate(source, class_name, env, self_obj=None, only=None):
    table, fields = methods(source, class_name)
    keys = {}

    def literal(match):
        key = '_lit_%d' % len(keys)
        keys[key] = EStr(json.loads(match[0]))
        return key

    for name, (static, params, code) in table.items():
        if only and name not in only:
            continue
        code = re.sub(r'//[^\n]*', '', code)
        code = re.sub(r'"(?:\\.|[^"\\])*"', literal, code)
        code = re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)', r'foreach (int \1 : indices(\2, \3))', code)
        lines = []
        indent = 1
        for token in re.split(r'([{};])', code):
            token = token.strip()
            if not token or token == ';':
                continue
            if token == '{':
                indent += 1
                continue
            if token == '}':
                indent -= 1
                continue
            token = re.sub(r'new array<[^;]*?>\(\)', 'EArray()', token)
            token = re.sub(r'new (\w+)(?:\(\))?', r'\1()', token)
            token = re.sub(r'^(?:ref\s+)?(?:array<[^>]*>|int|float|bool|string|vector|[A-Z]\w*(?:<[^>]*>)?)\s+(\w+)\s*=', r'\1 =', token)
            bare = re.fullmatch(r'(?:ref\s+)?(?:array<[^>]*>|int|float|bool|string|vector|[A-Z]\w*(?:<[^>]*>)?)\s+(\w+)', token)
            if bare and not token.startswith('return'):
                token = bare[1] + ' = None'
            for field in fields:
                token = re.sub(r'(?<![\w.])' + field + r'\b', 'self.' + field, token)
            token = re.sub(r'(?<![\w.])mHC\w+\b', lambda m: 'self.' + m[0], token)
            for other, (other_static, _, _) in table.items():
                if other_static:
                    token = re.sub(r'(?<![\w])' + class_name + r'\.' + other + r'\(', other + '(', token)
                    token = re.sub(r'(?<![\w.])' + other + r'\(', other + '(', token)
                else:
                    token = re.sub(r'(?<![\w.])' + other + r'\(', 'self.' + other + '(', token)
            token = token.replace('&&', ' and ').replace('||', ' or ')
            token = re.sub(r'!(?!=)', 'not ', token)
            for original, target in (('true', 'True'), ('false', 'False'), ('null', 'None')):
                token = re.sub(r'\b' + original + r'\b', target, token)
            if token.startswith('else if ('):
                token = 'elif ' + token[9:-1] + ':'
            elif token.startswith('if ('):
                token = 'if ' + token[4:-1] + ':'
            elif token.startswith('while ('):
                token = 'while ' + token[7:-1] + ':'
            elif token.startswith('foreach ('):
                loop = re.fullmatch(r'foreach \((?:\w+) (\w+) : (.+)\)', token)
                token = 'for ' + loop[1] + ' in ' + loop[2] + ':'
            elif token == 'else':
                token = 'else:'
            elif token.startswith('switch'):
                raise AssertionError('switch is not supported by the test adapter; use if chains')
            token = re.sub(r'([\w.]+)\+\+$', r'\1 += 1', token)
            lines.append('    ' * indent + token)
        names = [p.split('=')[0].split()[-1] for p in params.split(',') if p.strip()]
        header = 'def %s(%s):' % (name, ', '.join((['self'] if not static else []) + names))
        namespace = env
        namespace.update(keys)
        namespace.setdefault('EArray', EArray)
        namespace.setdefault('indices', range)
        # Empty blocks (e.g. `if (...) { }`) are not authored; fail loudly.
        exec(compile(header + '\n' + '\n'.join(lines or ['    pass']), 'authored:' + class_name + '.' + name, 'exec'), namespace)
        function = namespace[name]
        env[name] = function
    return env


def v3(x, y, z):
    return [x, y, z]


def native_env():
    env = {
        'Vector': v3,
        'HCEventStatus': NS(ANNOUNCED=1, ACTIVE=2),
        'EArray': EArray,
    }
    rules = (ROOT / 'scripts/4_World/Groups/HCGroupRules.c').read_text()
    holder = {'indices': range}
    translate(rules, 'HCGroupRules', holder, only=('PositionValid',))
    env['HCGroupRules'] = NS(PositionValid=holder['PositionValid'])
    env['HCInfoPin'] = lambda: NS(Position=None, Label='', Joined=False)
    return env


def row(title='Supply recovery', briefing='', status=1, remaining=60, joined=False):
    return Row(Title=EStr(title), Briefing=EStr(briefing), Status=status,
               RemainingSeconds=remaining, Joined=joined)


SITE = 'Site coastal-police-source at <3569.727783, 13.309641, 2431.353027>\nReach the area and remain for 30 seconds.\nNo additional reward.'
DELIVERY = ('Site inland-police-source at <3421.3, 199.7, 13019.89>\n'
            'Carry the existing SodaCan_Cola, then place it directly inside the Barrel_Green at <100.0, 1.0, 200.0>. Carrying it nearby does not complete delivery.')


class InfoSites(unittest.TestCase):
    def setUp(self):
        source = INFO.read_text()
        self.env = native_env()
        translate(source, 'HCInfoEventSites', self.env)

    def parse(self, text, world=15360.0):
        pin = self.env['HCInfoPin']()
        return self.env['ParseSite'](EStr(text), world, pin), pin

    def test_retained_legacy_parser_extracts_only_source_position(self):
        ok, pin = self.parse(SITE)
        self.assertTrue(ok)
        self.assertAlmostEqual(3569.727783, pin.Position[0], 3)
        self.assertAlmostEqual(2431.353027, pin.Position[2], 3)

    def test_delivery_destination_is_never_promoted_to_a_pin(self):
        ok, pin = self.parse(DELIVERY)
        self.assertTrue(ok)
        self.assertAlmostEqual(3421.3, pin.Position[0], 1)
        self.assertAlmostEqual(13019.89, pin.Position[2], 1)

    def test_malformed_or_out_of_world_text_never_yields_a_pin(self):
        bad = [
            '', 'Reach the area', 'Site at <1, 2, 3>', 'Site a at 1, 2, 3',
            'Site a at <1, 2>', 'Site a at <1, 2, 3, 4>', 'Site a at <1, x, 3>',
            'Site a at <-5.0, 0, 3>', 'Site a at <1, 0, 99999>', 'Site a at <nan, 0, 3>',
            'Site a at <1, 0, 3', 'Site a at <1, 0, 3> trailing',
            'Site ' + 'x' * 200 + ' at <1, 0, 3>',
            '\nSite a at <1, 0, 3>', 'Site a at <1,, 3>', 'Site a at <1.2.3, 0, 3>',
        ]
        for text in bad:
            with self.subTest(text=text[:40]):
                ok, _ = self.parse(text)
                self.assertFalse(ok)
        ok, _ = self.parse('Site a at <15361, 0, 3>', 15360.0)
        self.assertFalse(ok)

    def test_collect_clears_stale_pins_even_for_valid_active_legacy_rows(self):
        rows = EArray([
            row('Supply recovery', SITE, 1, 60, False),
            row('Expired', SITE, 2, 0, False),
            row('Terminal', SITE, 4, 60, False),
            row('Unparseable', 'no site here', 1, 60, False),
            row('Joined one', DELIVERY, 2, 30, True),
        ])
        pins = EArray([NS(Label='stale quest')])
        self.env['Collect'](NS(Enabled=True, Rows=rows), 15360.0, pins)
        self.assertEqual([], pins)
        many = EArray([row('Many %d' % i, SITE, 1, 60, False) for i in range(80)])
        pins = EArray()
        self.env['Collect'](NS(Enabled=True, Rows=many), 15360.0, pins)
        self.assertEqual(0, len(pins))
        pins = EArray()
        self.env['Collect'](NS(Enabled=False, Rows=rows), 15360.0, pins)
        self.assertEqual(0, len(pins))

    def test_pin_dto_carries_only_a_label_a_position_and_a_joined_flag(self):
        source = INFO.read_text()
        match = re.search(r'class HCInfoPin\s*\{([^}]*)\}', source)
        self.assertTrue(match)
        fields = re.findall(r'(?:bool|int|float|string|vector) (\w+)', match[1])
        self.assertEqual(['Position', 'Label', 'Joined'], fields)


class InfoCache(unittest.TestCase):
    def test_retired_event_client_leaves_mission_list_empty(self):
        from tests.legacy.test_group_ui import SyntheticList, ui_member
        listing = SyntheticList()
        listing.items.append('stale quest')
        source = (GROUPS / 'HCGroupMapLayers.c').read_text()
        source = re.sub(r'\bHCEvent\w+\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
        env = dict(HCEventClient=NS(Get=lambda: NS(Fresh=lambda: False,
            GetView=lambda: self.fail('retired client view must not be queried'))))
        ui_member(source, 'Missions', NS(mHCEvents=listing), env, NS(MissionLayer=True))
        self.assertEqual([], listing.items)

    def build(self, fresh, view, reads):
        source = INFO.read_text()
        env = native_env()
        env['HCEventClient'] = NS(Get=lambda: NS(Fresh=lambda: fresh[0],
                                                  GetView=lambda: reads.append('view') or view))
        translate(source, 'HCInfoEventSites', env)
        env['HCInfoEventSites'] = NS(Collect=env['Collect'])
        translate(source, 'HCInfoEventCache', env)
        cache = NS(mHCPins=EArray(), mHCStamp=-100.0)
        for name in ('Pins', 'Clear'):
            setattr(cache, name, lambda *a, name=name: env[name](cache, *a))
        return cache

    def test_stale_or_missing_event_data_shows_no_pins_and_reads_nothing(self):
        reads = []
        fresh = [False]
        view = NS(Enabled=True, Rows=EArray([row('A', SITE, 1, 60, False)]))
        cache = self.build(fresh, view, reads)
        self.assertEqual(0, len(cache.Pins(0.0, 15360.0)))
        self.assertEqual([], reads)
        fresh[0] = True
        self.assertEqual(0, len(cache.Pins(1.0, 15360.0)))
        self.assertEqual([], reads)
        fresh[0] = False
        self.assertEqual(0, len(cache.Pins(2.5, 15360.0)))

    def test_pins_clear_even_when_old_event_data_claims_freshness(self):
        reads = []
        fresh = [True]
        view = NS(Enabled=True, Rows=EArray([row('A', SITE, 1, 60, False)]))
        cache = self.build(fresh, view, reads)
        cache.mHCPins.Insert(NS(Label='stale quest'))
        self.assertEqual(0, len(cache.Pins(10.0, 15360.0)))
        fresh[0] = False
        self.assertEqual(0, len(cache.Pins(10.5, 15360.0)))

    def test_draws_never_read_legacy_views_even_across_clock_changes(self):
        reads = []
        view = NS(Enabled=True, Rows=EArray([row('A', SITE, 1, 60, False)]))
        cache = self.build([True], view, reads)
        for tick in range(10):
            cache.Pins(10.0 + tick * 0.1, 15360.0)
        self.assertEqual([], reads)
        cache.Pins(11.5, 15360.0)
        self.assertEqual([], reads)
        # A clock rollback cannot revive the retired cache.
        cache.Pins(0.2, 15360.0)
        self.assertEqual([], reads)


class InfoFlags(unittest.TestCase):
    def setUp(self):
        self.env = native_env()
        translate(INFO.read_text(), 'HCInfoLayerFlags', self.env)
        self.flags = NS(ShowEvents=False, ShowVisited=True, ShowTeam=True, ShowMarkers=True, ShowGrid=True)
        self.toggle = lambda action: self.env['Toggle'](self.flags, action)
        self.label = lambda action: self.env['Label'](self.flags, action)

    def test_events_stay_disabled_and_other_buttons_flip_only_their_layer(self):
        pairs = {'HCInfoToggleVisited': 'ShowVisited', 'HCInfoToggleTeam': 'ShowTeam',
                 'HCInfoToggleMarkers': 'ShowMarkers', 'HCInfoToggleGrid': 'ShowGrid'}
        for action, field in pairs.items():
            with self.subTest(action=action):
                self.assertTrue(self.toggle(action))
                for other_field in pairs.values():
                    self.assertEqual(other_field != field, getattr(self.flags, other_field))
                self.assertFalse(self.flags.ShowEvents)
                self.assertTrue(self.toggle(action))
                self.assertTrue(getattr(self.flags, field))
        for initial in (False, True):  # Stale session flag cannot re-enable quests.
            self.flags.ShowEvents = initial
            self.assertTrue(self.toggle('HCInfoToggleEvents'))
            self.assertFalse(self.flags.ShowEvents)

    def test_unknown_buttons_are_not_consumed(self):
        self.assertFalse(self.toggle('HCSave'))
        self.assertFalse(self.toggle(''))
        self.assertFalse(self.flags.ShowEvents)
        self.assertTrue(all(getattr(self.flags, field) for field in
                            ('ShowVisited', 'ShowTeam', 'ShowMarkers', 'ShowGrid')))

    def test_labels_name_the_layer_and_its_state_without_relying_on_colour(self):
        self.assertEqual('', self.label('HCInfoToggleEvents'))
        self.toggle('HCInfoToggleEvents')
        self.assertEqual('', self.label('HCInfoToggleEvents'))
        self.assertEqual('Visited: on', self.label('HCInfoToggleVisited'))
        self.assertEqual('', self.label('HCNew'))

    def test_defaults_match_the_authored_field_initialisers(self):
        text = INFO.read_text()
        self.assertRegex(text, r'bool ShowEvents = false;')
        for field in ('ShowVisited', 'ShowTeam', 'ShowMarkers', 'ShowGrid'):
            self.assertRegex(text, r'bool ' + field + r' = true;')


class WiringAndPrivacy(unittest.TestCase):
    def test_layout_buttons_match_authored_actions_and_sit_in_front_of_the_map(self):
        layout = LAYOUT.read_text()
        names = re.findall(r'ButtonWidgetClass (HCInfoToggle\w+)', layout)
        self.assertEqual(['HCInfoToggleEvents', 'HCInfoToggleVisited', 'HCInfoToggleTeam',
                          'HCInfoToggleMarkers', 'HCInfoToggleGrid'], names)
        source = INFO.read_text()
        for name in names:
            self.assertIn('"' + name + '"', source)
        self.assertIn('hc_info_layers.layout', source)
        self.assertEqual(len(names), len(set(names)))

    def test_menu_routes_toggle_clicks_before_any_group_request_is_built(self):
        menu = (GROUPS / 'HCGroupMapMenu.c').read_text()
        click = re.search(r'override bool OnClick\([^)]*\)\s*\{', menu)
        code = body(menu, click.end())
        self.assertIn('mHCInfo.OnClick(w)', code)
        self.assertLess(code.index('mHCInfo.OnClick(w)'), code.index('new HCGroupRequest'))
        self.assertIn('mHCInfo.Init(layoutRoot)', menu)

    def test_draw_gates_every_layer_on_the_client_flags(self):
        layers = (GROUPS / 'HCGroupMapLayers.c').read_text()
        draw = re.search(r'void Draw\([^)]*\)\s*\{', layers)
        code = body(layers, draw.end())
        for flag in ('ShowGrid', 'ShowEvents', 'ShowVisited', 'ShowTeam', 'ShowMarkers'):
            self.assertIn('flags.' + flag, code)
        # Server data sources are unchanged: places/members/markers only come
        # from the validated frame; event pins only from the shared cache.
        self.assertIn('frame.Places', code)
        self.assertIn('mHCInfoEvents.Pins(', code)

    def test_client_layers_never_touch_server_catalogs_other_players_or_world_scans(self):
        forbidden = ['HCGroupPlaces', 'HCGroupPlaceCatalog', 'Explorers', 'PlaceIds', 'GetPlayers',
                     'GetObjectsAtPosition', 'EntityAI', 'ItemBase', 'DayZInfected', 'AIAgent',
                     'GetCargo', 'HCGroupState', 'HCGroupService', 'Candidates', 'Members',
                     'GetGame().GetPlayer', 'GetPosition()']
        text = INFO.read_text()
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)
        for path in (GROUPS / 'HCGroupMapLayers.c', GROUPS / 'HCGroupMapMenu.c'):
            for token in ('HCGroupPlaces', 'HCGroupPlaceCatalog', 'Explorers', 'PlaceIds', 'HCGroupService'):
                self.assertNotIn(token, path.read_text())

    def test_info_source_obeys_compile_rules(self):
        text = INFO.read_text()
        self.assertNotRegex(text, r'\?[^\n]*:')  # no ternary operator
        lines = text.splitlines()
        for number, line in enumerate(lines):
            self.assertFalse(re.match(r'\s*(\|\||&&)', line), number)
        for engine in ('Widget', 'Param', 'Man', 'Object', 'array', 'Grid', 'Team', 'Events', 'Math'):
            self.assertNotRegex(text, r'\b(?:bool|int|float|string|vector) ' + engine + r'\b')


class ServerDiscoveryPrivacy(unittest.TestCase):
    """Reconfirm the already-landed discovery journal against this layer's rules."""
    setUp = test_v1_groups.V1GroupsBehavior.setUp
    create = test_v1_groups.V1GroupsBehavior.create
    joined = test_v1_groups.V1GroupsBehavior.joined
    apply = test_v1_groups.V1GroupsBehavior.apply
    request = test_v1_groups.V1GroupsBehavior.request

    def place(self, uid):
        p = self.e['HCGroupPlace']()
        p.Id = uid
        p.Name = 'Synthetic ' + uid
        p.Position = [100, 0, 100]
        return p

    def test_group_visits_share_by_default_and_operator_can_keep_them_private(self):
        self.joined()
        place = self.place('p')
        self.assertTrue(self.e['RecordVisit'](self.state, self.cfg, 'alice', place, [100, 0, 100]))
        catalog = NS(Places=EArray([place, self.place('q')]))
        known = lambda uid: [x.Id for x in self.e['KnownPlaces'](self.state, self.cfg, uid, catalog)]
        self.assertTrue(self.cfg.ShareDiscovery)
        self.assertEqual(['p'], known('bob'))
        self.cfg.ShareDiscovery = False
        self.assertEqual(['p'], known('alice'))
        self.assertEqual([], known('bob'))
        self.assertEqual([], known('stranger'))
        self.cfg.ShareDiscovery = True
        self.assertEqual(['p'], known('bob'))
        self.assertEqual([], known('stranger'))

    def test_unvisited_catalog_entries_are_never_listed_and_count_is_bounded(self):
        self.joined()
        self.cfg.MaxDiscoveries = 2
        catalog = NS(Places=EArray([self.place(c) for c in 'abcd']))
        for letter in 'abcd':
            self.e['RecordVisit'](self.state, self.cfg, 'alice', self.place(letter), [100, 0, 100])
        known = self.e['KnownPlaces'](self.state, self.cfg, 'alice', catalog)
        self.assertEqual(['a', 'b'], [x.Id for x in known])
        self.assertEqual([], self.e['KnownPlaces'](self.state, self.cfg, 'alice', NS(Places=EArray([self.place('z')]))))


class AdminCommandSmoke(unittest.TestCase):
    def test_synthetic_sender_authority_refuses_guest_and_dispatches_admin_status(self):
        # Executes authored guards with explicit synthetic identities; no DayZ claim.
        from tests.legacy.test_horde_stimulus import compile_method
        admin = NS(GetPlainId=lambda: 'synthetic-admin')
        guest = NS(GetPlainId=lambda: 'synthetic-guest')
        service = NS(m_Running=True, m_Permissions=None, m_Admins=NS(PlainIds=EArray(['synthetic-admin'])))
        calls = []
        authorized = compile_method('../Admin/HCAdminModule.c', 'bool HCAuthorized(', 'sender', {'GetGame': lambda: NS(IsServer=lambda: True)})
        service.HCAuthorized = lambda sender: authorized(service, sender)
        service.HCRefused = lambda sender: calls.append('refused')
        service.HCStatus = lambda sender, ticket: calls.append(('status', sender, ticket))
        service.HCCommand = lambda *args: self.fail('status must not mutate gameplay')
        dispatch = compile_method('../Admin/HCAdminModule.c', 'bool HCDispatch(',
                                  'sender, command, value, ticket', {},
                                  ('HCAuthorized', 'HCRefused', 'HCStatus', 'HCCommand'))
        self.assertFalse(dispatch(service, guest, 'status', 0, 1))
        self.assertEqual(['refused'], calls)
        self.assertTrue(dispatch(service, admin, 'status', 0, 2))
        self.assertEqual(('status', admin, 2), calls[-1])
        service.m_Running = False
        self.assertFalse(dispatch(service, admin, 'status', 0, 3))


if __name__ == '__main__':
    unittest.main()
