"""Search supply provider behavior with an explicitly synthetic native world.

The authored Enforce members of HCSearchSupplyProvider, HCSearchSupplyRegistry,
HCSearchEconomy and HCSearchEconomyStore are executed through the restricted
translator in test_group_server.execute_member. Entities, inventory, files, and
crashes are synthetic fakes; this file is NOT DayZ engine evidence.
"""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_group_server
from tests.unit.test_group_server import EArray, body, execute_member
from tests.unit.test_search_economy_policy import EMap

LOOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Loot'
FILES = ('HCSearchSupplyProvider.c', 'HCSearchNativeSupply.c', 'HCSearchEconomy.c',
         'HCSearchEconomyStore.c', 'HCSearchRules.c')
WORLD, BUILD, PIN = 'synthetic_world', 'synthetic_build', 'a' * 64
GROUND, CARGO, PROXYCARGO = 1, 3, 5
ROOT = '$profile:HollowCountry/SearchEconomy/epoch_1'


class Crash(Exception):
    """Synthetic process death at an exact point; never caught by authored code."""


class Location:
    def __init__(self):
        self.parent = None
        self.signature = None
        self.item = None
        self.type = 0

    def IsValid(self):
        return self.signature is not None

    def GetParent(self):
        return self.parent

    def GetType(self):
        return self.type

    def CompareLocationOnly(self, other):
        return self.signature == other.signature


class Item:
    """Fake native entity. Identity is the Python object plus persistent id."""

    def __init__(self, world, pid, typ='SyntheticFood', quantity=5., position=(0., 0., 0.),
                 where='ground', nominal=1):
        self.world = world
        self.pid, self.typ, self.quantity = pid, typ, quantity
        self.position, self.where, self.nominal = list(position), where, nominal
        world.items.append(self)

    def GetPersistentID(self): return self.pid
    def GetType(self): return self.typ
    def GetQuantity(self): return self.quantity
    def GetPosition(self): return self.position
    def IsInventoryItem(self): return True
    def IsMan(self): return False
    def IsAnimal(self): return False
    def IsZombie(self): return False
    def IsTakeable(self): return True
    def GetEconomyProfile(self): return N(GetNominal=lambda: self.nominal)
    def GetHierarchyRootPlayer(self): return self.where if isinstance(self.where, Player) else None
    def GetInventory(self): return N(GetCurrentInventoryLocation=self.current)

    def current(self, location):
        location.item = self
        location.type = {'ground': GROUND, 'proxy': PROXYCARGO}.get(self.where, CARGO)
        location.parent = self.where if isinstance(self.where, Player) else None
        location.signature = (location.type, id(self.where), tuple(self.position))
        return True


class Player:
    def __init__(self, world, ident, capacity=10, position=(0., 0., 0.)):
        self.world, self.ident, self.capacity, self.position = world, ident, capacity, list(position)
        self.cargo, self.alive, self.crash_after_move = [], True, False
        self.during_move = None  # concurrent callback inside the native move

    def IsAlive(self): return self.alive
    def IsUnconscious(self): return False
    def GetPosition(self): return self.position
    def GetIdentity(self): return N(GetId=lambda: self.ident, GetPlayer=lambda: self)
    def GetInventory(self): return N(FindFreeLocationFor=self.find, TakeToDst=self.take)

    def find(self, item, flags, destination):
        if len(self.cargo) >= self.capacity:
            return False
        destination.parent, destination.item, destination.signature = self, item, ('dst', id(self))
        return True

    def take(self, mode, source, destination):
        self.world.events.append('move:' + str(item_id(source.item)))
        if self.during_move:
            self.during_move()
        source.item.where = self
        self.cargo.append(source.item)
        if self.crash_after_move:
            raise Crash('died after native move, before result journal')
        return True


def item_id(item):
    return '_'.join(str(part) for part in item.pid)


class World:
    def __init__(self):
        self.items, self.events, self.players, self.now = [], [], [], 1000.
        self.extra_objects = [N(name='building_without_inventory_item')]
        self.extra_cargos = []


class FS:
    def __init__(self):
        self.files, self.dirs, self.crash_before, self.torn = {}, set(), None, None


class Bound:
    """Instance of an authored class; methods dispatch to authored source."""
    FILE = ''

    def __init__(self, rt, **fields):
        self.__dict__.update(fields)
        self._rt = rt

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        if self.FILE not in self._rt.methods:
            raise AssertionError('missing authored search supply source: ' + self.FILE)
        if name not in self._rt.methods[self.FILE]:
            raise AttributeError(name)
        return lambda *args: self._rt.call(self.FILE, name, self, *args)


class Registry(Bound): FILE = 'HCSearchNativeSupply.c'
class Economy(Bound): FILE = 'HCSearchEconomy.c'
class Store(Bound): FILE = 'HCSearchEconomyStore.c'
class Provider(Bound): FILE = 'HCSearchSupplyProvider.c'


class Static:
    def __init__(self, rt, file):
        self._rt, self._file = rt, file

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *args: self._rt.call(self._file, name, N(), *args)


class RegistryFactory(Static):
    def __call__(self):
        return Registry(self._rt, m_Entries=EArray(), m_SourceId='', m_SourcePin='', m_WorldName='',
                        m_Build='', m_Opened=False, m_Sealed=False, m_Transferring=False)


def read(name):
    path = LOOT / name
    if not path.is_file():
        raise AssertionError('missing authored search supply source: ' + str(path))
    return path.read_text()


def method_names(source):
    return set(re.findall(r'^    (?:static |protected )?(?:ref )?[\w<>]+ (\w+)\(', source, re.M))


class Runtime:
    """One 'process lifetime': fresh authored objects over shared world + files."""

    def __init__(self, world, fs, ce=True, server=True):
        self.world, self.fs, self.log, self.ce, self.server = world, fs, [], ce, server
        self.created = []
        self.translated = {}  # (file, member) -> translated function; translation is the slow part
        self.sources = {name: read(name) for name in FILES if (LOOT / name).is_file()}
        self.methods = {name: method_names(text) for name, text in self.sources.items()}
        self.s_Registered = EArray()
        self.s_Registries = EArray()
        self.s_Active = None
        game = N(IsServer=lambda: self.server, GetVersion=lambda: BUILD, GetWorldName=lambda: WORLD,
                 GetObjectsAtPosition3D=self.scan, GetPlayers=lambda out: out.extend(world.players),
                 GetTickTime=lambda: world.now)
        # Any creation/deletion primitive is forbidden: calling it fails the test.
        forbidden = {name: self.forbid(name) for name in (
            'CreateObject', 'CreateObjectEx', 'ObjectDelete', 'SpawnLoot', 'SpawnEntity',
            'SpawnSingleEntity', 'CreateEntityInCargo', 'CreateInInventory')}
        self.env = {
            'str': str, 'EArray': EArray, 'EMap': EMap, 'Print': self.log.append,
            'GetGame': lambda: game, 'GetCEApi': lambda: object() if self.ce else None,
            'InventoryLocation': Location,
            'InventoryLocationType': N(UNKNOWN=0, GROUND=GROUND, ATTACHMENT=2, CARGO=CARGO,
                                       HANDS=4, PROXYCARGO=PROXYCARGO),
            'FindInventoryLocationType': N(CARGO=2), 'InventoryMode': N(SERVER=1),
            's_Registered': self.s_Registered, 's_Registries': self.s_Registries,
            'HCSearchScanBudget': self.budget_factory,
            'vector': N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
            'EntityAI': N(Cast=lambda obj: obj if hasattr(obj, 'IsInventoryItem') else None),
            'FileExist': lambda p: p in fs.files or p in fs.dirs, 'MakeDirectory': self.mkdir,
            'write_json': self.write_json, 'load_manifest': self.load_manifest,
            'load_manifest_value': lambda p, limit: self.parse_manifest(fs.files.get(p)),
            'load_record': lambda p: self.parse_record(fs.files.get(p)),
            'encode': lambda v: json.dumps(v, default=vars, sort_keys=True),
            'HCSearchRules': Static(self, 'HCSearchRules.c'),
            'HCSearchSupplyRegistry': RegistryFactory(self, 'HCSearchNativeSupply.c'),
            'HCSearchEconomyStore': lambda: Store(self, m_Root='', m_Manifest=None, m_Fault=False),
            'HCSearchEconomy': lambda: Economy(self, m_Enabled=True, m_Ready=False, m_Busy=False,
                                               m_Manifest=None, m_Store=None, m_Source=None,
                                               m_Phases=EArray(), s_Active=None),
            'HCSearchOwnedSupply': lambda: N(ItemHandle=None, SupplyId='', SourceRecordId='', ItemClass='',
                                             Quantity=0., Attempted=False, OriginalLocation=None),
            'HCSearchEntry': lambda: N(SiteId='', SupplyId='', ItemClass=''),
            'HCSearchManifest': lambda: N(Version=0, Epoch=0, WorldName='', Build='', SourceId='',
                                          SourcePin='', Entries=EArray()),
            'HCSearchRecord': lambda: N(Version=0, Epoch=0, Phase=0, WorldName='', Build='', SourceId='',
                                        SourcePin='', SiteId='', SupplyId='', ItemClass='', ActorId=''),
            'HCSearchSupplyPlan': lambda: N(Registry=None, Manifest=None, InitializeNewEpoch=False),
        }
        self.env.update(forbidden)

    def budget_factory(self):
        """Instance of the authored HCSearchScanBudget class; defaults come from its source."""
        text = self.sources.get('HCSearchSupplyProvider.c', '')
        block = re.search(r'class HCSearchScanBudget\s*\{(.*?)\n\}', text, re.S)
        fields = {m[1]: int(m[2]) for m in re.finditer(r'\bint (\w+) = (\d+);', block[1])} if block else {}
        return N(Overflow=False, Reason='', **fields)

    def forbid(self, name):
        def call(*args):
            self.created.append(name)
            raise AssertionError('forbidden item creation/removal primitive: ' + name)
        return call

    # ---- synthetic native world -------------------------------------------------
    def scan(self, position, radius, objects, cargos):
        for item in self.world.items:
            near = sum((a - b) ** 2 for a, b in zip(item.position, position)) <= radius ** 2 + 4.0
            if near and (item.where == 'ground' or isinstance(item.where, Player)):
                objects.Insert(item)
        objects.extend(self.world.extra_objects)
        proxies = [i for i in self.world.items if i.where == 'proxy' and
                   sum((a - b) ** 2 for a, b in zip(i.position, position)) <= radius ** 2 + 4.0]
        if proxies:
            cargos.Insert(N(IsProxyCargo=lambda: True, GetItemCount=lambda: len(proxies),
                            GetItem=lambda index: proxies[index]))
        cargos.Insert(N(IsProxyCargo=lambda: False, GetItemCount=lambda: 1,
                        GetItem=lambda index: self.world.items[0]))  # must be ignored
        for extra in self.world.extra_cargos:
            cargos.Insert(extra)

    def mkdir(self, path):
        self.fs.dirs.add(path)
        return True

    def write_json(self, path, value, limit):
        if path in self.fs.files:
            return False
        text = json.dumps(value, default=vars, sort_keys=True)
        if len(text) > limit:
            return False
        if self.fs.crash_before and self.fs.crash_before in path:
            raise Crash('died before writing ' + path)
        if self.fs.torn and self.fs.torn in path:
            self.fs.files[path] = text[:len(text) // 2]
            raise Crash('torn write ' + path)
        self.fs.files[path] = text
        return True

    @staticmethod
    def parse_manifest(text):
        try:
            data = json.loads(text)
            data['Entries'] = EArray(N(**entry) for entry in data['Entries'])
            return N(**data)
        except (TypeError, ValueError, KeyError):
            return None

    @staticmethod
    def parse_record(text):
        try:
            return N(**json.loads(text))
        except (TypeError, ValueError):
            return None

    def load_manifest(self, store, path, limit):
        manifest = self.parse_manifest(self.fs.files.get(path))
        if manifest is None:
            return False
        store.m_Manifest = manifest
        return True

    # ---- source translation -----------------------------------------------------
    def call(self, filename, name, instance, *args):
        cached = self.translated.get((filename, name))
        if cached:
            return cached(instance, *args)
        if filename not in self.sources:
            raise AssertionError('missing authored search supply source: ' + filename)
        source = self.sources[filename]
        match = re.search(r'\b(?:static )?[\w<>]+ ' + name + r'\(([^)]*)\)\s*\{', source)
        if not match:
            raise AssertionError('missing authored method: ' + filename + ' ' + name)
        text = body(source, match.end())
        text = re.sub(r'#ifdef\s+\w+.*?#endif', '', text, flags=re.S)
        text = re.sub(r'JsonFileLoader<HCSearchManifest>.MakeData\(([^,]+), (\w+), \w+\)',
                      r'((\2 := encode(\1)) != null)', text)
        text = text.replace('HCSearchJson<HCSearchManifest>.Load(path, 8388608, m_Manifest)',
                            'load_manifest(self, path, 8388608)')
        text = re.sub(r'HCSearchJson<HCSearchManifest>.Load\(([^,]+), 8388608, (\w+)\)',
                      r'((\2 := load_manifest_value(\1, 8388608)) != null)', text)
        text = re.sub(r'HCSearchJson<HCSearchRecord>.Load\(PathFor\(index, kind\), 8192, (\w+)\)',
                      r'((\1 := load_record(PathFor(index, kind))) != null)', text)
        text = text.replace('HCSearchJson<HCSearchManifest>.WriteNew(', 'write_json(')
        text = text.replace('HCSearchJson<HCSearchRecord>.WriteNew(', 'write_json(')
        text = re.sub(r'map<[^>]+> (\w+) = new map<[^>]+>', r'\1 = EMap()', text)
        text = re.sub(r'\b(?:ref )?array<[^>]+> (\w+) = new array<[^>]+>', r'\1 = EArray()', text)
        text = re.sub(r'new array<[^>]+>', 'EArray()', text)
        text = re.sub(r'(\w+)\.Get\(index\)', r'\1[index]', text)
        text = text.replace('.IndexOf(', '.find(')
        text = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', text)
        text = re.sub(r'int ([\w, ]+);', lambda m: ' = '.join(m[1].replace(' ', '').split(',')) + ' = 0;', text)
        text = re.sub(r'(\w+)\.GetPersistentID\(([^)]+)\)', r'\2 = \1.GetPersistentID()', text)
        text = re.sub(r'GetGame\(\)\.GetVersion\((\w+)\)', r'\1 = GetGame().GetVersion()', text)
        text = re.sub(r'GetGame\(\)\.GetPlayers\((\w+)\)', r'GetGame().GetPlayers(\1)', text)
        text = re.sub(r'\bs_Active\b', 'self.s_Active', text)
        text = re.sub(r'\bthis\b', 'self', text)
        # The restricted translator lacks "else if"; nest it (same semantics).
        text = re.sub(r'else if \(([^\n]*)\) (return [^;\n]*;)', r'else { if (\1) \2 }', text)
        types = (r'HCSearch\w+|EntityAI|PlayerBase|InventoryLocation|CEItemProfile|Object|Man|CargoBase|string|vector|float')
        text = re.sub(r'\b(?:' + types + r') (?=\w+\s*=)', '', text)
        text = re.sub(r'\b(?:' + types + r') (\w+)\s*;', r'\1 = null;', text)
        text = re.sub(r'while \(([^\n]*)\)', r'while \1:', text)
        text = re.sub(r'new (HCSearch\w+|InventoryLocation)(?!\w)(?:\(\))?', r'\1()', text)
        for method in self.methods[filename]:
            text = re.sub(r'(?<![\w.])' + method + r'\(', 'self.' + method + '(', text)
        captured = []

        def capture(code, scope):
            exec(code, scope)
            captured.append(scope['member'])  # before a nested member redefines the name
        test_group_server.exec = capture
        try:
            return execute_member('bool ' + name + '(' + match[1] + ') {' + text + '}', name, self.env, instance, *args)
        finally:
            test_group_server.__dict__.pop('exec', None)
            if captured:
                self.translated[(filename, name)] = captured[0]

    def provider(self):
        return Provider(self)

    def economy(self):
        return self.env['HCSearchEconomy']()


def volume(site, center=(0., 0., 0.), radius=3., classes=('SyntheticFood',)):
    return N(SiteId=site, Center=list(center), Radius=radius, Classes=EArray(classes))


class SupplyCase(unittest.TestCase):
    def setUp(self):
        self.world, self.fs = World(), FS()
        self.actor = Player(self.world, 'actor_a')
        self.world.players = []
        self.rt = Runtime(self.world, self.fs)

    def restart(self, **kw):
        """New process: authored objects are rebuilt; world/files survive."""
        self.rt = Runtime(self.world, self.fs, **kw)
        return self.rt

    def item(self, n, **kw):
        return Item(self.world, (n, 2, 3, 4), **kw)

    def prepare(self, volumes, allow=True, epoch=1, rt=None):
        rt = rt or self.rt
        return rt.provider().Prepare(epoch, 'synthetic_spawner', PIN, EArray(volumes), allow)

    def bind(self, plan, rt=None):
        rt = rt or self.rt
        economy = rt.economy()
        ok = economy.Open(plan.Manifest, plan.Registry, plan.InitializeNewEpoch)
        return economy, ok

    def moves(self):
        return [e for e in self.world.events if e.startswith('move:')]


class DiscoveryTests(SupplyCase):
    def test_discovery_registers_distinct_native_items_and_ignores_ineligible(self):
        a = self.item(1, position=(0, 0, 0))
        self.item(2, position=(0.5, 0, 0), typ='SyntheticWeapon')          # class not allowed here
        self.item(3, position=(3.5, 0, 0))                                # listed by scan, outside volume
        self.item(4, position=(0.2, 0, 0), nominal=0)                     # not CE-profiled
        held = self.item(5, position=(0.1, 0, 0), where=self.actor)       # inside a player
        proxy = self.item(6, position=(10, 0, 0), where='proxy')
        plan = self.prepare([volume('site_a'), volume('site_b', center=(10, 0, 0))])
        self.assertIsNotNone(plan)
        entries = plan.Manifest.Entries
        self.assertEqual([('site_a', '1_2_3_4', 'SyntheticFood'), ('site_b', '6_2_3_4', 'SyntheticFood')],
                         [(e.SiteId, e.SupplyId, e.ItemClass) for e in entries])
        self.assertTrue(plan.InitializeNewEpoch)
        self.assertEqual([a, proxy], [s.ItemHandle for s in plan.Registry.m_Entries])
        self.assertNotIn(held, [s.ItemHandle for s in plan.Registry.m_Entries])
        self.assertEqual([], self.rt.created)

    def test_one_native_item_is_never_assigned_to_two_overlapping_sites(self):
        self.item(1)
        plan = self.prepare([volume('site_a'), volume('site_b')])
        self.assertEqual(['1_2_3_4', ''], [e.SupplyId for e in plan.Manifest.Entries])
        self.assertEqual(['SyntheticFood', ''], [e.ItemClass for e in plan.Manifest.Entries])

    def test_empty_world_never_writes_an_all_empty_epoch(self):
        self.assertIsNone(self.prepare([volume('site_a')]))
        self.assertNotIn(ROOT, self.fs.dirs)
        self.assertEqual({}, self.fs.files)

    def test_new_epoch_needs_explicit_flag_and_an_empty_server(self):
        self.item(1)
        self.assertIsNone(self.prepare([volume('site_a')], allow=False))
        self.world.players = [self.actor]
        self.assertIsNone(self.prepare([volume('site_a')]))
        self.world.players = []
        self.assertIsNotNone(self.prepare([volume('site_a')]))

    def test_invalid_reviewed_volumes_fail_closed(self):
        self.item(1)
        bad = [[], [volume('site_a'), volume('site_a')], [volume('site_a', radius=0.)],
               [volume('site_a', radius=8.5)], [volume('site_a', classes=())],
               [volume('bad site')], [volume('site_a', classes=('bad class',))]]
        for volumes in bad:
            with self.subTest(volumes=[v.SiteId for v in volumes]):
                self.assertIsNone(self.prepare(volumes))

    def test_failed_refusal_releases_handles_so_a_corrected_retry_can_bind(self):
        self.item(1)
        self.world.players = [self.actor]
        self.assertIsNone(self.prepare([volume('site_a')]))
        self.world.players = []
        self.assertIsNotNone(self.prepare([volume('site_a')]))

    def test_proxy_cargo_origin_is_an_accepted_native_location(self):
        proxy = self.item(6, position=(10, 0, 0), where='proxy')
        plan = self.prepare([volume('site_b', center=(10, 0, 0))])
        self.assertEqual([proxy], [s.ItemHandle for s in plan.Registry.m_Entries])


class FiniteDepletionTests(SupplyCase):
    def started(self, count=2, sites=3):
        items = [self.item(n) for n in range(1, count + 1)]
        plan = self.prepare([volume('site_' + str(n)) for n in range(sites)])
        economy, ok = self.bind(plan)
        self.assertTrue(ok)
        return items, economy

    def test_each_item_moves_once_same_entity_then_supply_is_depleted(self):
        items, economy = self.started()
        self.assertEqual([2, 2, 2], [economy.Grant('site_' + str(n), self.actor) for n in range(3)])
        self.assertEqual(['move:1_2_3_4', 'move:2_2_3_4'], self.moves())
        self.assertEqual(items, self.actor.cargo)
        self.assertEqual([5., 5.], [i.quantity for i in items])
        for n in range(3):
            self.assertEqual(2, economy.Grant('site_' + str(n), self.actor))
        self.assertEqual(2, len(self.moves()))
        self.assertEqual([], self.rt.created)

    def test_depletion_survives_restart_and_never_refills_from_new_ground_items(self):
        items, economy = self.started()
        for n in range(3):
            self.assertEqual(2, economy.Grant('site_' + str(n), self.actor))
        rt = self.restart()
        late = self.item(9)
        plan = self.prepare([volume('site_' + str(n)) for n in range(3)], allow=False, rt=rt)
        economy, ok = self.bind(plan, rt)
        self.assertTrue(ok)
        self.assertEqual([2, 2, 2], list(economy.m_Phases))
        self.assertEqual([], list(plan.Registry.m_Entries))
        for n in range(3):
            self.assertEqual(2, economy.Grant('site_' + str(n), self.actor))
        self.assertEqual(2, len(self.moves()))
        self.assertEqual('ground', late.where)
        self.assertEqual([], rt.created)


class ConcurrencyTests(SupplyCase):
    def test_second_searcher_inside_native_move_is_busy_and_cannot_double_spend(self):
        item = self.item(1)
        plan = self.prepare([volume('site_a')])
        economy, _ = self.bind(plan)
        other = Player(self.world, 'actor_b')
        seen = []
        self.actor.during_move = lambda: seen.append(economy.Grant('site_a', other))
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.assertEqual([-3], seen)
        self.assertEqual(2, economy.Grant('site_a', other))
        self.assertEqual(1, len(self.moves()))
        self.assertEqual([item], self.actor.cargo)
        self.assertEqual([], other.cargo)

    def test_searchers_on_different_sites_never_receive_the_same_entity(self):
        self.item(1)
        self.item(2)
        plan = self.prepare([volume('site_a'), volume('site_b')])
        economy, _ = self.bind(plan)
        other = Player(self.world, 'actor_b')
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.assertEqual(2, economy.Grant('site_b', other))
        self.assertEqual({'1_2_3_4', '2_2_3_4'}, {item_id(i) for i in self.actor.cargo + other.cargo})
        self.assertEqual(2, len(self.moves()))


class InventoryFullTests(SupplyCase):
    def test_full_inventory_before_admission_loses_and_duplicates_nothing_and_stays_available(self):
        item = self.item(1)
        plan = self.prepare([volume('site_a')])
        economy, _ = self.bind(plan)
        self.actor.capacity = 0
        self.assertEqual(-4, economy.Grant('site_a', self.actor))
        self.assertEqual([], self.moves())
        self.assertEqual('ground', item.where)
        self.assertEqual([0], list(economy.m_Phases))
        self.assertFalse([p for p in self.fs.files if 'claim_' in p])  # no journal intent
        self.actor.capacity = 1
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.assertEqual([item], self.actor.cargo)

    def test_space_lost_during_native_callbacks_retains_item_and_does_not_repeat(self):
        item = self.item(1)
        plan = self.prepare([volume('site_a')])
        economy, _ = self.bind(plan)
        calls = []
        original = self.actor.find

        def find(it, flags, destination):
            calls.append(1)
            return original(it, flags, destination) if len(calls) < 3 else False
        self.actor.GetInventory = lambda: N(FindFreeLocationFor=find, TakeToDst=self.actor.take)
        self.assertEqual(4, economy.Grant('site_a', self.actor))
        self.assertEqual('ground', item.where)
        self.assertEqual([], self.actor.cargo)
        self.assertEqual([], self.moves())
        self.assertEqual(4, economy.Grant('site_a', self.actor))
        self.assertEqual([], self.moves())


class CrashRecoveryTests(SupplyCase):
    def setUp(self):
        super().setUp()
        self.item1 = self.item(1)
        self.volumes = [volume('site_a')]
        self.plan = self.prepare(self.volumes)
        self.economy, ok = self.bind(self.plan)
        self.assertTrue(ok)

    def restart_bind(self):
        rt = self.restart()
        plan = self.prepare(self.volumes, allow=False, rt=rt)
        self.assertIsNotNone(plan)
        self.assertFalse(plan.InitializeNewEpoch)
        economy, ok = self.bind(plan, rt)
        return rt, plan, economy, ok

    def assert_quarantined_after(self, where_after_restart):
        self.item1.where = where_after_restart
        self.item1.position = [0., 0., 0.]
        rt, plan, economy, ok = self.restart_bind()
        self.assertTrue(ok)
        before = len(self.moves())
        self.assertEqual([3], list(economy.m_Phases))
        self.assertEqual(3, economy.Grant('site_a', self.actor))
        self.assertEqual(before, len(self.moves()))
        self.assertEqual([], rt.created)
        return plan

    def test_crash_after_native_move_before_result_quarantines_with_item_in_inventory(self):
        self.actor.crash_after_move = True
        with self.assertRaises(Crash):
            self.economy.Grant('site_a', self.actor)
        self.assertIs(self.actor, self.item1.where)
        self.actor.crash_after_move = False
        plan = self.assert_quarantined_after(self.actor)
        self.assertEqual([], list(plan.Registry.m_Entries))  # held by player: not re-registered

    def test_crash_after_move_with_player_save_lost_reverts_to_floor_but_never_replays(self):
        self.actor.crash_after_move = True
        with self.assertRaises(Crash):
            self.economy.Grant('site_a', self.actor)
        self.actor.crash_after_move = False
        self.actor.cargo.clear()
        plan = self.assert_quarantined_after('ground')
        self.assertEqual(1, len(plan.Registry.m_Entries))  # same entity, one copy only
        self.assertEqual(1, len([i for i in self.world.items if item_id(i) == '1_2_3_4']))

    def test_crash_before_result_journal_or_torn_result_is_terminal(self):
        for mode in ('crash_before', 'torn'):
            with self.subTest(mode=mode):
                self.setUp()
                setattr(self.fs, mode, 'result_')
                with self.assertRaises(Crash):
                    self.economy.Grant('site_a', self.actor)
                setattr(self.fs, mode, None)
                self.assert_quarantined_after(self.actor)

    def test_crash_before_any_journal_write_changes_nothing_and_stays_available(self):
        self.fs.crash_before = 'claim_'
        with self.assertRaises(Crash):
            self.economy.Grant('site_a', self.actor)
        self.fs.crash_before = None
        self.assertEqual([], self.moves())
        rt, plan, economy, ok = self.restart_bind()
        self.assertTrue(ok)
        self.assertEqual([0], list(economy.m_Phases))
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.assertEqual(1, len(self.moves()))

    def test_crash_after_claim_before_attempt_is_quarantined_not_replayed(self):
        self.fs.crash_before = 'attempt_'
        with self.assertRaises(Crash):
            self.economy.Grant('site_a', self.actor)
        self.assertEqual([], self.moves())
        self.fs.crash_before = None
        self.assert_quarantined_after('ground')
        self.assertEqual([], self.moves())

    def test_missing_item_at_restart_is_unavailable_and_nothing_is_created(self):
        self.world.items.remove(self.item1)
        rt, plan, economy, ok = self.restart_bind()
        self.assertTrue(ok)
        self.assertEqual([], list(plan.Registry.m_Entries))
        self.assertEqual(-4, economy.Grant('site_a', self.actor))
        self.assertEqual([0], list(economy.m_Phases))
        self.assertEqual([], rt.created)
        self.assertEqual([], self.moves())

    def test_moved_or_changed_item_is_not_rebound_as_the_manifest_supply(self):
        self.item1.typ = 'SyntheticWeapon'
        rt, plan, economy, ok = self.restart_bind()
        self.assertEqual([], list(plan.Registry.m_Entries))
        self.assertEqual(-4, economy.Grant('site_a', self.actor))


class CorruptStoreTests(SupplyCase):
    def setUp(self):
        super().setUp()
        self.item(1)
        self.volumes = [volume('site_a')]
        plan = self.prepare(self.volumes)
        economy, ok = self.bind(plan)
        self.assertTrue(ok)
        self.path = ROOT + '/manifest.json'

    def prepare_after_restart(self, allow=True, volumes=None):
        rt = self.restart()
        files = dict(self.fs.files)
        plan = self.prepare(volumes or self.volumes, allow=allow, rt=rt)
        self.assertEqual(files, self.fs.files)  # preserve evidence; never rewrite
        return rt, plan

    def test_garbage_empty_or_truncated_manifest_never_reinitializes_or_rescans(self):
        good = self.fs.files[self.path]
        for text in ('{not json', '', good[:len(good) // 2], '[]', '{"Version": 1}'):
            with self.subTest(text=text[:12]):
                self.fs.files[self.path] = text
                rt, plan = self.prepare_after_restart()
                self.assertIsNone(plan)
                self.assertEqual([], rt.created)

    def test_existing_root_without_manifest_is_preserved_not_refilled(self):
        del self.fs.files[self.path]
        rt, plan = self.prepare_after_restart()
        self.assertIsNone(plan)

    def test_stored_identity_or_site_set_change_requires_migration(self):
        for mutate in (lambda m: m.update(SourcePin='b' * 64), lambda m: m.update(WorldName='other'),
                       lambda m: m.update(Build='other'), lambda m: m.update(SourceId='other'),
                       lambda m: m.update(Epoch=2), lambda m: m['Entries'][0].update(SiteId='other_site')):
            with self.subTest():
                good = self.fs.files[self.path]
                data = json.loads(good)
                mutate(data)
                self.fs.files[self.path] = json.dumps(data, sort_keys=True)
                rt, plan = self.prepare_after_restart()
                self.assertIsNone(plan)
                self.fs.files[self.path] = good
        rt, plan = self.prepare_after_restart(volumes=[volume('site_a'), volume('site_b')])
        self.assertIsNone(plan)

    def test_corrupt_journal_record_quarantines_site_and_is_never_replayed(self):
        item = self.world.items[-1]
        self.fs.files[ROOT + '/claim_0.json'] = '{broken'
        rt = self.restart()
        plan = self.prepare(self.volumes, allow=False, rt=rt)
        economy, ok = self.bind(plan, rt)
        self.assertEqual([3], list(economy.m_Phases))
        self.assertEqual(3, economy.Grant('site_a', self.actor))
        self.assertEqual([], self.moves())
        self.assertEqual('ground', item.where)


class ClockRollbackTests(SupplyCase):
    def test_availability_never_depends_on_wall_or_tick_time(self):
        for name in ('HCSearchSupplyProvider.c', 'HCSearchNativeSupply.c', 'HCSearchEconomy.c',
                     'HCSearchEconomyStore.c'):
            code = re.sub(r'//[^\n]*', '', read(name))
            self.assertIsNone(re.search(r'GetTickTime|GetSystemTime|GetYearMonthDay|GetTime|Date', code), name)
        self.item(1)
        self.item(2)
        volumes = [volume('site_a'), volume('site_b')]
        plan = self.prepare(volumes)
        economy, _ = self.bind(plan)
        self.world.now = 5000.
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.world.now = 10.  # clock rolled far back across a restart
        rt = self.restart()
        plan = self.prepare(volumes, allow=False, rt=rt)
        economy, ok = self.bind(plan, rt)
        self.assertTrue(ok)
        self.assertEqual([2, 0], list(economy.m_Phases))
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.world.now = 99999.
        self.assertEqual(2, economy.Grant('site_b', self.actor))
        self.assertEqual(['move:1_2_3_4', 'move:2_2_3_4'], self.moves())


class ProviderUnavailableTests(SupplyCase):
    def test_missing_ce_api_or_client_refuses_without_binding_or_creating(self):
        self.item(1)
        for kw in ({'ce': False}, {'server': False}):
            with self.subTest(kw=kw):
                rt = self.restart(**kw)
                self.assertIsNone(self.prepare([volume('site_a')], rt=rt))
                self.assertEqual([], rt.created)
                self.assertEqual({}, self.fs.files)
                self.assertEqual(set(), self.fs.dirs)

    def test_provider_source_contains_no_creation_or_deletion_primitive(self):
        forbidden = r'CreateObject|CreateEntityIn|CreateInInventory|SpawnLoot|SpawnEntity|SpawnSingleEntity|SpawnDE|' \
                    r'SpawnGroup|ObjectDelete|SetQuantity|AddQuantity|SetLifetime|IncreaseLifetime|' \
                    r'TakeEntityToCargo|ServerTake|LocalTake|SwapEntities|ReplaceItem|ECE_'
        for name in ('HCSearchSupplyProvider.c', 'HCSearchNativeSupply.c'):
            code = re.sub(r'//[^\n]*', '', read(name))
            self.assertIsNone(re.search(forbidden, code), name)
        self.assertRegex(read('HCSearchSupplyProvider.c'), r'GetObjectsAtPosition3D')
        self.assertNotRegex(re.sub(r'//[^\n]*', '', read('HCSearchSupplyProvider.c')), r'\.Grant\(|\.Transfer\(')

    def test_unprepared_provider_leaves_module_gate_closed_so_search_is_refused(self):
        from tests.unit.test_search_economy_integration import invoke as module_invoke
        self.assertIsNone(self.prepare([volume('site_a')]))  # nothing native to bind
        t = N(m_Ready=True, m_SearchProof=True, m_Store=N(Healthy=lambda: True), m_Economy=None)
        env = {'HCServer': N(Get=lambda: N(GetSettings=lambda: N(EnableInteriors=True, EnableSearch=True))),
               'HCInteriorRules': N(MaySearch=lambda *args: all(args)), 'GetGame': lambda: N(IsServer=lambda: True)}
        site = N(Id='site_a', Phase=0)
        self.assertFalse(module_invoke('SearchGate', env, t, self.actor, site))


class RegistryOriginTests(SupplyCase):
    def test_registry_still_rejects_non_ground_cargo_proxy_origins(self):
        registry = self.rt.env['HCSearchSupplyRegistry']()
        self.assertTrue(registry.BindSource('synthetic_spawner', PIN, WORLD, BUILD))
        attached = self.item(7)
        original = attached.current

        def current(location):
            original(location)
            location.type = 2  # ATTACHMENT
            return True
        attached.current = current
        attached.GetInventory = lambda: N(GetCurrentInventoryLocation=current)
        self.assertFalse(registry.RegisterOwned(attached, 'record_attached'))


class OwnershipLifecycleTests(SupplyCase):
    """Process-static ownership must not outlive a clean economy shutdown."""

    def two_sites(self):
        a, b = self.item(1), self.item(2)
        return a, b, [volume('site_a'), volume('site_b')]

    def test_clean_stop_then_rebind_in_the_same_process_binds_untouched_supplies(self):
        a, b, volumes = self.two_sites()
        old_plan = self.prepare(volumes)
        economy, ok = self.bind(old_plan)
        self.assertTrue(ok)
        economy.Stop()
        plan = self.prepare(volumes, allow=False)
        self.assertIsNotNone(plan)
        self.assertEqual([a, b], [s.ItemHandle for s in plan.Registry.m_Entries])
        economy, ok = self.bind(plan)
        self.assertTrue(ok)
        self.assertEqual([2, 2], [economy.Grant('site_a', self.actor), economy.Grant('site_b', self.actor)])
        self.assertEqual(['move:1_2_3_4', 'move:2_2_3_4'], self.moves())
        self.assertEqual([], self.rt.created)

    def test_a_retired_registry_is_disabled_and_cannot_move_anything(self):
        a, b, volumes = self.two_sites()
        old_plan = self.prepare(volumes)
        old_economy, _ = self.bind(old_plan)
        old_economy.Stop()
        self.assertIsNotNone(self.prepare(volumes, allow=False))
        self.assertFalse(old_plan.Registry.ReadyFor(old_plan.Manifest))
        self.assertEqual([], list(old_plan.Registry.m_Entries))
        self.assertFalse(old_plan.Registry.CanTransfer(old_plan.Manifest.Entries[0], self.actor))
        self.assertEqual(4, old_plan.Registry.Transfer(old_plan.Manifest.Entries[0], self.actor))
        self.assertFalse(old_plan.Registry.RegisterOwned(a, 'late_record'))
        self.assertFalse(old_plan.Registry.BindSource('synthetic_spawner', PIN, WORLD, BUILD))
        self.assertEqual([], self.moves())

    def test_consumed_item_stays_depleted_across_a_same_process_rebind(self):
        a, b, volumes = self.two_sites()
        economy, _ = self.bind(self.prepare(volumes))
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        economy.Stop()
        plan = self.prepare(volumes, allow=False)
        self.assertIsNotNone(plan)
        self.assertEqual([b], [s.ItemHandle for s in plan.Registry.m_Entries])  # a is in a player
        economy, ok = self.bind(plan)
        self.assertTrue(ok)
        self.assertEqual([2, 0], list(economy.m_Phases))
        # The player drops it back inside the reviewed volume: the journal still wins.
        a.where, a.position = 'ground', [0., 0., 0.]
        economy.Stop()
        plan = self.prepare(volumes, allow=False)
        economy, ok = self.bind(plan)
        self.assertTrue(ok)
        self.assertEqual(2, economy.Grant('site_a', self.actor))
        self.assertEqual('ground', a.where)
        self.assertEqual(['move:1_2_3_4'], self.moves())
        self.assertEqual(2, economy.Grant('site_b', self.actor))
        self.assertEqual(['move:1_2_3_4', 'move:2_2_3_4'], self.moves())

    def test_deleted_handles_no_longer_count_toward_the_global_limit(self):
        registry = self.rt.env['HCSearchSupplyRegistry']()
        self.assertTrue(registry.BindSource('synthetic_spawner', PIN, WORLD, BUILD))
        self.rt.s_Registered.extend([None] * 4096)  # engine nulls handles of deleted entities
        item = self.item(1)
        self.assertTrue(registry.RegisterOwned(item, 'record_1'))
        self.assertEqual([item], list(self.rt.s_Registered))

    def test_deleted_owned_entries_are_pruned_and_never_become_available_again(self):
        registry = self.rt.env['HCSearchSupplyRegistry']()
        self.assertTrue(registry.BindSource('synthetic_spawner', PIN, WORLD, BUILD))
        first, second = self.item(1), self.item(2)
        self.assertTrue(registry.RegisterOwned(first, 'record_1'))
        self.world.items.remove(first)
        registry.m_Entries[0].ItemHandle = None
        self.rt.s_Registered[0] = None
        self.assertTrue(registry.RegisterOwned(second, 'record_2'))
        self.assertEqual([second], [s.ItemHandle for s in registry.m_Entries])
        self.assertEqual([second], list(self.rt.s_Registered))
        entry = N(SupplyId='1_2_3_4', ItemClass='SyntheticFood')
        self.assertFalse(registry.CanTransfer(entry, self.actor))

    def test_refusal_after_registration_releases_every_handle_so_a_retry_can_bind(self):
        self.item(1)
        for n in range(100, 165):  # 65 distinct eligible items crowd site_b
            self.item(n, position=(10., 0., 0.))
        volumes = [volume('site_a'), volume('site_b', center=(10, 0, 0))]
        self.assertIsNone(self.prepare(volumes))
        self.assertEqual([], list(self.rt.s_Registered))
        self.assertEqual({}, self.fs.files)
        self.world.items[1:] = []
        plan = self.prepare([volume('site_a')])
        self.assertIsNotNone(plan)
        self.assertEqual(1, len(plan.Registry.m_Entries))


class CollectionCompletenessTests(SupplyCase):
    def stored_target(self, where='ground'):
        target = self.item(1, where=where)
        volumes = [volume('site_a')]
        economy, ok = self.bind(self.prepare(volumes))
        self.assertTrue(ok)
        rt = self.restart()
        return target, volumes, rt

    def crowd(self, count, first=1000):
        for n in range(first, first + count):
            self.item(n)

    def test_discovery_with_more_candidates_than_the_cap_refuses_instead_of_truncating(self):
        self.crowd(65)
        self.assertIsNone(self.prepare([volume('site_a')]))
        self.assertEqual({}, self.fs.files)
        self.assertEqual([], list(self.rt.s_Registered))
        self.assertEqual([], self.rt.created)

    def test_discovery_exactly_at_the_cap_still_succeeds(self):
        self.crowd(64)
        plan = self.prepare([volume('site_a')])
        self.assertIsNotNone(plan)
        self.assertEqual(1, len(plan.Registry.m_Entries))

    def test_stored_id_beyond_the_first_64_ground_candidates_is_still_rebound(self):
        target, volumes, rt = self.stored_target()
        self.crowd(100)
        self.world.items.remove(target)
        self.world.items.append(target)  # engine order puts the stored item last
        plan = self.prepare(volumes, allow=False, rt=rt)
        self.assertIsNotNone(plan)
        self.assertEqual([target], [s.ItemHandle for s in plan.Registry.m_Entries])

    def test_ground_candidates_cannot_crowd_out_a_stored_proxy_cargo_item(self):
        target, volumes, rt = self.stored_target(where='proxy')
        self.crowd(100)
        plan = self.prepare(volumes, allow=False, rt=rt)
        self.assertIsNotNone(plan)
        self.assertEqual([target], [s.ItemHandle for s in plan.Registry.m_Entries])

    def test_absent_stored_item_with_a_complete_scan_is_still_just_unavailable(self):
        target, volumes, rt = self.stored_target()
        self.world.items.remove(target)
        plan = self.prepare(volumes, allow=False, rt=rt)
        self.assertIsNotNone(plan)
        self.assertEqual([], list(plan.Registry.m_Entries))


class ScanBudgetTests(SupplyCase):
    LIMIT = 32768

    def stored(self, sites=1):
        items = [self.item(n) for n in range(1, sites + 1)]
        volumes = [volume('site_' + str(n)) for n in range(sites)]
        economy, ok = self.bind(self.prepare(volumes))
        self.assertTrue(ok)
        for item in items:
            self.world.items.remove(item)  # absence cannot be proven by an incomplete scan
        return volumes, self.restart()

    def counting_casts(self, rt):
        casts = []
        original = rt.env['EntityAI'].Cast
        rt.env['EntityAI'] = N(Cast=lambda obj: (casts.append(1), original(obj))[1])
        return casts

    def refused_without_touching_files(self, volumes, rt):
        before = dict(self.fs.files)
        self.assertIsNone(self.prepare(volumes, allow=False, rt=rt))
        self.assertEqual(before, self.fs.files)
        self.assertEqual([], list(rt.s_Registered))

    def test_object_walk_is_bounded_and_overflow_refuses_instead_of_assuming_absence(self):
        volumes, rt = self.stored()
        self.world.extra_objects = [N(name='tree')] * (self.LIMIT + 5000)
        casts = self.counting_casts(rt)
        self.refused_without_touching_files(volumes, rt)
        self.assertGreater(len(casts), 0)
        self.assertLessEqual(len(casts), self.LIMIT)

    def test_object_budget_is_shared_across_all_volumes_of_one_prepare(self):
        volumes, rt = self.stored(sites=2)
        self.world.extra_objects = [N(name='tree')] * 20000  # each volume alone is under the limit
        casts = self.counting_casts(rt)
        self.refused_without_touching_files(volumes, rt)
        self.assertLessEqual(len(casts), self.LIMIT)

    def test_cargo_with_more_slots_than_the_per_cargo_cap_refuses(self):
        volumes, rt = self.stored()
        calls = []
        self.world.extra_cargos = [N(IsProxyCargo=lambda: True, GetItemCount=lambda: 300,
                                     GetItem=lambda index: calls.append(index))]
        self.refused_without_touching_files(volumes, rt)
        self.assertLessEqual(len(calls), 256)

    def test_total_slot_walk_is_bounded_across_cargos(self):
        volumes, rt = self.stored()
        calls = []
        cargo = N(IsProxyCargo=lambda: True, GetItemCount=lambda: 100, GetItem=lambda index: calls.append(index))
        self.world.extra_cargos = [cargo] * 400  # 40000 slots in total
        self.refused_without_touching_files(volumes, rt)
        self.assertGreater(len(calls), 0)
        self.assertLessEqual(len(calls), self.LIMIT)

    def test_container_count_is_bounded(self):
        volumes, rt = self.stored()
        visited = []
        cargo = N(IsProxyCargo=lambda: (visited.append(1), True)[1], GetItemCount=lambda: 0,
                  GetItem=lambda index: None)
        self.world.extra_cargos = [cargo] * 6000
        self.refused_without_touching_files(volumes, rt)
        self.assertLessEqual(len(visited), 4097)

    def test_a_stored_match_found_before_the_budget_is_exhausted_still_binds(self):
        target = self.item(1)
        volumes = [volume('site_a')]
        economy, ok = self.bind(self.prepare(volumes))
        self.assertTrue(ok)
        rt = self.restart()
        self.world.extra_objects = [N(name='tree')] * (self.LIMIT + 5000)
        plan = self.prepare(volumes, allow=False, rt=rt)
        self.assertIsNotNone(plan)
        self.assertEqual([target], [s.ItemHandle for s in plan.Registry.m_Entries])


if __name__ == '__main__':
    unittest.main()
