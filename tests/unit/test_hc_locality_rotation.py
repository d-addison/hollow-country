"""HC-18 spec/plan/task: durable fair pages, sparse native site opportunities.

Synthetic DTOs, clocks, budgets, file/provider ports only. Execute authored
Enforce rules/handlers through the existing restricted adapter; no DayZ proof.
Runtime: PENDING DayZDiag + normal PBO/server + two-client observer checks.

Spec: HC-18 / #143..#147, consume HC-10 and publish locality v1 for HC-16.
Plan/tasks: inspect installed file/navmesh/provider lifecycle; RED 65th row;
separate bounded catalog/history from sparse native controllers; preserve pending
refusals and selection intent through restart; GREEN + affected source readers.
Actual RED command (2026-11-18), also the final focused GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_locality_rotation -v
RED: AssertionError: '' != '1..64 sites are required'; Ran 1 test; FAILED (failures=1).
Fairness follow-up RED: AssertionError: 'synthetic-locality-64' != 'synthetic-locality-0'
(full-page cursor advanced); same command, Ran 1 test; FAILED (failures=1).
GREEN: same command, Ran 1 test; OK. Synthetic ports never establish DayZ behavior.

Round 2 / HC-18 review spec-plan-tasks (2026-11-18):
Spec: P1-1 qualification reaches Create on the next visit; P1-2 operator drift
never removes a site; P1-3 all sites fitting the live cap stay armed, with fair
rotation beyond it. P2 cursor-only recovery/fallback and durable route outcomes;
P3 qualified save constants, bounded pending logs, 1 MB defaults reader.
Plan: reuse HCAILimits/HCAIBudget, HCUnitBudget/HCWorkBudget,
HCSaveJob/HCSaveScheduler/HCWorldStore, HCV2Admission and HCProfileDefaults.
Tasks: source fixes + mirror/provision/readiness/package/runbook implemented;
DayZDiag, normal signed PBO/server, restart and two-client observer/combat
acceptance, target-load profiling remain PENDING. No new engine API or distance.

Actual RED command A:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_locality_rotation.ReviewFixes tests.unit.test_expansion_ai_sites.ShippedDefaultsTests tests.unit.test_package.PackageBehavior.test_locality_catalog_is_in_portable_mission_handoff tests.unit.test_friend_bundle.FriendBundleTests.test_profile_copy_is_an_allowlist_of_config_never_runtime_state -v
Ran 19 tests; FAILED (failures=13, errors=1).
P1-1: AssertionError: True is not false : qualification must await Create
P1-2: AssertionError: '' != 'catalog_unknown_site'
P1-3: AssertionError: 21 != 4
P2 fallback: AssertionError: 'bind' != 'refused'
P2 routes: cached refusal not found in [] : Bind must retain cached refusal
P3 logs: AssertionError: 1 != 20
P3 constants: Regex matched: 'STEP_FAILED'
P3 reader: AssertionError: False is not true
Loadout bound: AssertionError: 1 != 0
Mirror: AssertionError: False is not true
Readiness: 'Print(m_Sites.HCLocalitySummary())' not found
Mission package: ValueError: mission handoff file outside allowlist: ai/localities.json

Actual RED command B:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_locality_rotation.ReviewFixes.test_extra_operator_site_alone_does_not_refuse_catalog tests.unit.test_hc_locality_rotation.ReviewFixes.test_leftover_cursor_intent_recovers_primary_backup_or_fresh tests.unit.test_friend_bundle.FriendBundleTests.test_locality_config_is_allowed_but_rotation_state_is_not -v
Ran 3 tests; FAILED (failures=6).
P1-2 extra-only: AssertionError: '' != 'catalog_unmapped_site'
P2 primary/backup/fresh cursor recovery: AssertionError: False is not true
Friend config inclusion: AssertionError: False is not true

P1-3 retained eligibility follow-up RED/GREEN command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_locality_rotation.ReviewFixes.test_sites_within_live_cap_keep_empty_patrols_eligible_after_opportunity -v
RED: AssertionError: [namespace(...)] != [] : sites fitting the cap must remain armed between rotations
Ran 1 test; FAILED (failures=1). After limiting expiry to catalogs beyond cap:
Ran 1 test; OK.

GREEN (all above cases, plus shipped 21-site first-cycle creation, fair smaller
cap rotation, real authored cache write/read/refusal reuse and retained patrols):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_locality_rotation tests.unit.test_expansion_ai_sites tests.unit.test_package tests.unit.test_friend_bundle tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers tests.unit.test_hygiene -v
Actual GREEN: Ran 235 tests in 19.470s; OK (skipped=1).
Related reader/lifecycle GREEN:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_encounters tests.unit.test_expansion_ai_adapter tests.unit.test_ai_ops_168 tests.unit.test_ai_limits tests.unit.test_v2_materializer -v
Ran 109 tests in 3.066s; OK.
python3 -B -m tools.validate.enforce_lint --no-native
=> enforce_lint: pass findings=126 new=0 stale=0 native=no
These are explicitly synthetic DTO/file/clock/provider ports, not DayZ proof.
"""
import copy
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, declarations
from tests.unit.test_expansion_ai_sites import api, dto
from tools.validate.enforce_source import Source

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'


class LocalityRotation(unittest.TestCase):
    def test_fair_pages_retain_failed_island_across_restart_and_sparse_caps(self):
        env = dict(A=A, Print=lambda line: None)
        declarations(env)
        env['vector'] = N(Distance=lambda a, b: math.dist(a, b))
        env['Math'] = N(AbsFloat=abs)
        env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), env)
        rules = api((SCRIPTS / 'HCXAISiteRules.c').read_text(), env)
        env['HCXAISiteRules'] = rules
        policy = dto(env, 'HCXAISitePolicy', json.loads(
            (ROOT / 'mission/hollow-country/ai/sites.json').read_text()))
        template = next(s for s in policy.Sites if s.Kind == 'patrol')
        # 65 explicitly synthetic geometries: last row represents an island.
        policy.Sites = A(copy.deepcopy(template) for _ in range(65))
        for index, site in enumerate(policy.Sites):
            site.Id = 'synthetic-site-' + str(index)
        self.assertEqual('', rules.PolicyProblem(policy),
                         '65th island must not be refused by the legacy 64-row cap')
        catalog = env['HCXAILocalityCatalog']()
        catalog.WorldName = policy.WorldName
        for index, site in enumerate(policy.Sites):
            locality = env['HCXAILocality']()
            locality.Id = 'synthetic-locality-' + str(index)
            locality.Island = index == 64
            locality.SiteIds = A([site.Id])
            catalog.Localities.Insert(locality)
        # Type syntax adaptation only; every catalog/selection decision is C.
        source = (SCRIPTS / 'HCXAISiteRules.c').read_text().replace(
            'array<string> ', 'HCXAIStrings ')
        rules = api(source, env)
        env['HCXAISiteRules'] = rules
        self.assertEqual('', rules.HCLocalityProblem(catalog, policy))
        self.assertEqual(15, rules.HCPageSize(catalog, 15))
        self.assertEqual(2, rules.HCPageSize(catalog, 2))
        self.assertEqual(1, rules.HCAttemptsPerTick(catalog))
        self.assertEqual(300, rules.HCRetrySeconds(catalog))
        self.assertEqual(30, rules.HCSelectionIntervalSeconds(catalog))
        self.assertEqual(3600, rules.HCOpportunitySeconds(catalog))
        rotation = env['HCXAILocalityRotation']()
        rotation.WorldName = catalog.WorldName
        for locality in catalog.Localities:
            row = env['HCXAILocalityCoverage']()
            row.LocalityId = locality.Id
            rotation.Rows.Insert(row)

        source = (SCRIPTS / 'HCXAISites.c').read_text().replace(
            'array<ref HCXAISite> ', 'HCXAISites ')
        authored = Authored(source, env)
        now, saved, ports, logs = [1000], [], [], []
        env['Print'] = logs.append
        env['ExpansionStatic'] = N(GetTimestamp=lambda utc: now[0])
        env['GetGame'] = lambda: N(GetTickTime=lambda: 0.)
        env['HCXAIQualification'] = N(EncountersEnabled=lambda: True)
        env['HCXAIEncounters'] = N(Active=lambda: None)
        save_ok = [True]
        def checkpoint(job):
            if save_ok[0]:
                saved.append(copy.deepcopy(job.Data))
            return save_ok[0]
        env['HCSaveScheduler'] = N(HCFlush=checkpoint, HCUnregister=lambda job: None)
        state_fields = dict(Transient=False, Patrol=None, Site=None, LocalityId='',
                            OpportunityAt=0, Bound=False, Qualified=False, Failed=False)
        env['HCXAISiteState'] = lambda: N(**state_fields)

        def budget(path, names, **fields):
            translated = Authored(path.read_text().replace(
                'return HCMayContinue(', 'return this.HCMayContinue('), env)
            obj = N(**fields)
            for name in names:
                setattr(obj, name, lambda *args, n=name: translated.call(n, obj, *args))
            return obj
        units = budget(ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCUnitBudget.c',
                       ('HCReset', 'HCTake', 'HCCharge'), m_Limit=0, m_Used=0, m_Items=0)
        work = budget(ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorkBudget.c',
                      ('HCReset', 'HCContinue', 'HCMayContinue'),
                      m_Deadline=0., m_Began=0., m_Limit=0, m_Used=0)
        director = N(m_Localities=catalog, m_LocalitySave=N(
            Data=rotation, Fault=False, HCChanged=lambda: None),
            m_States=A(), m_Policy=policy, m_LocalityRefused=False,
            m_Routes=N(Rows=A()),
            m_LocalityCursor=0, m_LocalityNextAttemptAt=0, m_LocalityNextPendingLogAt=0,
            m_LocalityUnits=units, m_LocalityWork=work,
            m_LocalityStatus='ready', m_Phase='run')
        for name in ('HCHasSite', 'HCAddLegacySites', 'HCLocalityPageCount', 'HCTryLocality',
                     'HCStepLocalities', 'HCLocalityFault', 'HCLocalitySummary'):
            setattr(director, name, lambda *args, n=name: authored.call(n, director, *args))
        def bind(state):
            # Synthetic native geometry port: island is unsupported, never swim.
            ports.append(('geometry', state.LocalityId))
            state.Bound = True
            state.Failed = state.LocalityId.endswith('-64')
        director.Bind = bind
        director.QualifyStep = lambda state: setattr(state, 'Qualified', True)
        def create(state):
            ports.append(('provider', state.LocalityId))
            if state.LocalityId.endswith('-63'):  # explicit provider refusal
                return
            state.Patrol = N(m_HCPendingMembers=0, m_Group=None,
                             Stop=lambda: None, Delete=lambda: None)
        director.Create = create
        director.SaveRoutes = lambda: True
        selected = []
        for index in range(65):
            director.HCTryLocality(now[0])
            self.assertEqual(index + 1, saved[-1].SelectionSerial)
            # SelectionSerial intent was committed before the native geometry port.
            self.assertEqual(index, len(selected))
            self.assertEqual(1, len(director.m_States))
            selected.append(director.m_States[0].LocalityId)
            director.m_LocalityNextAttemptAt = now[0] + 10000
            for _ in range(3):
                director.HCStepLocalities()
            now[0] += rules.HCOpportunitySeconds(catalog) + 1
            director.HCStepLocalities()
            self.assertEqual(0, len(director.m_States))
            if index == 31:
                # Explicit synthetic disk/restart: no native actors restored.
                director.m_LocalitySave.Data = copy.deepcopy(saved[-1])
        self.assertEqual(65, len(set(selected)))
        self.assertEqual(catalog.Localities[-1].Id, selected[-1])
        rotation = director.m_LocalitySave.Data
        island = rules.HCCoverage(rotation, selected[-1])
        self.assertTrue(island.Pending)
        self.assertEqual('route_geometry_or_provider_refused', island.Refusal)
        self.assertNotIn(('provider', selected[-1]), ports)
        self.assertTrue(all(row.LastSelected > 0 for row in rotation.Rows))
        self.assertTrue(rules.HCCoverage(rotation, selected[-2]).Pending)
        self.assertEqual(selected[0], rules.HCOldestPending(rotation))

        # Missing island access is explicitly pending, with no geometry call.
        saved_sites = catalog.Localities[-1].SiteIds
        catalog.Localities[-1].SiteIds = A()
        rotation.NextId = selected[-1]
        before_geometry = len(ports)
        director.HCTryLocality(now[0])
        self.assertEqual('island_access_route_unreviewed', island.Refusal)
        self.assertEqual(before_geometry, len(ports))
        last_attempt = island.LastSelected
        rotation.NextId = selected[-1]
        director.HCTryLocality(now[0])  # backoff cannot consume another attempt
        self.assertEqual(last_attempt, island.LastSelected)
        catalog.Localities[-1].SiteIds = saved_sites

        # Repeated opportunities cannot create a second controller locally.
        rotation.NextId = selected[0]
        island.RetryAt = 0
        director.m_States = A([N(LocalityId=selected[0], Site=policy.Sites[0], Transient=False)])
        director.HCTryLocality(now[0])
        self.assertEqual(1, len(director.m_States))
        # A live/deferred native group is never removed to free a page slot.
        live = env['HCXAISiteState']()
        live.LocalityId, live.Site = selected[0], policy.Sites[0]
        live.OpportunityAt = 0
        live.Patrol = N(m_Group=N(Count=lambda: 1), m_HCPendingMembers=0,
                        Stop=lambda: self.fail('live group stopped'),
                        Delete=lambda: self.fail('live group deleted'))
        director.m_States = A([live])
        director.m_LocalityNextAttemptAt = now[0] + 10000
        director.HCStepLocalities()
        self.assertEqual([live], director.m_States)
        self.assertFalse(rotation.Rows[0].Pending)
        self.assertEqual(selected[1], rules.HCOldestPending(rotation))
        live.Patrol.m_Group = None
        live.Patrol.m_HCPendingMembers = 2
        director.HCStepLocalities()
        self.assertEqual([live], director.m_States)
        # Disabled feature is a cheap no-op, even with missing dependencies.
        director.m_Localities = None
        director.HCStepLocalities()
        director.m_Localities = catalog

        # A full page must retain its next cursor; advancing while full can
        # starve a periodic island forever through selection/expiry aliasing.
        rotation.NextId = selected[-1]
        director.m_States = A(N(LocalityId='occupied-' + str(i)) for i in range(env['HCAILimits'].Get().MaxActiveSites))
        before = len(director.m_States)
        director.HCTryLocality(now[0])
        self.assertEqual(before, len(director.m_States))
        self.assertEqual(selected[-1], rotation.NextId)
        # Failed cursor save disables rotation; legacy admission remains available.
        director.m_States.Clear()
        save_ok[0] = False
        director.HCTryLocality(now[0])
        self.assertEqual(65, len(director.m_States))
        self.assertTrue(director.m_LocalityRefused)
        self.assertEqual('bind', director.m_Phase)
        self.assertIsNone(director.m_Localities)

        # Production catalog is stock-derived input, not a runtime census.
        shipped = json.loads((ROOT / 'mission/hollow-country/ai/localities.json').read_text())
        self.assertGreater(len(shipped['Localities']), 64)
        self.assertTrue(all(r['Source'] for r in shipped['Localities']))
        self.assertEqual({'skalisty', 'drakon', 'otmel', 'prison-island'},
                         {r['Id'] for r in shipped['Localities'] if r['Island']})
        mapped = [sid for r in shipped['Localities'] for sid in r['SiteIds']]
        real_policy = json.loads((ROOT / 'mission/hollow-country/ai/sites.json').read_text())
        self.assertCountEqual(mapped, [s['Id'] for s in real_policy['Sites']])

        # Execute the actual staged save with synthetic filesystem failure.
        parsed = Source(SCRIPTS / 'HCXAISites.c', source)
        store = next(c for c in parsed.classes if c.name == 'HCXAILocalitySave')
        store_source = source[store.offset:store.body_end + 1]
        store_source = store_source.replace('array<string> ', 'HCXAIStrings ')
        for field in ('Data', 'Fault', 'HCDirty'):
            store_source = re.sub(r'(?<![.\w])' + field + r'\b', 'this.' + field, store_source)
        files, fail_copy = {}, [False]
        def copy_file(src, dst):
            if fail_copy[0]:
                return False
            files[dst] = files[src]
            return True
        env.update(PATH='rotation', INTENT='intent', BACKUP='backup',
                   HCSaveJob=N(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2),
                   FileExist=lambda path: path in files, CopyFile=copy_file,
                   DeleteFile=lambda path: files.pop(path, None) is not None,
                   MakeDirectory=lambda path: True,
                   HCWorldStore=N(MAX_BYTES=1048576, Read=lambda path: files.get(path, ''),
                                  Write=lambda path, text: files.setdefault(path, text) == text))
        # Out-parameter serialization is a restricted test port only.
        store_source = store_source.replace(
            'JsonFileLoader<HCXAILocalityRotation>.MakeData(Data, m_Text, error)',
            'synthetic_serialize(this)')
        store_source = store_source.replace(
            'JsonFileLoader<HCXAILocalityRotation>.MakeData(this.Data, m_Text, error)',
            'synthetic_serialize(this)')
        store_source = store_source.replace(
            'JsonFileLoader<HCXAILocalityRotation>.LoadData(HCWorldStore.Read(path), this.Data, error)',
            'synthetic_load(this, path)')
        def serialize(job):
            job.m_Text = json.dumps(vars(job.Data), default=lambda row: vars(row), sort_keys=True)
            return True
        env['synthetic_serialize'] = serialize
        def load(job, path):
            raw = json.loads(files[path])
            job.Data = N(**raw)
            job.Data.Rows = A(N(**row) for row in raw['Rows'])
            return True
        env['synthetic_load'] = load
        writer = Authored(store_source, env)
        job = N(Data=rotation, Fault=False, m_Stage=0, m_Revision=1,
                m_SnapshotRevision=0, m_Text='', HCDirty=True)
        for _ in range(3):
            self.assertEqual(1, writer.call('HCStep', job))
        self.assertIn('intent', files)
        self.assertEqual(0, writer.call('HCStep', job))
        self.assertNotIn('intent', files)
        restored = N(Data=None, Fault=False)
        restored.HCRestore = lambda path, world: writer.call('HCRestore', restored, path, world)
        self.assertTrue(writer.call('HCLoad', restored, catalog.WorldName))
        self.assertEqual(rotation.NextId, restored.Data.NextId)
        self.assertEqual(island.Refusal, restored.Data.Rows[-1].Refusal)
        self.assertTrue(restored.Data.Rows[-1].Pending)
        writer.call('HCChanged', job)
        self.assertEqual(1, writer.call('HCStep', job))
        self.assertEqual(1, writer.call('HCStep', job))
        fail_copy[0] = True
        self.assertEqual(2, writer.call('HCStep', job))
        self.assertTrue(job.Fault)
        self.assertIn('intent', files)
        restored = N(Data=None, Fault=False)
        restored.HCRestore = lambda path, world: writer.call('HCRestore', restored, path, world)
        self.assertTrue(writer.call('HCLoad', restored, catalog.WorldName))
        self.assertFalse(restored.Fault)
        self.assertNotIn('intent', files)


class ReviewFixes(unittest.TestCase):
    """HC-18 round 2: synthetic ports execute authored handlers, no engine proof."""
    def setUp(self):
        self.logs, self.saves = [], []
        self.env = dict(A=A, Print=self.logs.append)
        declarations(self.env)
        self.env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), self.env)
        self.rules = api((SCRIPTS / 'HCXAISiteRules.c').read_text().replace(
            'array<string> ', 'HCXAIStrings '), self.env)
        self.env['HCXAISiteRules'] = self.rules
        self.catalog = self.env['HCXAILocalityCatalog']()
        self.catalog.WorldName = 'chernarusplus'
        self.policy = N(WorldName='chernarusplus', Sites=A())
        self.rotation = self.env['HCXAILocalityRotation']()
        self.rotation.WorldName = 'chernarusplus'
        self.now = 1000
        self.env.update(ExpansionStatic=N(GetTimestamp=lambda utc: self.now),
                        GetGame=lambda: N(GetTickTime=lambda: 0.),
                        HCXAIQualification=N(EncountersEnabled=lambda: True),
                        HCXAIEncounters=N(Active=lambda: None),
                        HCSaveScheduler=N(HCFlush=lambda job: True, HCUnregister=lambda job: None))
        self.env['HCXAISiteState'] = lambda: N(Transient=False, Patrol=None, Site=None,
            LocalityId='', OpportunityAt=0, Bound=False, Qualified=False, Failed=False, Cached=False)
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace(
            'array<ref HCXAISite> ', 'HCXAISites ')
        source = re.sub(r'([\w.]+\.Count\(\))\.ToString\(\)', r'str(\1)', source)
        self.authored = Authored(source, self.env)
        self.director = N(m_Localities=self.catalog, m_LocalitySave=N(Data=self.rotation,
            Fault=False, HCChanged=lambda: None), m_States=A(), m_Policy=self.policy,
            m_LocalityRefused=False, m_LocalityCursor=0, m_LocalityNextAttemptAt=999999,
            m_LocalityNextPendingLogAt=0, m_LocalityStatus='ready', m_Phase='run',
            m_Routes=N(Rows=A()),
            m_LocalityUnits=N(HCReset=lambda n: None, HCTake=lambda n: True, HCCharge=lambda n: None),
            m_LocalityWork=N(HCReset=lambda n: None, HCContinue=lambda: True))
        for name in ('HCStepLocalities', 'HCTryLocality', 'HCLocalityFault',
                     'HCLocalityPageCount', 'HCLocalitySummary', 'HCAddLegacySites',
                     'HCHasSite', 'HCReconcileLocalitySites'):
            setattr(self.director, name, lambda *args, n=name: self.authored.call(n, self.director, *args))
        self.director.Bind = lambda state: setattr(state, 'Bound', True)
        self.director.QualifyStep = lambda state: setattr(state, 'Qualified', True)
        self.director.Create = lambda state: setattr(state, 'Patrol', N(m_HCPendingMembers=0,
            m_Group=None, Stop=lambda: None, Delete=lambda: None))
        self.director.SaveRoutes = lambda: self.saves.append(copy.deepcopy(self.director.m_Routes))

    def add_locality(self, name, site_ids):
        row = self.env['HCXAILocality']()
        row.Id, row.SiteIds = name, A(site_ids)
        self.catalog.Localities.Insert(row)
        coverage = self.env['HCXAILocalityCoverage']()
        coverage.LocalityId = name
        self.rotation.Rows.Insert(coverage)
        for sid in site_ids:
            if not any(s.Id == sid for s in self.policy.Sites):
                self.policy.Sites.Insert(N(Id=sid, Checkpoint=False))
        return row

    def test_qualification_survives_until_next_visit_creates_patrol(self):
        self.add_locality('synthetic-town', ['synthetic-site'])
        self.director.HCTryLocality(self.now)
        self.director.HCStepLocalities()  # bind
        self.director.HCStepLocalities()  # qualify
        self.assertTrue(self.director.m_States[0].Qualified)
        self.assertFalse(self.director.m_States[0].Failed, 'qualification must await Create')
        self.director.HCStepLocalities()
        self.assertIsNotNone(self.director.m_States[0].Patrol)

    def test_catalog_drift_keeps_removed_and_extra_operator_sites_eligible(self):
        for drift in ('removed', 'extra'):
            with self.subTest(drift=drift):
                self.setUp()
                self.add_locality('synthetic-town', ['synthetic-kept', 'synthetic-removed'])
                self.policy.Sites = A([self.policy.Sites[0]])
                if drift == 'extra':
                    self.policy.Sites.Insert(N(Id='synthetic-extra', Checkpoint=False))
                self.assertEqual('', self.rules.HCLocalityProblem(self.catalog, self.policy))
                self.director.HCReconcileLocalitySites()
                mapped = [sid for row in self.catalog.Localities for sid in row.SiteIds]
                self.assertCountEqual([s.Id for s in self.policy.Sites], mapped)
                self.assertEqual(1, sum('catalog_unknown_site' in line for line in self.logs))
                self.assertFalse(self.director.m_LocalityRefused)
                for row in self.catalog.Localities:
                    if not self.rules.HCCoverage(self.rotation, row.Id):
                        coverage = self.env['HCXAILocalityCoverage']()
                        coverage.LocalityId = row.Id
                        self.rotation.Rows.Insert(coverage)
                    self.director.HCTryLocality(self.now)
                self.assertCountEqual([s.Id for s in self.policy.Sites],
                                      [s.Site.Id for s in self.director.m_States])

    def test_extra_operator_site_alone_does_not_refuse_catalog(self):
        self.add_locality('synthetic-town', ['synthetic-kept'])
        self.policy.Sites.Insert(N(Id='synthetic-extra', Checkpoint=False))
        self.assertEqual('', self.rules.HCLocalityProblem(self.catalog, self.policy))

    def test_leftover_cursor_intent_recovers_primary_backup_or_fresh(self):
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace(
            'array<ref HCXAISite> ', 'HCXAISites ')
        parsed = Source(SCRIPTS / 'HCXAISites.c', source)
        store = next(c for c in parsed.classes if c.name == 'HCXAILocalitySave')
        code = source[store.offset:store.body_end + 1].replace('array<string> ', 'HCXAIStrings ')
        for field in ('Data', 'Fault'):
            code = re.sub(r'(?<![.\w])' + field + r'\b', 'this.' + field, code)
        code = re.sub(r'JsonFileLoader<HCXAILocalityRotation>.LoadData\(HCWorldStore.Read\((PATH|path)\), this.Data, error\)',
                      r'synthetic_load(this, \1)', code)
        files = {}
        def load(job, path):
            if files.get(path) != 'valid':
                return False
            job.Data = copy.deepcopy(self.rotation)
            return True
        self.env.update(PATH='primary', BACKUP='backup', INTENT='intent',
            FileExist=lambda path: path in files,
            DeleteFile=lambda path: files.pop(path, None) is not None,
            synthetic_load=load)
        writer = Authored(code, self.env)
        for primary, backup in (('valid', 'valid'), ('broken', 'valid'), (None, 'valid'), (None, None)):
            with self.subTest(primary=primary, backup=backup):
                files.clear()
                files['intent'] = 'interrupted selection'
                if primary: files['primary'] = primary
                if backup: files['backup'] = backup
                job = N(Data=None, Fault=False)
                job.HCRestore = lambda path, world: writer.call('HCRestore', job, path, world)
                self.assertTrue(writer.call('HCLoad', job, 'chernarusplus'))
                self.assertFalse(job.Fault)
                self.assertNotIn('intent', files)
                self.assertEqual('chernarusplus', job.Data.WorldName)

    def test_first_page_cycle_covers_all_21_sites_when_live_cap_fits(self):
        self.env['HCAILimits'].Get().MaxActiveSites = 21
        # Explicit synthetic multistore locality + site-less catalog rows.
        for i in range(7):
            self.add_locality('synthetic-town-' + str(i),
                              ['synthetic-site-' + str(i * 3 + j) for j in range(3)])
            self.add_locality('synthetic-empty-' + str(i), [])
        self.assertEqual(21, self.rules.HCPageSize(self.catalog, 21))
        self.catalog.PageSize = 4  # old profile must not shrink live-cap coverage
        self.assertEqual(21, self.rules.HCPageSize(self.catalog, 21))
        for _ in self.catalog.Localities:
            self.director.HCTryLocality(self.now)
        self.assertEqual(21, len(self.director.m_States))
        self.assertCountEqual([s.Id for s in self.policy.Sites],
                              [s.Site.Id for s in self.director.m_States])

    def test_shipped_21_sites_are_armed_in_first_cycle_at_cap_21(self):
        self.env['HCAILimits'].Get().MaxActiveSites = 21
        shipped = json.loads((ROOT / 'mission/hollow-country/ai/localities.json').read_text())
        for row in shipped['Localities']:
            self.add_locality(row['Id'], row['SiteIds'])
        expected = [row['Id'] for row in json.loads(
            (ROOT / 'mission/hollow-country/ai/sites.json').read_text())['Sites']]
        self.assertEqual(21, len(expected))
        for _ in self.catalog.Localities:
            self.director.HCTryLocality(self.now)
        for _ in range(3):
            self.director.HCStepLocalities()
        self.assertCountEqual(expected, [state.Site.Id for state in self.director.m_States if state.Patrol])

    def test_clock_and_save_fault_handlers_fall_back_without_refusing_director(self):
        for fault in ('clock', 'save'):
            with self.subTest(fault=fault):
                self.setUp()
                self.add_locality('synthetic-town', ['synthetic-site'])
                if fault == 'clock':
                    self.now = 0
                else:
                    self.director.m_LocalitySave.Fault = True
                self.director.HCStepLocalities()
                self.assertEqual('bind', self.director.m_Phase)
                self.assertEqual(1, len(self.director.m_States))
                self.assertIsNone(self.director.m_Localities)

    def test_legacy_fallback_does_not_rebind_or_recreate_retained_patrol(self):
        self.add_locality('synthetic-town', ['synthetic-0', 'synthetic-1'])
        self.director.HCTryLocality(self.now)
        kept = self.director.m_States[0]
        kept.Bound = kept.Qualified = True
        self.director.Create(kept)
        patrol = kept.Patrol
        self.director.HCLocalityFault()
        bound, created = [], []
        self.director.Bind = lambda state: bound.append(state.Site.Id)
        self.director.Create = lambda state: created.append(state.Site.Id)
        self.env['HCXAISiteDirector'] = N(WORK_PER_TICK=4)
        self.authored.call('StepBind', self.director)
        self.assertEqual(['synthetic-1'], bound)
        for state in self.director.m_States:
            state.Qualified = True
        self.director.m_Cursor = 0
        self.authored.call('StepCreate', self.director)
        self.assertEqual(['synthetic-1'], created)
        self.assertIs(patrol, kept.Patrol)

    def test_persisted_route_refusal_reloads_and_avoids_native_qualification(self):
        self.add_locality('synthetic-town', ['synthetic-site'])
        self.director.m_Routes.Rows.Insert(N(Key='synthetic-key', SiteId='synthetic-site',
                                             Qualified=False, Reason='synthetic disconnected route'))
        files = {}
        def save(path, data, error):
            files[path] = copy.deepcopy(data)
            return True
        def load(data, routes, error):
            vars(routes).update(vars(copy.deepcopy(data)))
            return True
        self.env.update(HCXAISiteDirector=N(ROUTES='routes'), MakeDirectory=lambda path: True,
            FileExist=lambda path: path in files,
            HCWorldStore=N(Read=lambda path: files[path]),
            SyntheticRouteJSON=N(SaveFile=save, LoadData=load))
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace(
            'JsonFileLoader<HCXAIRouteCache>', 'SyntheticRouteJSON').replace(
            'HCXAIRouteCache routes;', 'HCXAIRouteCache routes = new HCXAIRouteCache();')
        authored = Authored(source, self.env)
        self.assertTrue(authored.call('SaveRoutes', self.director))
        restored = authored.call('LoadRoutes', None)
        self.assertEqual('synthetic disconnected route', restored.Rows[0].Reason)
        # GetAIWorld is fetched but no path/sample call may follow a cached refusal.
        self.env['GetGame'] = lambda: N(GetWorld=lambda: N(GetAIWorld=lambda: N()))
        self.director.RouteRow = lambda key: restored.Rows[0]
        state = N(Key='synthetic-key', Site=N(Id='synthetic-site'), Failed=False)
        source = source.replace('AIWorld world', 'HCXAITestWorld world').replace('TVectorArray', 'HCXAITestArray')
        source = re.sub(r'([\w.]+\.Count\(\))\.ToString\(\)', r'str(\1)', source)
        authored = Authored(source, self.env)
        authored.call('QualifyStep', self.director, state)
        self.assertTrue(state.Failed)
        self.assertIn('cached refusal:', state.Reason)

    def test_sites_within_live_cap_keep_empty_patrols_eligible_after_opportunity(self):
        self.add_locality('synthetic-town', ['synthetic-site'])
        self.director.HCTryLocality(self.now)
        for _ in range(3):
            self.director.HCStepLocalities()
        kept = self.director.m_States[0]
        self.now += 3601
        self.director.HCStepLocalities()
        self.assertEqual([kept], self.director.m_States,
                         'sites fitting the cap must remain armed between rotations')

    def test_smaller_cap_rotates_fairly_including_sites_in_same_locality(self):
        self.env['HCAILimits'].Get().MaxActiveSites = 2
        self.add_locality('synthetic-a', ['synthetic-0', 'synthetic-1', 'synthetic-2'])
        self.add_locality('synthetic-b', ['synthetic-3', 'synthetic-4'])
        selected = set()
        for _ in range(12):
            self.director.HCTryLocality(self.now)
            self.assertLessEqual(len(self.director.m_States), 2)
            selected.update(s.Site.Id for s in self.director.m_States)
            self.director.m_States.Clear()  # explicit empty-controller expiry port
            self.now += 3601
        self.assertEqual(5, len(selected))

    def test_clock_or_save_fault_keeps_existing_patrol_and_enters_legacy_binding(self):
        self.add_locality('synthetic-town', ['synthetic-0', 'synthetic-1'])
        self.director.HCTryLocality(self.now)
        kept = self.director.m_States[0]
        self.director.Create(kept)
        patrol = kept.Patrol
        self.director.HCLocalityFault()
        self.assertEqual('bind', self.director.m_Phase)
        self.assertIsNone(self.director.m_Localities)
        self.assertIs(patrol, kept.Patrol)
        self.assertTrue(all(s.LocalityId == '' for s in self.director.m_States))
        self.assertCountEqual(['synthetic-0', 'synthetic-1'], [s.Site.Id for s in self.director.m_States])

    def test_route_outcome_saved_and_cached_refusal_survives_binding(self):
        self.add_locality('synthetic-town', ['synthetic-site'])
        cached = N(SiteId='synthetic-site', Qualified=False)
        self.director.m_Routes.Rows.Insert(cached)
        self.director.HCTryLocality(self.now)
        self.director.HCStepLocalities()
        self.assertIn(cached, self.director.m_Routes.Rows, 'Bind must retain cached refusal')
        self.director.HCStepLocalities()
        self.assertEqual(1, len(self.saves), 'terminal qualification must save route cache')

    def test_site_less_pending_log_is_rate_limited(self):
        self.add_locality('synthetic-empty', [])
        self.catalog.RetrySeconds = 1
        for i in range(20):
            self.director.HCTryLocality(self.now + i)
        pending = [line for line in self.logs if 'state=pending' in line]
        self.assertEqual(1, len(pending))

    def test_save_step_results_are_class_qualified(self):
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace(
            'array<ref HCXAISite> ', 'HCXAISites ')
        store = source[source.index('class HCXAILocalitySave'):source.index('class HCXAISiteDirector')]
        self.assertNotRegex(store, r'(?<![.\w])STEP_(?:FAILED|MORE|DONE)')


if __name__ == '__main__':
    unittest.main()
