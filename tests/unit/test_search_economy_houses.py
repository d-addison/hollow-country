"""Lazy House search (T5): targeting, lazy bind, caps, LRU release, journal and the hook.

The authored Enforce sources HCSearchHouseJournal.c, HCSearchHouses.c and
HCSearchHouseHook.c are translated to Python by the small statement translator below and
executed over explicitly SYNTHETIC fakes (houses, players, items, files, template pack).
The translator only supplies language scaffolding (blocks, foreach, declarations, new, casts,
out parameters); every policy decision under test comes from the authored source. The
existing registry/provider are executed through the Runtime of test_search_supply_provider.
Offline tests never establish DayZ behavior: CAP-09, replication, TakeToDst from proxy cargo,
CE value tiers and two-client behavior stay pending.
"""
import re
import unittest
from tests.unit.test_tilt_rule import tilt_rules
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_search_supply_provider as sp
from tests.unit import tick_budget_fixture as tick_fixture
from tools.setup import probe_runtime
from tests.unit.test_group_server import EArray

SCRIPTS = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'
LOOT = SCRIPTS / '4_World/Loot'
HOUSE_FILES = ('HCSearchHouseJournal.c', 'HCSearchHouses.c', 'HCSearchHouseHook.c')
KEYWORDS = {'return', 'else', 'delete', 'new', 'break', 'continue'}
TYPE = r'[A-Za-z_]\w*(?:<[^>]*>)?'
DECL = re.compile(r'^(?:(?:ref|const|static|protected|private|autoptr)\s+)*(?P<t>' + TYPE +
                  r')\s+(?P<n>[A-Za-z_]\w*)\s*(?:=\s*(?P<v>.+))?$', re.S)
DEFAULTS = {'int': '0', 'float': '0.0', 'bool': 'False', 'string': "''", 'vector': '[0.0, 0.0, 0.0]'}


class W5RetirementSmoke(unittest.TestCase):
    def test_oldest_eviction_keeps_replay_barrier_after_snapshot_roundtrip(self):
        import json
        env = dict(EArray=EArray)
        for code in Translator((LOOT / 'HCSearchRefresh.c').read_text(), only=(
                'HCSearchRetirementEntry', 'HCSearchRetirementState', 'HCSearchRetirementPolicy')).classes():
            exec(code, env)
        self.assertIn('HCSearchRetirementPolicy', env, 'bounded retirement policy missing')
        policy = env['HCSearchRetirementPolicy']
        policy.MAX_RECENT = 2  # Explicit small synthetic FIFO; production cap is 2048.
        state = env['HCSearchRetirementState']()
        state.Archive = EArray([0] * 2048)
        for supply, fingerprint in (('synthetic_oldest', 3), ('synthetic_next', 4), ('synthetic_new', 5)):
            policy.Retain(state, supply, fingerprint)
        self.assertEqual(['synthetic_next', 'synthetic_new'], [r.SupplyId for r in state.Recent])
        state.Archive = EArray(json.loads(json.dumps(list(state.Archive))))
        self.assertTrue(policy.Contains(state, 'synthetic_oldest', 3))
        self.assertFalse(policy.Contains(state, 'synthetic_unseen', 6))


class HMap(dict):
    def Contains(self, key): return key in self
    def Set(self, key, value): self[key] = value
    def Count(self): return len(self)
    def Clear(self): self.clear()
    def __bool__(self): return True


def find_out(container, key):
    """Enforce map.Find(key, out value) as (found, value)."""
    return (key in container, container.get(key))


def match_brace(text, start):
    depth, i = 0, start
    while True:
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return i
        i += 1


def match_paren(text, start):
    depth, i = 0, start
    while True:
        depth += (text[i] == '(') - (text[i] == ')')
        if depth == 0:
            return i
        i += 1


class Translator:
    """Enforce subset -> Python. Anything it cannot read raises, never guesses."""

    def __init__(self, source, only=None):
        text = re.sub(r'//[^\n]*', '', source)
        self.strings = []
        text = re.sub(r'"(?:[^"\\]|\\.)*"', self.stash, text)
        self.text, self.only = text, only

    def stash(self, match):
        self.strings.append(match[0])
        return '__S%d__' % (len(self.strings) - 1)

    def unstash(self, text):
        return re.sub(r'__S(\d+)__', lambda m: self.strings[int(m[1])], text)

    def classes(self):
        out, pos = [], 0
        pattern = re.compile(r'(modded\s+)?class\s+(\w+)(?:\s*(?:extends|:)\s*(\w+))?\s*\{')
        while True:
            m = pattern.search(self.text, pos)
            if not m:
                return out
            end = match_brace(self.text, m.end() - 1)
            if self.only is None or m[2] in self.only:
                out.append(self.klass(m[2], m[3], m[1], self.text[m.end():end]))
            pos = end + 1

    def members(self, body):
        out, i = [], 0
        while True:
            while i < len(body) and body[i].isspace():
                i += 1
            if i >= len(body):
                return out
            j = i
            while body[j] not in ';{':
                j += 1
            head = body[i:j].strip()
            if body[j] == ';':
                out.append((head, None))
                i = j + 1
            else:
                k = match_brace(body, j)
                out.append((head, body[j + 1:k]))
                i = k + 1

    def klass(self, name, base, modded, body):
        members = self.members(body)
        names = set()
        for head, block in members:
            if block is not None or '(' in head:
                names.add(re.search(r'(\w+)\s*\(', head)[1])
            else:
                names.add(DECL.match(head)['n'])
        lines = []
        init = []
        for head, block in members:
            if block is None and '(' not in head:
                decl = DECL.match(head)
                static = bool(re.search(r'\b(static|const)\b', head.split(decl['t'])[0]))
                value = decl['v']
                code = self.expr(value, names) if value else DEFAULTS.get(decl['t'], 'None')
                if re.match(r'new\s+(array|map)', value or ''):
                    code = 'EArray()' if value.startswith('new array') else 'HMap()'
                if static:
                    lines.append('    %s = %s' % (decl['n'], code))
                else:
                    init.append('        self.%s = %s' % (decl['n'], code))
        lines.append('    def __init__(self):')
        lines.extend(init or ['        pass'])
        for head, block in members:
            if block is None and '(' not in head:
                continue
            m = re.match(r'^((?:(?:static|override|protected|private)\s+)*)' + TYPE +
                         r'\s+(\w+)\s*\(([^)]*)\)$', head)
            if not m:
                raise AssertionError('unreadable member: ' + head)
            params = [p.strip().split()[-1] for p in m[3].split(',') if p.strip()]
            deco = '    @classmethod\n' if 'static' in m[1] else ''
            lines.append(deco + '    def %s(self%s):' % (m[2], ''.join(', ' + p for p in params)))
            body_lines = self.block(block, names, 2)
            lines.extend(body_lines or ['        pass'])
        header = 'class %s(%s):' % (name, base or ('_Base_' + name if modded else 'object'))
        return self.unstash(header + '\n' + '\n'.join(lines) + '\n')

    # ---- statements ----
    def block(self, text, names, indent):
        out, i = [], 0
        while True:
            i = self.skip(text, i)
            if i >= len(text):
                return out
            lines, i = self.stmt(text, i, names, indent)
            out.extend(lines)

    @staticmethod
    def skip(text, i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    def stmt(self, text, i, names, indent):
        pad = '    ' * indent
        if text[i] == '{':
            end = match_brace(text, i)
            return self.block(text[i + 1:end], names, indent) or [pad + 'pass'], end + 1
        m = re.match(r'(if|while|foreach)\s*\(', text[i:])
        if m:
            open_at = i + m.end() - 1
            close = match_paren(text, open_at)
            cond = text[open_at + 1:close]
            body, j = self.stmt(text, self.skip(text, close + 1), names, indent + 1)
            if m[1] == 'foreach':
                var, coll = cond.split(' : ')
                head = pad + 'for %s in %s:' % (var.split()[-1], self.expr(coll, names))
            else:
                head = pad + '%s %s:' % (m[1], self.expr(cond, names))
            out = [head] + body
            k = self.skip(text, j)
            if m[1] == 'if' and re.match(r'else\b', text[k:]):
                other, j = self.stmt(text, self.skip(text, k + 4), names, indent + 1)
                out += [pad + 'else:'] + other
            return out, j
        end = text.index(';', i)
        return self.simple(text[i:end].strip(), names, pad), end + 1

    def simple(self, stmt, names, pad):
        first = stmt.split()[0] if stmt.split() else ''
        if first not in KEYWORDS:
            decl = DECL.match(stmt)
            if decl and decl['t'] not in KEYWORDS:
                value = self.expr(decl['v'], names) if decl['v'] else DEFAULTS.get(decl['t'], 'None')
                if decl['v'] and re.match(r'new\s+array', decl['v']):
                    value = 'EArray()'
                if decl['v'] and re.match(r'new\s+map', decl['v']):
                    value = 'HMap()'
                return [pad + '%s = %s' % (decl['n'], value)]
        if stmt.endswith('++'):
            return [pad + self.expr(stmt[:-2], names) + ' += 1']
        if first in ('break', 'continue'):
            return [pad + first]
        if first == 'return':
            rest = stmt[6:].strip()
            return [pad + ('return ' + self.expr(rest, names) if rest else 'return')]
        return [pad + self.expr(stmt, names)]

    # ---- expressions ----
    def expr(self, text, names):
        text = re.sub(r'new\s+(?:array|map)<[^>]*>(?:\(\))?', lambda m: 'EArray()' if 'array' in m[0] else 'HMap()', text)
        text = re.sub(r'new\s+(\w+)(?:\(\))?', r'\1()', text)
        text = text.replace('&&', ' and ').replace('||', ' or ')
        text = re.sub(r'!(?!=)', ' not ', text)
        text = re.sub(r'\bnull\b', 'None', text)
        text = re.sub(r'\btrue\b', 'True', text)
        text = re.sub(r'\bfalse\b', 'False', text)
        text = re.sub(r'\bsuper\.', 'super().', text)
        text = re.sub(r'\bthis\b', 'self', text)

        def prefix(m):
            return 'self.' + m[0] if m[0] in names else m[0]
        text = re.sub(r'(?<![\w.])[A-Za-z_]\w*', prefix, text)
        text = re.sub(r'HCSearchJson<HCSearchRecord>\.Load\((.+?), 8192, (\w+)\)',
                      r'(((\2 := load_record(\1)) is not None))', text)
        text = text.replace('HCSearchJson<HCSearchRecord>.WriteNew(', 'write_json(')
        text = re.sub(r'([\w.]+)\.Find\(([^,()]+), (\w+)\)',
                      r'((_r := find_out(\1, \2)) and (((\3 := _r[1]) if _r[0] else 0) or True) and _r[0])', text)
        text = re.sub(r'([\w.]+)\.Substring\(', r'substr(\1, ', text)
        text = re.sub(r'((?:\w+(?:\(\))?\.)*\w+(?:\(\))?)\.ToString\(\)', r'tostr(\1)', text)
        return text


def translate(filename, only=None, base=LOOT):
    return Translator((base / filename).read_text(), only).classes()


# ---- synthetic fakes -----------------------------------------------------------------
class FakeHouse:
    def __init__(self, cls, position, yaw=0., tilt=0.):
        self.cls, self.position, self.yaw, self.tilt = cls, list(position), yaw, tilt

    def GetType(self): return self.cls
    def GetPosition(self): return self.position
    def GetOrientation(self): return [self.yaw, self.tilt, 0.]
    def ModelToWorld(self, p): return [a + b for a, b in zip(self.position, p)]
    def WorldToModel(self, w): return [a - b for a, b in zip(w, self.position)]


class FakeTarget:
    def __init__(self, obj, hit, parent=None):
        self.obj, self.hit, self.parent = obj, list(hit), parent

    def GetObject(self): return self.obj
    def GetParent(self): return self.parent
    def GetCursorHitPos(self): return self.hit


class FakePlayer(sp.Player):
    def __init__(self, world, ident, position):
        super().__init__(world, ident, position=position)
        self.messages, self.hands = [], None

    def GetHumanInventory(self): return N(GetEntityInHands=lambda: self.hands)
    def MessageStatus(self, text): self.messages.append(text)


class FakeAction:
    m_MainItem = None

    def __init__(self, player, target):
        self.m_Player, self.m_Target, self.Site = player, target, None


def settings(**override):
    base = dict(EnableInteriors=True, EnableSearch=True, MaxBoundSearchSites=256, MaxActiveInteriors=12,
                MaxBindQueriesPerTick=2, MaxTickWorkItems=32, MaxPropsPerInterior=5, SearchDensityScale=0)
    base.update(override)
    from tests.unit.settings_registry_fixture import attach_density
    return attach_density(N(**base))


PACK_PIN = 'c' * 64
SYNTH = 'SyntheticHouse'
# Explicit synthetic template pack: NOT shipped evidence and never inside a pack.
SITE_A = N(Id=1, Center=EArray([0., 1., 0.]), Radius=1.0, Room=2, Groups=EArray(['g-0001']))
SITE_B = N(Id=2, Center=EArray([20., 1., 0.]), Radius=1.0, Room=3, Groups=EArray(['g-0001']))
SITE_C = N(Id=3, Center=EArray([40., 1., 0.]), Radius=1.0, Room=4, Groups=EArray(['g-0001']))


class Pack:
    """Test-only stand-in for T3's HCInteriorTemplates reader (contract section 10)."""

    def __init__(self, loaded=True, sites=(SITE_A, SITE_B, SITE_C), search='covered', items=('SyntheticFood', 'SyntheticTool')):
        self.loaded, self.sites, self.search, self.items = loaded, sites, search, items

    def api(self):
        return N(Loaded=lambda: self.loaded,
                 ClassRow=lambda cls: N(Search=self.search) if cls == SYNTH else None,
                 Template=lambda cls: N(TemplateId='tpl_synth', SearchSites=EArray(self.sites)) if cls == SYNTH else None,
                 Group=lambda gid: N(Items=EArray(self.items)) if gid == 'g-0001' else None,
                 SourcePin=lambda: PACK_PIN)


class Harness:
    """One process lifetime over a shared synthetic world and file system."""

    def __init__(self, world=None, fs=None, pack=None, **settings_override):
        self.world = world or sp.World()
        self.fs = fs or sp.FS()
        self.pack = pack or Pack()
        self.rt = sp.Runtime(self.world, self.fs)
        self.settings = settings(**settings_override)
        self.houses_binding = N(houses=None)
        self.pilot_calls = []
        self.build()

    def build(self):
        pilot = self.pilot_calls
        env = dict(self.rt.env)
        env.update(
            HMap=HMap, find_out=find_out, tostr=str, substr=lambda s, a, n: s[a:a + n],
            load_record=lambda path: self.rt.parse_record(self.fs.files.get(path)),
            write_json=self.rt.write_json,
            Vector=lambda x, y, z: [x, y, z],
            Math=N(AbsFloat=abs),
            vector=N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
            House=N(Cast=lambda obj: obj if isinstance(obj, FakeHouse) else None),
            HCInteriorActionData=N(Cast=lambda obj: obj if isinstance(obj, FakeAction) else None),
            HCInteriorTemplates=self.pack.api(),
            HCInteriorRules=N(**vars(tilt_rules()), MaySearch=lambda *a: all(a), SearchAdmitted=lambda: True,
                              SaneVector=lambda v, limit: all(abs(c) < limit for c in v),
                              TransformKey=lambda pos, ori: 'x%dy%dz%dw%d' % (pos[0], pos[1], pos[2], ori[0])),
            HCInteriorSearchContext=lambda: N(InstanceId='', LayoutId='', History='', Room='', GroupId='',
                                              SourcePin='', EvidencePin='', MeasuredRecordSha256='', Items=EArray()),
            HCSearchSiteVolume=lambda: N(SiteId='', Center=[0., 0., 0.], Radius=0., Classes=EArray()),
            HCSearchEntry=lambda: N(SiteId='', SupplyId='', ItemClass=''),
            HCSearchScanBudget=self.rt.budget_factory,
            HCSearchSupplyProvider=self.rt.provider,
            HCSearchBinding=N(Houses=lambda: self.houses_binding.houses),
        )
        env['HCInteriorSite'] = lambda: N(Id='', SlotId=0, Target=None, Point=[0., 0., 0.], Item='',
                                           Phase=0, Owner=None, StartedAt=0., Deadline=0.)
        env['_Base_HCInteriorsModule'] = type('PilotModule', (), {
            name: (lambda self, *a, name=name: pilot.append(name) or (name == 'CanStart' or name == 'CanContinue'))
            for name in ('CanStart', 'CanContinue', 'BeginSearch', 'CommitSearch', 'EndSearch')})
        # The real HCInteriorSite fields are proven by translating its declaration.
        for klass in translate('../Interiors/HCInteriorCatalog.c', only=('HCInteriorSite',)):
            exec(klass, env)
        # SearchType is read from the authored catalog source (not retyped here).
        catalog = (SCRIPTS / '4_World/Interiors/HCInteriorCatalog.c').read_text()
        body = re.search(r'static bool SearchType\(string type\)\s*\{(.*?)\}', catalog, re.S)[1]
        pilot_types = set(re.findall(r'"(\w+)"', body))
        self.pilot_types = pilot_types
        env['HCInteriorCatalog'] = N(SearchType=lambda cls: cls in pilot_types)
        site_fields = env['HCInteriorSite']()
        self.site_fields = {k for k in vars(site_fields)}
        from tests.unit.test_refusal_report import install_refusal
        install_refusal(env)
        tick_fixture.install(env)
        for filename in HOUSE_FILES:
            for source in translate(filename):
                exec(source, env)
        self.env = env
        self.houses = env['HCSearchHouses']()
        self.houses.Start(self.settings)
        self.houses_binding.houses = self.houses
        self.hook = env['HCInteriorsModule']()

    def restart(self, **override):
        """New process: authored objects rebuilt; world and files survive."""
        if override:
            self.settings = settings(**override)
        self.rt = sp.Runtime(self.world, self.fs)
        self.build()

    def house(self, position=(1000., 0., 1000.), **kw):
        return FakeHouse(SYNTH, position, **kw)

    def player(self, ident='actor_a', position=(0., 0., 0.)):
        player = FakePlayer(self.world, ident, position)
        self.world.players.append(player)
        return player

    def food(self, n, near, typ='SyntheticFood'):
        return sp.Item(self.world, (n, 2, 3, 4), typ=typ, position=near)

    def action(self, player, house, local_hit, standing=None):
        hit = house.ModelToWorld(local_hit)
        if standing is not None:
            player.position = list(house.ModelToWorld(standing))
        return FakeAction(player, FakeTarget(house, hit))

    def moves(self):
        return [e for e in self.world.events if e.startswith('move:')]


def site_world(house, site):
    return house.ModelToWorld(list(site.Center))


class HouseCase(unittest.TestCase):
    def setUp(self):
        self.h = Harness()


class TargetingTests(HouseCase):
    def check(self, local_hit, standing, **kw):
        house = self.h.house(**kw)
        player = self.h.player()
        self.h.food(1, site_world(house, SITE_A))
        action = self.h.action(player, house, local_hit, standing)
        return self.h.houses.CanStart(player, action.m_Target), house, player

    def test_hit_inside_sphere_starts_and_hit_outside_refuses(self):
        self.assertTrue(self.check([0.2, 1., 0.], [0., 1., 1.5])[0])
        self.setUp()
        self.assertFalse(self.check([0., 1., 1.3], [0., 1., 1.5])[0])

    def test_player_at_2_4_m_is_accepted_and_at_2_6_m_refused(self):
        self.assertTrue(self.check([0., 1., 0.], [0., 1., 2.4])[0])
        self.setUp()
        self.assertFalse(self.check([0., 1., 0.], [0., 1., 2.6])[0])

    def test_refuses_when_the_template_pack_is_not_loaded(self):
        self.h = Harness(pack=Pack(loaded=False))
        self.assertFalse(self.check([0., 1., 0.], [0., 1., 1.])[0])
        house = self.h.house()
        player = self.h.player()
        self.h.houses.Begin(self.h.action(player, house, [0., 1., 0.], [0., 1., 1.]))
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertEqual({}, {k: v for k, v in self.h.fs.files.items()})

    def test_house_search_accepts_nearly_level_and_refuses_excessive_or_nan_tilt(self):
        for tilt, expected in ((.3, True), (-.3, True), (-0., True), (.5, True),
                               (-.5, True), (.6, False), (-.6, False), (float('nan'), False)):
            with self.subTest(tilt=tilt):
                self.h = Harness()
                self.assertEqual(expected, self.check([0., 1., 0.], [0., 1., 1.], tilt=tilt)[0])

    def test_class_not_marked_covered_tilted_house_and_bad_sphere_refuse(self):
        self.h = Harness(pack=Pack(search='excluded'))
        self.assertFalse(self.check([0., 1., 0.], [0., 1., 1.])[0])
        self.h = Harness()
        self.assertFalse(self.check([0., 1., 0.], [0., 1., 1.], tilt=5.)[0])
        huge = N(Id=1, Center=EArray([0., 1., 0.]), Radius=9.0, Room=2, Groups=EArray(['g-0001']))
        self.h = Harness(pack=Pack(sites=(huge,)))
        self.assertFalse(self.check([0., 1., 0.], [0., 1., 1.])[0])

    def test_non_house_target_is_not_a_house_target(self):
        prop = N(GetType=lambda: 'SyntheticCabinet')
        self.assertFalse(self.h.env['HCSearchHouses'].IsHouseTarget(FakeTarget(prop, [0., 0., 0.])))
        self.assertTrue(self.h.env['HCSearchHouses'].IsHouseTarget(FakeTarget(self.h.house(), [0., 0., 0.])))

    def test_site_id_follows_the_contract_formula_and_rotated_house_keeps_local_frame(self):
        house = self.h.house()
        player = self.h.player()
        hit = self.h.houses.Resolve(player, self.h.action(player, house, [0., 1., 0.], [0., 1., 1.]).m_Target)
        self.assertEqual('SyntheticHouse_x1000y0z1000w0_site1_v2', hit.SiteId)
        self.assertEqual(site_world(house, SITE_A), hit.Center)


class SearchTests(HouseCase):
    def begin(self, local=(20., 1., 0.), stand=None, ident='actor_a', house=None, player=None):
        house = house or self.h.house()
        player = player or self.h.player(ident)
        action = self.h.action(player, house, list(local), stand or [local[0], 1., 1.5])
        self.h.houses.Begin(action)
        return house, player, action

    def test_first_search_binds_existing_ce_items_and_moves_one_without_creating(self):
        house = self.h.house()
        item = self.h.food(1, site_world(house, SITE_A))
        self.h.food(2, site_world(house, SITE_A), typ='SyntheticTool')
        before = list(self.h.world.items)
        _, player, action = self.begin(local=(0., 1., 0.), house=house, stand=[0., 1., 1.5])
        self.assertEqual(1, self.h.houses.SessionCount())
        self.assertEqual(2, self.h.houses.m_Journal.Count())
        self.h.world.now += 6.5
        self.h.houses.Commit(action)
        self.assertEqual(1, len(self.h.moves()))
        self.assertEqual(before, self.h.world.items)
        self.assertEqual([], self.h.rt.created)
        self.assertEqual(1, len(player.cargo))
        self.assertIn(player.cargo[0], before)
        self.assertEqual(5., player.cargo[0].quantity)
        self.assertEqual(2, action.Site.Phase)
        self.h.houses.End(action)
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertIsNone(action.Site)
        self.assertIsNotNone(item)

    def test_commit_before_six_seconds_does_nothing_and_second_commit_never_moves_again(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        _, _, action = self.begin(local=(0., 1., 0.), house=house)
        self.h.world.now += 2.
        self.h.houses.Commit(action)
        self.assertEqual([], self.h.moves())
        self.h.world.now += 5.
        self.h.houses.Commit(action)
        self.h.houses.Commit(action)
        self.assertEqual(1, len(self.h.moves()))

    def test_nothing_is_created_split_or_refunded_when_the_move_fails(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        _, _, action = self.begin(local=(0., 1., 0.), house=house, player=player)
        player.capacity = 0
        self.h.world.now += 6.5
        self.h.houses.Commit(action)
        self.assertEqual([], self.h.moves())
        self.assertEqual([], self.h.rt.created)
        self.assertEqual(1, len(self.h.world.items))

    def test_empty_scan_is_not_journaled_and_is_negatively_cached_for_sixty_seconds(self):
        house = self.h.house()
        self.begin(local=(0., 1., 0.), house=house)
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertFalse([p for p in self.h.fs.files if 'entry_' in p])
        self.h.food(1, site_world(house, SITE_A))
        self.begin(local=(0., 1., 0.), house=house)
        self.assertEqual(0, self.h.houses.SessionCount())
        self.h.world.now += 61.
        self.begin(local=(0., 1., 0.), house=house)
        self.assertEqual(1, self.h.houses.SessionCount())

    def test_depletion_persists_across_restart_and_never_replays(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        _, player, action = self.begin(local=(0., 1., 0.), house=house)
        self.h.world.now += 6.5
        self.h.houses.Commit(action)
        self.h.houses.End(action)
        self.assertEqual(1, len(self.h.moves()))
        self.h.food(9, site_world(house, SITE_A))  # CE places another item later; it was never journaled
        self.h.restart()
        player2 = self.h.player('actor_b')
        self.h.houses.Begin(self.h.action(player2, house, [0., 1., 0.], [0., 1., 1.]))
        # The spent supply stays spent; the site is already bound so no rescan adds loot.
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertEqual(1, len(self.h.moves()))

    def test_site_cap_stops_new_sites_but_not_bound_ones(self):
        self.h = Harness(MaxBoundSearchSites=2)
        house = self.h.house()
        for n, site in enumerate((SITE_A, SITE_B, SITE_C), start=1):
            self.h.food(n, site_world(house, site))
        sessions = []
        for site in (SITE_A, SITE_B, SITE_C):
            _, _, action = self.begin(local=tuple(site.Center), house=house, ident='p%d' % site.Id)
            sessions.append(self.h.houses.SessionCount())
        self.assertEqual([1, 2, 2], sessions)
        self.assertEqual(2, self.h.houses.m_Journal.SiteCount())

    def test_journal_cap_is_4096_entries(self):
        journal = self.h.env['HCSearchHouseJournal']()
        self.assertTrue(journal.Open('stock-ce-template-houses-v2', PACK_PIN, 'synthetic_world', '1.30.164289'))
        for n in range(4096):
            self.assertTrue(journal.Add('site_x', 'supply%d' % n, 'SyntheticFood'), n)
        self.assertFalse(journal.Add('site_x', 'supply4096', 'SyntheticFood'))
        self.assertEqual(4096, journal.Count())
        self.assertEqual('', journal.PathFor(4096, 'entry'))

    def test_full_journal_refuses_a_new_site_before_any_scan(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        self.h.houses.EnsureJournal()
        for n in range(4096):
            self.h.houses.m_Journal.Add('other_site', 'supply%d' % n, 'SyntheticFood')
        self.begin(local=(0., 1., 0.), house=house, player=player)
        self.assertEqual(0, self.h.houses.SessionCount())

    def test_bind_queries_per_tick_are_capped(self):
        self.h = Harness(MaxBindQueriesPerTick=1)
        house = self.h.house()
        for n, site in enumerate((SITE_A, SITE_B), start=1):
            self.h.food(n, site_world(house, site))
        self.begin(local=tuple(SITE_A.Center), house=house, ident='p1')
        self.begin(local=tuple(SITE_B.Center), house=house, ident='p2')
        self.assertEqual(1, self.h.houses.SessionCount())
        self.h.world.now += 1.
        self.begin(local=tuple(SITE_B.Center), house=house, ident='p2')
        self.assertEqual(2, self.h.houses.SessionCount())

    def test_group_item_cap_is_1024_not_256(self):
        filler = ['Filler%04d' % n for n in range(1023)]
        for count, sessions in ((1024, 1), (1025, 0)):
            self.h = Harness(pack=Pack(items=['SyntheticFood'] + filler + ['Extra'] * (count - 1024)))
            house = self.h.house()
            self.h.food(1, site_world(house, SITE_A))
            self.begin(local=(0., 1., 0.), house=house)
            self.assertEqual(sessions, self.h.houses.SessionCount(), count)

    def test_player_with_hands_full_or_second_session_on_one_site_is_refused(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        player.hands = object()
        self.begin(local=(0., 1., 0.), house=house, player=player)
        self.assertEqual(0, self.h.houses.SessionCount())
        player.hands = None
        self.begin(local=(0., 1., 0.), house=house, player=player)
        other = self.h.player('actor_b')
        self.begin(local=(0., 1., 0.), house=house, player=other)
        self.assertEqual(1, self.h.houses.SessionCount())

    def test_continue_requires_the_same_site_and_player_in_range(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        _, player, action = self.begin(local=(0., 1., 0.), house=house)
        self.assertTrue(self.h.houses.CanContinue(action))
        player.position = house.ModelToWorld([0., 1., 3.])
        self.assertFalse(self.h.houses.CanContinue(action))
        player.position = house.ModelToWorld([0., 1., 1.])
        self.h.world.now += 16.
        self.assertFalse(self.h.houses.CanContinue(action))


class LruTests(HouseCase):
    def test_spent_binding_releases_outside_player_range_and_new_house_binds_at_cap(self):
        # Explicit synthetic world/players; this does not establish DayZ behavior.
        self.h = Harness(MaxBoundSearchSites=1)
        first, second = self.houses_at(2)
        action = self.start(first, 'p1')
        self.h.world.now += 6.5
        self.h.houses.Commit(action)
        self.h.houses.End(action)
        player = action.m_Player
        self.h.houses.RecycleSpentBindings(EArray([player]))
        self.assertEqual(1, self.h.houses.m_Journal.SiteCount())
        player.position = second.GetPosition()
        self.h.houses.RecycleSpentBindings(EArray([player]))
        self.assertEqual(0, self.h.houses.m_Journal.SiteCount())
        self.assertTrue(self.h.houses.m_Journal.SupplyKnown('1_2_3_4'))
        replacement = self.start(second, 'p2')
        self.assertIsNotNone(replacement.Site)
        self.assertEqual(1, self.h.houses.m_Journal.SiteCount())
        self.assertEqual(1, len(self.h.moves()))

    def houses_at(self, count):
        out = []
        for n in range(count):
            house = self.h.house(position=(1000. + 100. * n, 0., 1000.))
            self.h.food(n + 1, site_world(house, SITE_A))
            out.append(house)
        return out

    def start(self, house, ident):
        player = self.h.player(ident)
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        return action

    def test_least_recently_used_idle_house_is_released_first(self):
        self.h = Harness(MaxActiveInteriors=2)
        a, b, c = self.houses_at(3)
        self.h.houses.End(self.start(a, 'p1'))
        self.h.world.now += 1.
        self.h.houses.End(self.start(b, 'p2'))
        self.h.world.now += 1.
        self.h.houses.End(self.start(c, 'p3'))
        self.assertEqual(2, self.h.houses.ActiveCount())
        self.assertEqual(['SyntheticHouse_x1100y0z1000w0', 'SyntheticHouse_x1200y0z1000w0'],
                         [slot.InstanceId for slot in self.h.houses.m_Slots])
        # Released house keeps its journal rows and rebinds the same item without new rows.
        rows = self.h.houses.m_Journal.Count()
        self.h.world.now += 1.
        again = self.start(a, 'p4')
        self.assertEqual(1, self.h.houses.SessionCount())
        self.assertEqual(rows, self.h.houses.m_Journal.Count())
        self.h.houses.End(again)

    def test_a_house_with_a_live_session_is_never_released(self):
        self.h = Harness(MaxActiveInteriors=2)
        a, b, c = self.houses_at(3)
        self.start(a, 'p1')
        self.h.world.now += 1.
        self.start(b, 'p2')
        self.h.world.now += 1.
        refused = self.start(c, 'p3')
        self.assertEqual(2, self.h.houses.SessionCount())
        self.assertIsNone(refused.Site)
        self.assertEqual(2, self.h.houses.ActiveCount())

    def test_idle_house_is_released_while_the_busy_one_stays(self):
        self.h = Harness(MaxActiveInteriors=2)
        a, b, c = self.houses_at(3)
        self.start(a, 'p1')            # busy, oldest
        self.h.world.now += 1.
        self.h.houses.End(self.start(b, 'p2'))   # idle
        self.h.world.now += 1.
        self.start(c, 'p3')
        names = [slot.InstanceId for slot in self.h.houses.m_Slots]
        self.assertIn('SyntheticHouse_x1000y0z1000w0', names)
        self.assertNotIn('SyntheticHouse_x1100y0z1000w0', names)


class HookTests(HouseCase):
    def test_house_target_goes_to_the_service_and_other_targets_take_the_pilot_path(self):
        house = self.h.house()
        player = self.h.player()
        self.h.food(1, site_world(house, SITE_A))
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.assertTrue(self.h.hook.CanStart(player, action.m_Target))
        self.assertEqual([], self.h.pilot_calls)
        self.h.hook.BeginSearch(action)
        self.assertEqual(1, self.h.houses.SessionCount())
        self.assertEqual([], self.h.pilot_calls)
        self.h.world.now += 6.5
        self.h.hook.CommitSearch(action)
        self.assertEqual(1, len(self.h.moves()))
        self.h.hook.EndSearch(action)
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertEqual([], self.h.pilot_calls)
        prop = N(GetType=lambda: 'SyntheticCabinet')
        pilot = FakeAction(player, FakeTarget(prop, [0., 0., 0.]))
        self.assertTrue(self.h.hook.CanStart(player, pilot.m_Target))
        self.h.hook.BeginSearch(pilot)
        self.h.hook.CanContinue(pilot)
        self.h.hook.CommitSearch(pilot)
        self.h.hook.EndSearch(pilot)
        self.assertEqual(['CanStart', 'BeginSearch', 'CanContinue', 'CommitSearch', 'EndSearch'], self.h.pilot_calls)

    def test_house_target_is_refused_while_the_service_is_stopped(self):
        house = self.h.house()
        player = self.h.player()
        self.h.houses_binding.houses = None
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.assertFalse(self.h.hook.CanStart(player, action.m_Target))
        self.h.hook.BeginSearch(action)
        self.assertEqual([], self.h.pilot_calls)

    def test_wrapper_site_has_the_real_interior_site_fields(self):
        self.assertTrue({'Id', 'SlotId', 'Target', 'Point', 'Phase', 'Owner', 'StartedAt', 'Deadline'} <= self.h.site_fields)


    def test_pilot_search_target_is_never_taken_by_the_house_service(self):
        # SearchType props must keep the existing prop route before House targeting,
        # including container types added beyond the original three pilot cases.
        from tools.package.interior_catalog import SEARCH_TYPES
        self.assertEqual(set(SEARCH_TYPES), self.h.pilot_types)
        for cls in sorted(self.h.pilot_types):
            self.h.pilot_calls.clear()
            cabinet = FakeHouse(cls, (5., 0., 5.))
            player = self.h.player('pilot_' + cls)
            target = FakeTarget(cabinet, [5., 1., 5.])
            self.assertFalse(self.h.env['HCSearchHouses'].IsHouseTarget(target))
            self.assertTrue(self.h.hook.CanStart(player, target))
            self.assertEqual(['CanStart'], self.h.pilot_calls)
            action = FakeAction(player, target)
            self.h.hook.BeginSearch(action)
            self.assertEqual(['CanStart', 'BeginSearch'], self.h.pilot_calls)
            self.assertEqual(0, self.h.houses.SessionCount())


class SourceShapeTests(unittest.TestCase):
    def sources(self):
        return {name: (LOOT / name).read_text() for name in HOUSE_FILES}

    def test_new_loot_sources_pass_the_native_compile_lint(self):
        for name, text in self.sources().items():
            self.assertEqual([], probe_runtime.lint_hook(text), name)

    def test_reserved_word_local_is_refused_by_the_lint(self):
        found = probe_runtime.lint_hook('class T\n{\n    void M()\n    {\n        vector local = "0 0 0";\n    }\n}\n')
        self.assertTrue(found, 'lint no longer rejects a local named local; update the guard')

    def test_created_objects_are_owned_with_ref(self):
        text = self.sources()['HCSearchHouses.c']
        self.assertRegex(text, r'class HCSearchHouseSession\s*\{[^}]*\bref HCInteriorSite Site;')
        for source in self.sources().values():
            for match in re.finditer(r'^    (?!static)(?!ref)(?:protected )?(array<[^;]*>|map<[^;]*>|HCSearch\w+|HCInterior\w+) (m_\w+|\w+)( = new [^;]*)?;', source, re.M):
                # weak members are allowed only for objects owned elsewhere
                self.assertNotIn(' = new ', match[0], match[0])
                self.assertFalse(match[1].startswith(('array<', 'map<')), match[0])
        self.assertNotIn('protected HCSearchHouseJournal m_Journal', text)


class StopTests(HouseCase):
    def test_stop_forgets_sessions_and_handles_but_keeps_journal(self):
        house = self.h.house()
        self.h.food(1, site_world(house, SITE_A))
        player = self.h.player()
        action = self.h.action(player, house, [0., 1., 0.], [0., 1., 1.])
        self.h.houses.Begin(action)
        files = dict(self.h.fs.files)
        self.h.houses.Stop()
        self.assertEqual(0, self.h.houses.SessionCount())
        self.assertFalse(self.h.houses.Started())
        self.assertEqual(files, self.h.fs.files)
        self.assertEqual([], self.h.rt.created)


if __name__ == '__main__':
    unittest.main()
