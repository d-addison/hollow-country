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
        self.assertEqual(4, rules.HCPageSize(catalog, 15))
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

        source = (SCRIPTS / 'HCXAISites.c').read_text()
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
            m_LocalityCursor=0, m_LocalityNextAttemptAt=0,
            m_LocalityUnits=units, m_LocalityWork=work,
            m_LocalityStatus='ready', m_Phase='run')
        for name in ('HCLocalityReserved', 'HCLocalityPageCount', 'HCTryLocality',
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
        director.m_States = A([N(LocalityId=selected[0])])
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
        director.m_States = A(N(LocalityId='occupied-' + str(i)) for i in range(4))
        before = len(director.m_States)
        director.HCTryLocality(now[0])
        self.assertEqual(before, len(director.m_States))
        self.assertEqual(selected[-1], rotation.NextId)
        # Failed durable intent prevents native admission, preserves quarantine.
        director.m_States.Clear()
        save_ok[0] = False
        director.HCTryLocality(now[0])
        self.assertEqual(0, len(director.m_States))
        self.assertTrue(director.m_LocalityRefused)
        self.assertEqual('refused', director.m_Phase)

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
                   STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2,
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
            'JsonFileLoader<HCXAILocalityRotation>.LoadData(HCWorldStore.Read(PATH), this.Data, error)',
            'synthetic_load(this)')
        def serialize(job):
            job.m_Text = json.dumps(vars(job.Data), default=lambda row: vars(row), sort_keys=True)
            return True
        env['synthetic_serialize'] = serialize
        def load(job):
            raw = json.loads(files['rotation'])
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
        self.assertFalse(writer.call('HCLoad', restored, catalog.WorldName))
        self.assertTrue(restored.Fault)


if __name__ == '__main__':
    unittest.main()
