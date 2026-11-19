"""HC-19 upgrade regression: explicit SYNTHETIC pre-HC-19 disk image.

DTO keys are from 25a7dc2: HCSceneChains.c, HCEventData.c and
HCEventRuntimeData.c. No profile or DayZ result is embedded here. The
original initializer-preserving ports were corrected by #177 after boot 057
observed missing scalar zero-fill. Both allocation shapes now zero scalars;
authored Open restores the absent legacy Stories section explicitly. This is
still not a reproduction of boot 050's unknown DTO.
Spec/plan/task: HC-19 / #147; task.md in the dispatched writer inputs.

Actual TDD receipt, 2026-11-18:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_scene_upgrade -v
  RED: unexpectedly None : missing Stories must retain explicitly constructed defaults
       False is not true : refusal must identify reason=state_invalid
       (also clock/tmp/backup_only/read); Ran 4 tests; FAILED (failures=7).
  GREEN: same command; Ran 4 tests; OK (before adding lifecycle coverage).
  Final GREEN: same command; Ran 5 tests; OK.
  Focused suite GREEN: 130 tests; exact command:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_scene_upgrade tests.unit.test_hc_story_schedule tests.unit.test_hc_story_module tests.unit.test_v2_scenes tests.unit.test_hc_unit_budget tests.unit.test_v2_leads tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers tests.unit.test_hygiene tests.unit.test_enforce_formula_complexity -v
  Lint: python3 -B -m tools.validate.enforce_lint --no-native
        pass findings=124 new=0 stale=0 native=no.
  The fixture was also accepted by the actual 25a7dc2 StateValid body loaded
  read-only with git show and executed via the same restricted translator.
  Native loader behavior and boot 050's exact rejection remain unconfirmed.
"""
import copy
import functools
import json
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import environment, translate
from tests.unit.test_group_server import EArray, body
from tests.unit.test_hc_story_schedule import SCENES, bind, dto

CHAINS = SCENES / 'HCSceneChains.c'
PATH = '$profile:HollowCountry/scene-chains.json'
NOW = 217216081


def plain(value):
    return json.loads(json.dumps(value, default=vars))


class LegacySceneUpgrade(unittest.TestCase):
    def setUp(self):
        self.env = environment()
        self.logs = []
        self.env.update(Print=self.logs.append,
                        HCV2Admission=N(Admitted=lambda preference: preference))
        from tests.unit.json_loader_port import json_fields_port
        self.env['HCJsonFields'] = json_fields_port()
        reviewed = (SCENES.parent / 'Events/HCEventReviewedSites.c').read_text()
        self.env['HCEventReviewedSites'] = N()
        for name in ('Build', 'Curated', 'SceneMission'):
            setattr(self.env['HCEventReviewedSites'], name,
                    translate(reviewed, name, self.env, 'HCEventReviewedSites'))
        for kind in ('HCSceneCatalog', 'HCSceneChainDefinition', 'HCSceneStageDefinition',
                     'HCSceneChain', 'HCSceneChainState'):
            factory = functools.partial(dto, kind, self.env, CHAINS)
            self.env[kind] = factory
            self.env['HCEvent' + kind[2:]] = factory
        self.env['HCStoryProgress'] = lambda: dto('HCStoryProgress', self.env)
        self.env['HCEventStoryProgress'] = self.env['HCStoryProgress']
        # Explicit synthetic kit/class/geometry port; no placement claim.
        self.env['HCEventSceneKits'] = N(Reviewed=lambda site: site is not None,
                                       Find=lambda kind: kind)
        self.policy = N()
        self.chains = N()
        self.env['HCEventStoryPolicy'] = self.policy
        self.env['HCEventSceneChains'] = self.chains
        bind('HCStoryPolicy', self.policy, self.env,
             names=['HCConfigValid', 'HCUnmigrated', 'HCValid', 'HCIdentity', 'HCMigrate'])
        bind('HCSceneChains', self.chains, self.env,
             names=['Defaults', 'Plan', 'Site', 'CatalogValid', 'StateValid',
                    'ResumeAfterGap'], path=CHAINS)
        self.fixture = self.legacy_fixture()

    def legacy_fixture(self):
        """Three pinned plans; active, completed and cancelled legacy rows.

        Only pre-HC-19 serialized keys, explicitly listed even at default values.
        Plan/objective schema is unchanged since 25a7dc2; use authored builders.
        All lifecycle values below are synthetic, not boot 049's contents.
        """
        plans = self.chains.Defaults().Chains[:3]
        rows = []
        for index, plan in enumerate(plans):
            stage = (1, 2, 0)[index]
            due = NOW - 1000
            records = []
            if index < 2:
                for number in range(stage + 1):
                    definition = self.env['HCEventRuntimePolicy'].Definition(plan.Stages[number].Objective)
                    definition.ObjectiveTag = 'scene-duration'
                    completed = index == 1 or number < stage
                    records.append(dict(Id=number + 1, Revision=4 if completed else 2,
                        Status=4 if completed else 1, Session=plan.Id, Definition=plain(definition),
                        Expires=due + 43200, Progress=int(completed), LastObservation=int(completed),
                        Participants=[]))
            rows.append(dict(Id=plan.Id, Stage=stage, DueAt=due, ExpiresAt=due + 43200,
                BeganAt=due if records else 0, EventId=len(records),
                Cancelled=index == 2, Complete=index == 1,
                Director=dict(Version=1, WorldName='chernarusplus', Session=plan.Id,
                    LastNow=NOW - 5, NextId=len(records) + 1, PrunedThrough=0,
                    SessionGeneration=0, Sessions=[plan.Id], Records=records)))
        return dict(Version=1, WorldName='chernarusplus', Revision=617, LastNow=NOW,
                    Catalog=dict(Version=1, Chains=plain(plans)), Chains=rows)

    def decode(self, raw, mode='initializer', target=None):
        """Synthetic JSON/DTO port, never an implementation of scene policy.

        Scalars zero-fill even with caller-provided output. Other modes still
        exercise null/absent managed-object allocation uncertainty.
        """
        nested = {
            ('HCSceneChainState', 'Catalog'): 'HCSceneCatalog',
            ('HCSceneChainState', 'Chains'): 'HCSceneChain',
            ('HCSceneChainState', 'Stories'): 'HCStoryProgress',
            ('HCSceneCatalog', 'Chains'): 'HCSceneChainDefinition',
            ('HCSceneChainDefinition', 'Stages'): 'HCSceneStageDefinition',
            ('HCSceneStageDefinition', 'Objective'): 'HCEventMission',
            ('HCSceneChain', 'Director'): 'HCEventState',
            ('HCEventState', 'Records'): 'HCEventRecord',
            ('HCEventRecord', 'Definition'): 'HCEventDefinition',
        }

        def hydrate(kind, data, value=None):
            from tests.unit.json_loader_port import zero_scalars
            value = zero_scalars(value or self.env[kind]())
            for key, entry in data.items():
                child = nested.get((kind, key))
                if isinstance(entry, list):
                    entry = EArray(hydrate(child, row) if child else row for row in entry)
                elif isinstance(entry, dict) and child:
                    entry = hydrate(child, entry)
                setattr(value, key, entry)
            return value

        result = hydrate('HCSceneChainState', raw, target)
        if 'Stories' not in raw and target is None:
            if mode == 'null':
                result.Stories = None
            elif mode == 'default-loss':
                result.Stories = N(Version=0, NextSequence=0, LegacyThrough=0,
                                  TerminalThrough=0, NextArrival=0,
                                  LegacyIds=None, TerminalExceptions=None)
        return result

    def store(self, image, mode='initializer', tmp=False, backup_only=False, read_ok=True):
        disk = {PATH: image, PATH + '.bak': image}
        if tmp:
            disk[PATH + '.tmp'] = 'synthetic unfinished intent'
        if backup_only:
            del disk[PATH]
        self.disk = disk
        self.writes = []
        self.env.update(FileExist=lambda path: path == '$profile:HollowCountry' or path in disk,
                        MakeDirectory=lambda path: True)
        owner = N(m_Path=PATH, m_Fault=False, m_Image='', m_Revision=0)

        def read_decode(path, target):
            text = disk[path]
            if not read_ok:
                return False, text, None
            try:
                return True, text, self.decode(json.loads(text), mode, target)
            except (ValueError, TypeError):
                return False, text, None

        self.env['ReadDecode'] = read_decode
        # Out-parameter syntax adapter only; Read + LoadData are one synthetic
        # port. Authored Open/Fault/StateValid keep all admission decisions.
        source = CHAINS.read_text()
        match = re.search(r'class HCSceneChainStore\s*\{', source)
        source = body(source, match.end())
        source = re.sub(r'\bHC(?:Scene|Story)\w*\b', lambda m: 'HCEvent' + m[0][2:], source)
        call = ('if (!HCGroupIO.Read(m_Path, 65536, m_Image) || '
                '!JsonFileLoader<HCEventSceneChainState>.LoadData(m_Image, state, error))')
        self.assertIn(call, source, 'update only the out-parameter adapter if Open syntax changes')
        source = source.replace(call, 'bool loaded; loaded, m_Image, state = ReadDecode(m_Path, state); if (!loaded)')
        for name in ('Open', 'Fault'):
            method = translate(source, name, self.env, 'HCEventSceneChainStore', member=True)
            setattr(owner, name, functools.partial(method, owner))
        # Saving is deliberately not part of Open's legacy read: verify no write.
        owner.Save = lambda state: self.writes.append(plain(state)) or True
        return owner

    def test_legacy_initializer_and_null_ports_already_pass_all_validators(self):
        self.assertNotIn('Stories', self.fixture)
        for row in self.fixture['Chains']:
            self.assertNotIn('StorySequence', row)
        for mode in ('initializer', 'null'):
            with self.subTest(mode=mode):
                state = self.decode(self.fixture, mode)
                # Explicit synthetic post-migration defaults for the direct
                # validator check. Open below must restore these from absence.
                if mode == 'initializer':
                    state.Stories = dto('HCStoryProgress', self.env)
                self.assertTrue(self.policy.HCUnmigrated(state.Stories))
                self.assertTrue(self.policy.HCValid(state))
                self.assertTrue(self.chains.CatalogValid(state.Catalog, False))
                for chain in state.Chains:
                    self.assertTrue(self.env['HCEventDirector'].StateValid(chain.Director))
                self.assertTrue(self.chains.StateValid(state))
                store = self.store(json.dumps(self.fixture), mode)
                self.assertIsNotNone(store.Open(NOW + 600))
                self.assertEqual(617, store.m_Revision)
                self.assertEqual([], self.writes)

    def test_open_constructs_defaults_before_loading_missing_story_fields(self):
        # Without an explicit output object this synthetic serializer port loses
        # absent progress defaults, and the authored HCValid rejects Version=0.
        state = self.decode(self.fixture, 'default-loss')
        self.assertFalse(self.policy.HCUnmigrated(state.Stories))
        self.assertFalse(self.policy.HCValid(state))
        store = self.store(json.dumps(self.fixture), 'default-loss')
        before = dict(self.disk)
        reopened = store.Open(NOW + 600)
        self.assertIsNotNone(reopened, 'missing Stories must retain explicitly constructed defaults')
        self.assertTrue(self.chains.StateValid(reopened))
        self.assertEqual(before, self.disk)
        self.assertEqual([], self.writes)

    def test_open_operator_off_gap_then_enable_migrates_once_and_reopens(self):
        store = self.store(json.dumps(self.fixture))
        state = store.Open(NOW + 600)
        pinned = plain(state)
        config = dto('HCStorySettings', self.env)
        config.EnableStories = False
        self.chains.LoadCatalog = self.chains.Defaults

        def schedule():
            return bind('HCStorySchedule', N(m_Ready=False, m_Reason='', m_State=None),
                        self.env, member=True)

        owner = schedule()
        self.assertFalse(owner.HCStart(state, store, config, NOW + 600, True))
        self.assertEqual('operator-off', owner.HCReason())
        self.assertEqual(pinned, plain(state), 'operator-off must retain the pinned legacy page')
        self.assertEqual([], self.writes)
        # Existing Scenes still owns downtime pausing, including active record
        # expiry; completed and cancelled rows retain their old deadlines.
        self.assertEqual(600, self.chains.ResumeAfterGap(state, NOW + 600))
        self.assertEqual(pinned['Chains'][0]['DueAt'] + 600, state.Chains[0].DueAt)
        self.assertEqual(pinned['Chains'][1]['DueAt'], state.Chains[1].DueAt)
        self.assertEqual(pinned['Chains'][2]['DueAt'], state.Chains[2].DueAt)
        self.assertTrue(self.chains.StateValid(state))
        config.EnableStories = True
        self.assertTrue(owner.HCStart(state, store, config, NOW + 610, True))
        self.assertEqual(1, len(self.writes), 'migration must save before admission')
        self.assertEqual(NOW + 600, state.LastNow)
        self.assertEqual((3, 4), (state.Stories.LegacyThrough, state.Stories.NextSequence))
        restarted_store = self.store(json.dumps(self.writes[0]))
        restarted = restarted_store.Open(NOW + 620)
        self.assertIsNotNone(restarted)
        self.assertTrue(schedule().HCStart(restarted, restarted_store, config, NOW + 620, True))
        self.assertEqual([], self.writes, 'reopening migrated state must not number/save again')
        self.assertTrue(any('runtime=PENDING' in line for line in self.logs))

    def test_refusals_identify_category_and_preserve_all_images(self):
        bad = copy.deepcopy(self.fixture)
        bad['Chains'][0]['ExpiresAt'] += 1
        for reason, image, now, flags in (
            ('state_invalid', json.dumps(bad), NOW, {}),
            ('clock', json.dumps(self.fixture), NOW - 1, {}),
            ('tmp', json.dumps(self.fixture), NOW, dict(tmp=True)),
            ('backup_only', json.dumps(self.fixture), NOW, dict(backup_only=True)),
            ('read', json.dumps(self.fixture), NOW, dict(read_ok=False)),
            ('read', '{invalid json', NOW, {}),
        ):
            with self.subTest(reason=reason):
                self.logs.clear()
                store = self.store(image, **flags)
                before = dict(self.disk)
                self.assertIsNone(store.Open(now))
                self.assertTrue(store.m_Fault)
                self.assertEqual(before, self.disk)
                self.assertEqual([], self.writes)
                self.assertTrue(any('[HollowCountry] V2 scenes persistence refused;' in line
                                    and 'reason=' + reason in line for line in self.logs),
                                'refusal must identify reason=' + reason)

    def test_migration_preserves_legacy_page_and_rejects_partial_or_migrated_corruption(self):
        state = self.decode(self.fixture)
        config = dto('HCStorySettings', self.env)
        pinned = plain(state)
        self.policy.HCMigrate(state, NOW + 600, config)
        self.assertTrue(self.chains.StateValid(state))
        self.assertEqual(NOW, state.LastNow)
        migrated = plain(state)
        self.assertEqual([1, 2, 3], [row.pop('StorySequence') for row in migrated['Chains']])
        del migrated['Stories']
        del pinned['Stories']
        for row in pinned['Chains']:
            del row['StorySequence']
        self.assertEqual(pinned, migrated, 'migration must only add story metadata')
        for field, value in (('NextSequence', 2), ('LegacyThrough', 1), ('NextArrival', 1),
                             ('TerminalThrough', 1), ('Version', 0),
                             ('LegacyIds', ['forged']), ('TerminalExceptions', [1])):
            with self.subTest(partial=field):
                bad = copy.deepcopy(self.fixture)
                bad['Stories'] = plain(dto('HCStoryProgress', self.env))
                bad['Stories'][field] = value
                store = self.store(json.dumps(bad))
                self.assertIsNone(store.Open(NOW))
        for mutate in (lambda s: setattr(s.Chains[0], 'StorySequence', 0),
                       lambda s: setattr(s.Stories, 'NextSequence', 99),
                       lambda s: s.Stories.TerminalExceptions.Insert(2),
                       lambda s: setattr(s.Chains[0].Director.Records[0], 'Status', 1)):
            bad = copy.deepcopy(state)
            mutate(bad)
            store = self.store(json.dumps(plain(bad)))
            self.assertIsNone(store.Open(NOW + 600))


if __name__ == '__main__':
    unittest.main()
