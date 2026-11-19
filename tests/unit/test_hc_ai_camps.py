"""HC-16 / #143 synthetic authored-policy execution, never DayZ evidence.

Given finite founding reserves and one home, growth must pay exactly once;
raids retain a seven-day barrier across a synthetic restart. Native inventory,
provider movement/emotes, two-client presentation and persistence remain pending.
"""
from copy import deepcopy
from functools import wraps
import json
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'


def authored_camp_api():
    """Shared explicit synthetic DTO/stdlib port for holdout fixture updates."""
    source = (WORLD / 'HCAICampLifecycle.c').read_text()
    cfg = N(**{k: int(v) for k, v in re.findall(r'^    int (\w+) = (\d+);',
                source.split('class HCAICampLife')[0], re.M)})
    api = N()
    env = dict(HCAICampLifecycle=api, HCAILimits=N(SIZE_CEILING=12),
               Math=N(Min=min, Max=max), INT_MAX=2147483647,
               integer_div=lambda left, right: left // right)
    # Language ports: Enforce integer division and native DTO field defaults.
    # Older shared fixtures deliberately specify only the fields they exercise.
    translated = source.replace('(now - pool.ReserveAt) / policy.ReserveDaySeconds',
                                'integer_div(now - pool.ReserveAt, policy.ReserveDaySeconds)')
    translated = translated.replace('int.MAX', 'INT_MAX')
    translate(translated, 'HCAICampLifecycle', env)
    defaults = {}
    for typ in ('HCAICampLife', 'HCAICampResources'):
        fields = source.split('class ' + typ + '\n{', 1)[1].split('\n}', 1)[0]
        defaults[typ] = {name: json.loads(value) if value else
                        {'bool': False, 'int': 0, 'string': ''}[kind]
                        for kind, name, value in re.findall(
                            r'    (bool|int|string) (\w+)(?: = ([^;]+))?;', fields)}
    def dto_port(function, params):
        @wraps(function)
        def call(*args):
            for value, typ in zip(args, params):
                if value is not None:
                    for field, default in defaults.get(typ, {}).items():
                        if not hasattr(value, field): setattr(value, field, default)
            return function(*args)
        return call
    for name, value in tuple(env.items()):
        match = re.search(r'static \w+ ' + name + r'\(([^)]*)\)', source)
        if match:
            params = [p.strip().split()[0] for p in match[1].split(',')]
            setattr(api, name, dto_port(value, params))
    return cfg, api


def synthetic_camp(home='synthetic-house', **overrides):
    fields = dict(Home=home, Party='', Allocated=False, Refunded=False,
                  Population=0, Supply=0, Level=-1, LastStage=0,
                  LastUpkeep=0, ReoccupyAfter=0)
    fields.update(overrides)
    return N(**fields)


def synthetic_image(value):
    """Explicit deterministic JSON port, not the native serializer."""
    def fields(obj):
        return {k: v for k, v in vars(obj).items() if not callable(v)}
    return EStr(json.dumps(value, default=fields, sort_keys=True, indent=2))


def authored_holdouts(state, prior=None, save_ok=True):
    """Execute authored startup/transitions with synthetic storage/world ports."""
    from tests.unit.ai_limits_fixture import install
    class Map(dict):
        def Get(self, key): return self.get(key, '')
        def Set(self, key, value): self[key] = value
        def Contains(self, key): return key in self
    cfg, api = authored_camp_api()
    logs, writes, status = [], [], []
    clock = [1000000]
    module = N(m_State=state, m_Ready=False, m_Dirty=False, m_Caches=EArray(),
               m_Bodies=EArray(), m_CampRefusals=Map(), m_SaveJob=None,
               m_Operational=N(HCPublish=lambda *a: status.append(a)),
               SiteAvailable=lambda row: True, Cache=lambda i: object(),
               HCSyncLights=lambda: None)
    env = dict(HCAICampLifecycle=api, Print=logs.append, str=str,
               HCWorldClock=N(UTC=lambda: clock[0]),
               HCWorldModule=N(Get=lambda: N(Epoch=lambda: 7)),
               GetGame=lambda: N(IsServer=lambda: True),
               HCAIPartyIdentity=N(HCValid=lambda identity: identity is not None),
               HCArray=EArray, HCMap=Map, HCHoldoutState=lambda: state,
               HCEncounterCacheIO=N(Valid=lambda cache: cache.Phase == 2),
               HCHoldoutSaveJob=N, HCAICampDebug=N,
               HCSaveScheduler=N(HCRegister=lambda job: None),
               HCDebugSnapshot=N(HCRegister=lambda page: None),
               HCV2Gates=N(Qualified=lambda gate: False),
               HCV2Admission=N(Line=lambda *a: 'synthetic admission'),
               FileExist=lambda path: prior is not None,
               HCWorldStore=N(Read=lambda path: prior),
               HCWorldLimits=N(Token=lambda token: bool(token), Position=lambda pos: len(pos) == 3),
               serialize=lambda image: (synthetic_image(image), ''),
               HCStore=lambda name: N(Load=lambda fresh, collection: state))
    install(env)
    source = (WORLD/'HCHoldouts.c').read_text()
    source = source.replace('override ', '').replace('protected ', '').replace('this', 'self')
    source = source.replace('new HCEncounterCacheIO', 'new HCCache')
    env['HCCache'] = N
    source = source.replace('HCEncounterStore<HCHoldoutState>', 'HCStore')
    source = source.replace('new HCStore(', 'HCStore(')
    source = source.replace(') occupied++;', ') { occupied++; }')
    source = source.replace(') m_Bodies.Remove(releaseIndex);', ') { m_Bodies.Remove(releaseIndex); }')
    source = source.replace(') return;', ') { return; }').replace(') continue;', ') { continue; }')
    source = re.sub(r'array<ref \w+>', 'HCArray', source)
    source = source.replace('map<string, bool>', 'HCMap').replace('map<string, string>', 'HCMap')
    source = re.sub(r'([\w.]+(?:\(\))?(?:\.\w+(?:\(\))?)*)\.ToString\(\)', r'str(\1)', source)
    source = source.replace('if (!JsonFileLoader<HCHoldoutState>.MakeData(m_State, canonical, encodeError) || canonical != priorImage)',
                            'canonical, encodeError = serialize(m_State); if (!canonical || canonical != priorImage)')
    names = ('OnStart', 'HCRefuseState', 'Count', 'Occupied', 'HCCampHomes', 'OccupantKilled',
             'HCStepCamp', 'Raid', 'HCRaidCamp', 'HCPartyKilled', 'ReleaseOccupant',
             'HCOwnsOccupant', 'HCLogCamp')
    # The shared adapter supports forward loops; supply the reverse-loop syntax.
    source = re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)',
                    r'foreach (int \1 : reverse_indices(\2))', source)
    env['reverse_indices'] = lambda n: range(n, -1, -1)
    env['Get'] = lambda: module  # Static HCHoldouts.Get port for the super callback.
    translate(source, 'HCHoldouts', env, only=names)
    for name in names:
        if name in env:
            setattr(module, name, lambda *a, name=name: env[name](module, *a))
    module.OccupantKilled = env['OccupantKilled']
    def save():
        if module.m_Dirty:
            if not save_ok:
                module.m_Ready = False
                return False
            writes.append(deepcopy(state))
            module.m_Dirty = False
        return True
    module.SaveChanged = save
    module.PublishState = lambda row: None
    return module, logs, writes, status, clock


def synthetic_state():
    cfg, api = authored_camp_api()
    policy_env = {}
    translate((WORLD/'HCAICampLifecycle.c').read_text(), 'HCAICampPolicy', policy_env)
    cfg.HCValid = lambda: policy_env['HCValid'](cfg)
    camp = synthetic_camp()
    pool = N(Stock=cfg.FoundingStock, Population=cfg.FoundingPopulation,
             ReserveAt=1000000, Refunded=0)
    api.HCFound(camp, pool, EArray([camp]), 'holdout:synthetic-house', 3, 1000000, cfg)
    api.HCGrow(camp, 1000000, cfg)
    row = N(Camp=camp, Ledger=N(Id=camp.Home, PlaceId='synthetic-place',
            HouseClass='SyntheticHouse', HousePos=[1, 0, 1], State='OCCUPIED',
            Since=1000000, ReoccupyAfter=0, Occupants=3, Routine='FUNDED_CAMP'),
            Cache=N(Phase=2, EntityRef='synthetic-cache'), StockAttempts=0,
            StockDay=0, Contents=EArray(), Published=True)
    return N(Version=3, CampPolicy=cfg, Resources=pool, Rows=EArray([row]), TemplatePin='')


class CampReserveBehavior(unittest.TestCase):
    def test_terminal_refund_once_and_refounding_after_lockout(self):
        state = synthetic_state()
        module, logs, writes, status, clock = authored_holdouts(state)
        module.m_Ready = True
        camp, pool, cfg = state.Rows[0].Camp, state.Resources, state.CampPolicy
        state.Rows[0].StockAttempts = 3  # Lifetime native-item quota is never reset.
        before, unspent, population = pool.Stock, camp.Supply, camp.Population
        module.Raid(0)
        self.assertEqual(before + unspent, pool.Stock)
        self.assertEqual((True, 0, population), (camp.Refunded, camp.Supply, camp.Population))
        self.assertEqual(unspent, pool.Refunded)
        self.assertTrue(writes[-1].Rows[0].Camp.Refunded)
        self.assertEqual(before + unspent, writes[-1].Resources.Stock)
        # #176: a synthetic provider death inside an already-refunded lockout
        # debits one living body but cannot refund twice or reopen occupancy.
        row = state.Rows[0]
        refunded_deadline = camp.ReoccupyAfter
        clock[0] += 1
        body = N()
        module.m_Bodies.Insert(N(HoldoutId=row.Ledger.Id, Body=body))
        identity = N(HCGeneration=lambda: 7, HCPartyId=lambda: camp.Party,
                     HCCampId=lambda: 'camp:' + row.Ledger.Id,
                     HCHomeId=lambda: row.Ledger.PlaceId,
                     HCRouteId=lambda: 'stationary:' + row.Ledger.Id,
                     HCCargoId=lambda: 'cargo:' + row.Ledger.Id)
        module.HCPartyKilled(identity, body)
        module.OccupantKilled(body)  # Authored super path cannot debit twice.
        population -= 1
        self.assertEqual(population, camp.Population)
        self.assertEqual((before + unspent, unspent), (pool.Stock, pool.Refunded))
        self.assertEqual(('RAIDED', 0, refunded_deadline),
                         (row.Ledger.State, row.Ledger.Occupants, camp.ReoccupyAfter))
        self.assertFalse(module.HCStepCamp(0, clock[0]))
        self.assertTrue(camp.Refunded)
        self.assertTrue(writes[-1].Rows[0].Camp.Refunded)
        self.assertEqual(population, writes[-1].Rows[0].Camp.Population)
        restored = deepcopy(state)  # Explicit persisted-image restart.
        module, _, _, _, _ = authored_holdouts(restored)
        module.m_Ready = True
        module.Raid(0)
        self.assertEqual(before + unspent, restored.Resources.Stock)
        self.assertFalse(module.HCStepCamp(0, refunded_deadline - 1))
        self.assertTrue(module.HCStepCamp(0, refunded_deadline))
        self.assertEqual('OCCUPIED', restored.Rows[0].Ledger.State)
        self.assertFalse(restored.Rows[0].Camp.Refunded)
        self.assertEqual(population, restored.Rows[0].Camp.Population)
        self.assertEqual(unspent, restored.Resources.Refunded)
        self.assertEqual(3, restored.Rows[0].StockAttempts)

    def test_regeneration_persists_elapsed_days_and_consumes_time_at_cap(self):
        cfg, api = authored_camp_api()
        self.assertTrue(hasattr(api, 'HCReplenish'), 'missing persisted reserve replenishment')
        pool = N(Stock=0, Population=0, ReserveAt=1000, Refunded=0)
        homes = EArray([synthetic_camp(Population=6, Allocated=True)])
        self.assertFalse(api.HCReplenish(pool, homes, 1000+cfg.ReserveDaySeconds-1, cfg))
        self.assertTrue(api.HCReplenish(pool, homes, 1000+cfg.ReserveDaySeconds, cfg))
        self.assertEqual((cfg.ReserveRegenPerDay, cfg.ReservePopulationRegenPerDay),
                         (pool.Stock, pool.Population))
        pool = deepcopy(pool)
        self.assertFalse(api.HCReplenish(pool, homes, 1000+cfg.ReserveDaySeconds, cfg))
        self.assertFalse(api.HCReplenish(pool, homes, 999, cfg))
        now = 1000 + cfg.ReserveDaySeconds * 10000
        self.assertTrue(api.HCReplenish(pool, homes, now, cfg))
        self.assertEqual((cfg.ReserveCap, cfg.ReservePopulationCap-6), (pool.Stock, pool.Population))
        self.assertTrue(api.HCReplenish(pool, homes, now+cfg.ReserveDaySeconds, cfg))
        pool.Stock = 0
        pool.Population = 0
        self.assertFalse(api.HCReplenish(pool, homes, now+cfg.ReserveDaySeconds, cfg))
        self.assertEqual((0, 0), (pool.Stock, pool.Population), 'time at cap is not banked')

    def test_regeneration_uses_one_shared_watermark_and_persists_without_a_cache(self):
        state = synthetic_state()
        module, _, writes, _, _ = authored_holdouts(state)
        module.m_Ready = True
        module.Cache = lambda index: None
        before = state.Resources.Stock
        now = state.Resources.ReserveAt + state.CampPolicy.ReserveDaySeconds + 99
        self.assertFalse(module.HCStepCamp(0, now))  # No camp transition is possible.
        self.assertEqual(before + state.CampPolicy.ReserveRegenPerDay, state.Resources.Stock)
        self.assertEqual(now-99, writes[-1].Resources.ReserveAt)
        restored = deepcopy(state)
        module, _, writes, _, _ = authored_holdouts(restored)
        module.m_Ready = True
        module.Cache = lambda index: None
        self.assertFalse(module.HCStepCamp(0, now))
        self.assertEqual([], writes, 'restart at the same clock must not replay regeneration')

    def test_reserve_noop_does_not_allocate_or_scan_a_home_snapshot(self):
        state = synthetic_state()
        module, _, _, _, clock = authored_holdouts(state)
        module.m_Ready = True
        module.Cache = lambda index: None
        scans = []
        module.HCCampHomes = lambda: scans.append('homes') or EArray([state.Rows[0].Camp])
        self.assertFalse(module.HCStepCamp(0, clock[0]))
        self.assertEqual([], scans)
        self.assertFalse(module.HCStepCamp(0, clock[0] + state.CampPolicy.ReserveDaySeconds))
        self.assertEqual(['homes'], scans)

    def test_fresh_epoch_and_failed_regeneration_save_cannot_fund_a_camp(self):
        state = synthetic_state()
        row = state.Rows[0]
        row.Camp = synthetic_camp()
        row.Ledger.State, row.Ledger.Occupants = 'DORMANT', 0
        state.Resources.Stock = state.Resources.Population = state.Resources.ReserveAt = 0
        module, _, writes, _, clock = authored_holdouts(state)
        module.m_Ready = True
        self.assertFalse(module.HCStepCamp(0, clock[0]))
        self.assertEqual(0, state.Resources.Stock)
        self.assertEqual(clock[0], writes[0].Resources.ReserveAt)
        module, _, writes, _, _ = authored_holdouts(state, save_ok=False)
        module.m_Ready = True
        self.assertFalse(module.HCStepCamp(0, clock[0] + state.CampPolicy.ReserveDaySeconds * 2))
        self.assertFalse(module.m_Ready)
        self.assertFalse(row.Camp.Allocated)

    def test_policy_rejects_unbounded_or_disabled_recovery_and_accepts_defaults(self):
        state = synthetic_state()
        cfg = state.CampPolicy
        self.assertTrue(cfg.HCValid())
        for field, bad in (('ReserveCap', cfg.FoundingStock-1), ('ReserveCap', 257),
                           ('ReserveRegenPerDay', 0), ('ReserveRegenPerDay', cfg.ReserveCap+1),
                           ('ReserveDaySeconds', 0), ('ReserveDaySeconds', 604801),
                           ('ReservePopulationCap', cfg.FoundingPopulation-1),
                           ('ReservePopulationCap', 129), ('ReservePopulationRegenPerDay', 0)):
            with self.subTest(field=field, value=bad):
                old = getattr(cfg, field)
                setattr(cfg, field, bad)
                self.assertFalse(cfg.HCValid())
                setattr(cfg, field, old)

    def test_abandonment_and_last_death_release_unspent_supply_and_can_recover(self):
        for reason in ('supply', 'last-death'):
            state = synthetic_state()
            module, _, writes, _, clock = authored_holdouts(state)
            module.m_Ready = True
            row, cfg = state.Rows[0], state.CampPolicy
            if reason == 'supply':
                row.Camp.Supply = 0
                now = row.Camp.LastUpkeep + cfg.UpkeepSeconds
                self.assertTrue(module.HCStepCamp(0, now))
                self.assertEqual('ABANDONED', row.Ledger.State)
            else:
                row.Camp.Population = row.Ledger.Occupants = 1
                self.assertTrue(authored_camp_api()[1].HCDeath(row.Camp))
                now = clock[0]
                module.Raid(0)
            self.assertTrue(row.Camp.Refunded)
            self.assertEqual(0, row.Camp.Supply)
            self.assertTrue(writes)
            self.assertTrue(module.HCStepCamp(0, now+cfg.RaidLockoutSeconds))
            self.assertGreater(row.Camp.Population, 0)
            self.assertEqual('OCCUPIED', row.Ledger.State)

    def test_capped_refund_and_failed_durable_write_close_feature(self):
        state = synthetic_state()
        state.Resources.Stock = state.CampPolicy.ReserveCap - 1
        module, _, _, _, _ = authored_holdouts(state, save_ok=False)
        module.m_Ready = True
        module.Raid(0)
        self.assertEqual(state.CampPolicy.ReserveCap, state.Resources.Stock)
        self.assertEqual(1, state.Resources.Refunded)
        self.assertFalse(module.m_Ready)
        self.assertFalse(module.HCStepCamp(0, 2000000))

    def test_startup_refuses_legacy_and_corrupt_accepts_funded_and_refunded_images(self):
        for kind in ('legacy', 'schema2', 'funded', 'refunded', 'noncanonical', 'stock',
                     'stock-cap', 'population', 'life', 'version', 'clock-future',
                     'clock-missing', 'refund-mismatch', 'refund-counter', 'missing-field', 'unknown-field'):
            with self.subTest(kind=kind):
                state = synthetic_state()
                if kind == 'refunded':
                    module, _, _, _, _ = authored_holdouts(state)
                    module.m_Ready = True
                    module.Raid(0)
                if kind == 'stock': state.Resources.Stock = -1
                if kind == 'stock-cap': state.Resources.Stock = state.CampPolicy.ReserveCap+1
                if kind == 'population': state.Resources.Population = state.CampPolicy.FoundingPopulation + 1000
                if kind == 'life': state.Rows[0].Camp.Supply = -1
                if kind == 'version': state.Version = 99
                if kind == 'schema2': state.Version = 2
                if kind == 'clock-future': state.Resources.ReserveAt += 1
                if kind == 'clock-missing': state.Resources.ReserveAt = 0
                if kind == 'refund-mismatch': state.Rows[0].Camp.Refunded = True
                if kind == 'refund-counter': state.Resources.Refunded = -1
                prior = synthetic_image(state)
                if kind == 'legacy': prior = EStr('{"Version": 1, "Rows": []}')
                if kind == 'noncanonical': prior = EStr(prior + ' ')
                if kind == 'missing-field': prior = EStr(prior.replace('"Refunded": false,', ''))
                if kind == 'unknown-field': prior = EStr(prior[:-1] + ', "Unknown": 1}')
                module, logs, writes, status, _ = authored_holdouts(state, prior)
                module.OnStart(N(EnableDebugSnapshot=False))
                self.assertEqual(kind in ('funded', 'refunded'), module.m_Ready)
                if module.m_Ready:
                    receipt = next(line for line in logs if 'state=ready' in line)
                    self.assertIn('reserve=' + str(state.Resources.Stock), receipt)
                    self.assertIn('cap=' + str(state.CampPolicy.ReserveCap), receipt)
                    self.assertIn('refunded=' + str(state.Resources.Refunded), receipt)
                else:
                    self.assertEqual('refused', status[-1][0])
                    self.assertEqual([], writes)

    def test_party_killed_checks_identity_debits_one_and_removes_super_callback_binding(self):
        for invalid in ('generation', 'party', 'camp', 'home', 'route', 'cargo', None):
            with self.subTest(invalid=invalid):
                state = synthetic_state()
                module, _, writes, _, _ = authored_holdouts(state)
                module.m_Ready = True
                row = state.Rows[0]
                body = N()
                module.m_Bodies.Insert(N(HoldoutId=row.Ledger.Id, Body=body))
                values = dict(generation=7, party=row.Camp.Party, camp='camp:'+row.Ledger.Id,
                              home=row.Ledger.PlaceId, route='stationary:'+row.Ledger.Id,
                              cargo='cargo:'+row.Ledger.Id)
                if invalid: values[invalid] = 'foreign'
                identity = N(**{'HC'+key.title() if key == 'generation' else 'HC'+key.title()+'Id':
                                lambda value=value: value for key, value in values.items()})
                module.HCPartyKilled(identity, body)
                self.assertEqual(2 if invalid is None else 3, row.Camp.Population)
                self.assertEqual(0 if invalid is None else 1, len(module.m_Bodies))
                self.assertEqual(invalid is None, bool(writes))
                if invalid is None:
                    self.assertEqual('RAIDED', row.Ledger.State)
                    self.assertTrue(row.Camp.Refunded)
                    self.assertFalse(module.HCOwnsOccupant(row.Ledger.Id, body))
                    module.OccupantKilled(body)  # Actual authored PlayerBase super path.
                    self.assertEqual(2, row.Camp.Population)
                    # A second real actor may die before it was routine-bound.
                    module.HCPartyKilled(identity, N())
                    self.assertEqual(1, row.Camp.Population)
                    module.HCPartyKilled(identity, N())
                    self.assertEqual(0, row.Camp.Population)

    def test_routine_step_prioritizes_upkeep_over_growth_and_alert_expiry(self):
        state = synthetic_state()
        module, _, _, _, _ = authored_holdouts(state)
        module.m_Ready = True
        row, cfg = state.Rows[0], state.CampPolicy
        row.Ledger.State = 'ALERT'
        now = row.Camp.LastUpkeep + cfg.UpkeepSeconds
        supply = row.Camp.Supply
        self.assertTrue(module.HCStepCamp(0, now))
        self.assertEqual((0, supply-1, 'OCCUPIED'), (row.Camp.Level, row.Camp.Supply, row.Ledger.State))
        self.assertTrue(module.HCStepCamp(0, now))
        self.assertEqual(1, row.Camp.Level)
        self.assertFalse(module.HCStepCamp(0, now))


class AICampBehavior(unittest.TestCase):
    def test_finite_growth_single_home_raid_restart_and_observed_death(self):
        path = WORLD / 'HCAICampLifecycle.c'
        self.assertTrue(path.exists(), 'HC-16 missing resource-funded camp lifecycle')
        cfg, api = authored_camp_api()
        def camp(home):
            return N(Home=home, Party='', Allocated=False, Population=0, Supply=0,
                     Level=-1, LastStage=0, LastUpkeep=0, ReoccupyAfter=0)
        pool = N(Stock=cfg.FoundingStock, Population=cfg.FoundingPopulation)
        a, b = camp('synthetic-house'), camp('synthetic-house')
        rows = EArray([a, b])
        empty = N(Stock=0, Population=0)
        self.assertFalse(api.HCFound(a, empty, rows, 'holdout:synthetic-house', 3, 100, cfg))
        self.assertEqual((0, 0, -1), (a.Population, a.Supply, a.Level))
        self.assertTrue(api.HCFound(a, pool, rows, 'holdout:synthetic-house', 3, 100, cfg))
        remaining = (pool.Stock, pool.Population)
        self.assertFalse(api.HCFound(a, pool, rows, 'holdout:synthetic-house', 3, 100, cfg))
        self.assertFalse(api.HCFound(b, pool, rows, 'another-party', 3, 100, cfg))
        self.assertEqual(remaining, (pool.Stock, pool.Population))
        self.assertEqual((cfg.FoundingStock-cfg.CampAllocation, cfg.FoundingPopulation-3), remaining)
        for level in range(4):
            self.assertTrue(api.HCGrow(a, 100 + level*cfg.GrowthSeconds, cfg))
            self.assertEqual(level, a.Level)
        self.assertEqual(cfg.CampAllocation - sum(api.HCCost(i, cfg) for i in range(4)), a.Supply)
        self.assertFalse(api.HCGrow(a, 100+4*cfg.GrowthSeconds, cfg))
        self.assertEqual(remaining, (pool.Stock, pool.Population))
        api.HCRaid(a, 50000, cfg)
        restored, restored_pool = deepcopy(a), deepcopy(pool)  # Explicit synthetic DTO restart.
        self.assertFalse(api.HCGrow(restored, 50000+604799, cfg))
        self.assertTrue(api.HCGrow(restored, 50000+604800, cfg))
        self.assertEqual(remaining, (restored_pool.Stock, restored_pool.Population))
        self.assertEqual(3, restored.Population, 'a theft/raid does not invent deaths')
        self.assertTrue(api.HCDeath(restored))
        self.assertEqual(2, restored.Population)
        restored.Supply = 0
        self.assertFalse(api.HCGrow(restored, 50000+604800+cfg.GrowthSeconds, cfg))
        self.assertTrue(api.HCUpkeep(restored, restored.LastUpkeep+cfg.UpkeepSeconds, cfg))
        self.assertEqual(-1, restored.Level)
        self.assertTrue(api.HCDeath(restored))
        self.assertTrue(api.HCDeath(restored))
        self.assertFalse(api.HCDeath(restored))
        self.assertFalse(api.HCFound(restored, restored_pool, EArray([restored]),
                                     restored.Party, 3, 900000, cfg))
        # Integration: execute the actual funded transition through a synthetic
        # verified-write port. A failed durable barrier closes the feature.
        holdouts = (WORLD/'HCHoldouts.c').read_text()
        row = N(Camp=camp('synthetic-other'), Ledger=N(Id='synthetic-other', HousePos=(1,0,1),
                State='DORMANT', Occupants=0, Routine='', Since=100, ReoccupyAfter=0),
                Published=True)
        state = N(Resources=N(Stock=cfg.FoundingStock, Population=cfg.FoundingPopulation),
                  CampPolicy=cfg, Rows=EArray([row]))
        from tests.unit.ai_limits_fixture import install
        integration = dict(HCAICampLifecycle=api, Print=lambda s: None,
                           HCAICampLife=N, HCAICampPolicy=N)
        install(integration)
        # The shared translator provides language scaffolding only.
        holdouts = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', holdouts)
        holdouts = holdouts.replace('array<ref HCAICampLife> homes', 'HCAICampHomeArray homes')
        integration['str'] = str
        translate(holdouts, 'HCHoldouts', integration,
                  only=('HCStepCamp', 'HCCampHomes'))
        writes = []
        module = N(m_State=state, m_Dirty=False, m_Ready=True,
                   SiteAvailable=lambda r: True, Cache=lambda i: object(),
                   Occupied=lambda: 0, Count=lambda: len(state.Rows), SaveChanged=lambda: writes.append(deepcopy(state)) or True,
                   HCLogCamp=lambda *a: None)
        module.HCCampHomes = lambda: integration['HCCampHomes'](module)
        self.assertTrue(integration['HCStepCamp'](module, 0, 100))
        self.assertEqual(2, len(writes))  # Fresh clock epoch, then funded stage.
        self.assertFalse(writes[0].Rows[0].Camp.Allocated)
        self.assertEqual('OCCUPIED', row.Ledger.State)
        self.assertEqual(0, row.Camp.Level)
        # Explicit high-stage fixture: alert expiry must work even when no
        # further growth or daily upkeep is due.
        row.Camp.Level = 3
        row.Ledger.State = 'ALERT'
        self.assertFalse(integration['HCStepCamp'](module, 0, 160))
        self.assertEqual('ALERT', row.Ledger.State)
        self.assertTrue(integration['HCStepCamp'](module, 0, 100+cfg.GrowthSeconds))
        self.assertEqual('OCCUPIED', row.Ledger.State)
        row.Camp.Level = 0
        module.SaveChanged = lambda: False
        self.assertFalse(integration['HCStepCamp'](module, 0, 100+cfg.GrowthSeconds))
        self.assertFalse(module.m_Ready)
        # No timed text simulation is permitted to kill or create neighbours.
        for filename in ('HCCampVisitors.c', 'HCCampProbes.c'):
            text = (WORLD.parent/'Camps'/filename).read_text()
            self.assertNotIn('module.Tell(', text)
            self.assertNotIn('LoseNeighbours(', text)
            self.assertNotIn('camp.Neighbours =', text)
        routine = ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICampRoutine.c'
        self.assertIn('HCWorldMaterializer.HCIdentity', routine.read_text())
        self.assertNotIn('CreateObject', routine.read_text())

        # One actor request per dispatch on an already qualified synthetic route;
        # providers record requests only, never claim that an engine action ran.
        from tests.unit.test_map_layers import EStr
        from tests.unit.test_group_server import execute_member
        requests, identities, refusals = [], [], []
        clock, position, combat = [100], [(0, 0, 0)], [False]
        identity = N(HCCampId=lambda: EStr('camp:synthetic-house'))
        actors = EArray(N(IsAlive=lambda: True, GetIdentity=lambda: None,
                         GetPosition=lambda: position[0],
                         GetEmoteManager=lambda: N(IsEmotePlaying=lambda: False,
                                                   CanPlayEmote=lambda i: True),
                         Expansion_SetEmote=lambda *a: requests.append(('rest', a)),
                         OverrideTargetPosition=lambda *a: requests.append(('walk', a)))
                        for _ in range(3))
        group = N(Count=lambda: 3, GetMember=lambda i: actors[i], IsInCombat=lambda: combat[0])
        site = N(Transient=True, Completed=False, Qualified=True,
                 Patrol=N(m_Group=group), ProposalId='synthetic-lease',
                 PatrolPoints=EArray([(0, 0, 0), (3, 0, 0)]), HCCampMemberCursor=0,
                 HCCampRoleEpoch=0, HCCampNextRoleAt=0)
        view = N(Home=N(State='OCCUPIED', Id='synthetic-house', HousePos=(0, 0, 0)),
                 Level=3, Supply=9, Population=3)
        homes = N(HCRoutineView=lambda i: view, HCRoutinePolicy=lambda: cfg,
                  HCOwnsOccupant=lambda *a: True, BindOccupant=lambda *a: True)
        director = N(Phase=lambda: 'run', States=lambda: EArray([site]))
        routine_env = dict(GetGame=lambda: N(IsServer=lambda: True),
            HCXAISiteDirector=N(Active=lambda: director), HCHoldouts=N(Get=lambda: homes),
            HCPerfPlayers=N(HCGet=lambda: EArray([object()])),
            HCWorldMaterializer=N(HCIdentity=lambda lease: identities.append(lease) or identity),
            HCWorldClock=N(UTC=lambda: clock[0]), eAIBase=N(Cast=lambda a: a),
            EmoteConstants=N(ID_EMOTE_SITA=123),  # Explicitly synthetic enum value.
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x,y in zip(a,b))),
            HCRefuse=lambda state, reason: refusals.append(reason), Print=lambda s: None, str=str)
        routine_source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', routine.read_text())
        routine_source = routine_source.replace('array<ref HCXAISiteState> states', 'HCXAICampStates states')
        routine_source = routine_source.replace('array<Man> players', 'HCPlayers players')
        routine_source = routine_source.replace('eAIGroup group', 'HCGroup group').replace('eAIBase actor', 'HCActor actor')
        translate(routine_source, 'HCXAICampRoutine', routine_env, only=('Step', 'Close'))
        worker = N(m_Enabled=False, m_Closed=False, m_Cursor=0,
                   m_Units=N(HCReset=lambda n: None, HCTake=lambda n: True),
                   m_Work=N(HCReset=lambda n: None, HCContinue=lambda: True))
        step = lambda: routine_env['Step'](worker)
        step()
        self.assertEqual([], identities)
        worker.m_Enabled = True
        for _ in range(3): step()
        self.assertEqual(['rest'], [r[0] for r in requests])
        self.assertIn('ROUTINE_TARGET_CLEAR_UNAVAILABLE', refusals)
        step()  # Role cooldown: no new request.
        self.assertEqual(1, len(requests))
        view.Home.State = 'ALERT'
        step()
        self.assertEqual(1, len(requests), 'alert suspends routine roles')
        view.Home.State = 'OCCUPIED'
        clock[0] += cfg.RoleSeconds
        step()  # Relief boundary resets the cursor without issuing an action.
        self.assertEqual(1, len(requests))
        for _ in range(3): step()
        self.assertEqual(['rest', 'rest'], [r[0] for r in requests])
        combat[0] = True
        step()
        self.assertEqual(2, len(requests))
        combat[0] = False
        clock[0] += cfg.RoleSeconds
        step()  # Finish relief before checking the actor's observed position.
        position[0] = (cfg.RoutineRangeMeters+1, 0, 0)
        step()
        self.assertEqual('HOUSE_ROUTE_CONNECTION_UNPROVEN', refusals[-1])
        self.assertEqual(2, len(requests))
        routine_env['Close'](worker)
        count = len(identities)
        step()
        self.assertEqual(count, len(identities), 'off means no identity scan')
        observed = []
        callback_env = dict(HCXAICampRoutine=N(HCObserveKilled=observed.append),
                            super=N(EEKilled=lambda killer: None))
        killed = N(m_HCCampDeathSent=False)
        for _ in range(2):
            execute_member(routine.read_text().replace('this', 'self'), 'EEKilled', callback_env.copy(), killed, None)
        self.assertEqual([killed], observed, 'a real callback is debited once')


if __name__ == '__main__': unittest.main()
