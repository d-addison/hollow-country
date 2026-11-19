"""Round 2 authored loaders and LOD tick work on explicit synthetic IO/budgets.
No native persistence, visibility, timing or DayZ acceptance is established.
"""
import json
import re
import unittest
from types import SimpleNamespace as N
from pathlib import Path

from tests.unit.test_hc_burn_infected import brace_ifs
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray, translated_rules
from tests.unit.test_infected_lod_followups import lod_config
from tests.unit.test_infected_lod import SERVICE, STORE, policy
from tests.unit.json_loader_port import overlay, json_fields_port
from tests.unit.tick_budget_fixture import new_budget, budget_class

ROOT = Path(__file__).resolve().parents[2]
GROUP_STORE = ROOT / 'mods/HollowCountry/scripts/4_World/Groups/HCGroupStore.c'
GROUP_DATA = ROOT / 'mods/HollowCountry/scripts/3_Game/Groups/HCGroupData.c'


def syntax_port(text):
    text = brace_ifs(text)
    # The restricted adapter has no else-if or postfix-increment syntax.
    while 'else if (' in text:
        start = text.index('else if (')
        opening = text.index('{', start)
        depth, end = 1, opening + 1
        while depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        text = text[:end] + ' }' + text[end:]
        text = text[:start] + 'else { ' + text[start+5:]
    return re.sub(r'(\b[\w.]+)\+\+;', r'\1 += 1;', text)


class LoaderFixture:
    def __init__(self, module, image, save_ok=True):
        self.files = {}
        self.logs = []
        self.reasons = []
        self.saves = []
        self.module = module
        group = module == 'Groups'
        self.kind = 'HCGroupSettings' if group else 'HCInfectedLODConfig'
        self.path = '$profile:HollowCountry/Groups/settings.json' if group else '$profile:HollowCountry/Infected/lod.json'
        def lod_defaults():
            cfg, source = lod_config()
            fields = re.findall(r'^    (?:int|float|bool|string) (\w+) =', source.split('static string DefaultMemberType')[0], re.M)
            return N(**{key: getattr(cfg, key) for key in fields}, MemberTypes=EArray(), Herds=EArray())
        self.factory = translated_rules()['HCGroupSettings'] if group else lod_defaults
        self.files[self.path] = image
        self.save_ok = save_ok
        text = GROUP_STORE.read_text() if group else STORE.read_text().split('class HCInfectedLODHerd\n')[0]
        text = re.sub(r'reason = ("[^"]*");', r'reason = refusal(\1);', text)
        # Syntax-only out-parameter and type adaptations. Native IO is synthetic.
        text = re.sub(r'(?:HCGroupIO.Read|HCInfectedStore.ReadBounded)\(path, (?:8192, )?content\)',
                      '((content := read(path)) != null)', text)
        text = re.sub(r'JsonFileLoader<\w+>.LoadData\(content, (\w+), error\)',
                      r'((\1 := decode(content)) != null)', text)
        text = re.sub(r'(?:HCV2ThreatStore|HCGroupJson|JsonFileLoader)<\w+>', 'StorePort', text)
        text = re.sub(r'\bHC\w+ (?=\w+\s*[;=])', 'HCEventHandle ', text)
        text = text.replace('static '+self.kind+' ', 'static HCEventHandle ')
        self.env = dict(FileExist=lambda p: p in self.files, MakeDirectory=lambda p: True,
                        read=lambda p: self.files.get(p), decode=self.decode, Print=self.logs.append,
                        refusal=lambda value: self.reasons.append(value) or value,
                        HCJsonFields=json_fields_port(), HCGroupRules=N(SettingsValid=translated_rules()['SettingsValid']),
                        HCInfectedStore=N(ROOT='$profile:HollowCountry', DIRECTORY='$profile:HollowCountry/Infected'),
                        StorePort=N(CanOpen=lambda p: not (p+'.tmp' in self.files), Save=self.save,
                                    SaveFile=lambda p,c,e: self.save(p,c,65536), WriteNew=self.save),
                        **{self.kind: self.factory})
        restore_text = GROUP_DATA.read_text() if group else text
        restore_text = re.sub(r'\bHC\w+ (?=\w+\s*[;=])', 'HCEventHandle ', restore_text)
        restore = translate(restore_text, 'HCRestoreMissingDefaults', self.env)
        self.env['HCRestoreMissingDefaults'] = restore
        self.env['HCGroupSettingDefaults'] = N(HCRestoreMissingDefaults=restore)
        self.load = translate(syntax_port(text), 'LoadSettings' if group else 'Load', self.env)

    def decode(self, content):
        try:
            cfg = overlay(json.loads(content), self.factory(), EArray)
        except (ValueError, TypeError):
            return None
        if self.module != 'Groups':
            # Execute the authored validator on empty synthetic class/seed arrays.
            text = lod_config()[1]
            text = re.sub(r'for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)',
                          r'foreach (int \1 : indices(\2))', text)
            fields = re.findall(r"^    (?:int|float|bool|string) (\w+) =", text.split("static string DefaultMemberType")[0], re.M) + ["MemberTypes", "Herds"]
            for key in fields:
                text = re.sub(r'(?<![\w.])'+key+r'\b', 'm_'+key, text)
            text = re.sub(r'\bHC\w+ (?=\w+\s*[;=])', 'HCEventHandle ', text)
            fn = translate(text, 'IsValid', dict(HCLODPolicy=policy(), indices=range,
                           HCInfectedVarietyPolicy=N(ValidNonCalmHold=lambda n: 30 <= n <= 3600)), member=True)
            cfg.IsValid = lambda: fn(N(**{'m_'+k:v for k,v in vars(cfg).items() if k != 'IsValid'}))
        return cfg

    def save(self, path, cfg, limit):
        self.saves.append(path)
        if not self.save_ok:
            return False
        self.files[path] = json.dumps({k:v for k,v in vars(cfg).items() if not callable(v)})
        return True

    def run(self):
        return self.load() if self.module == 'Groups' else self.load('')


class SettingsMigration(unittest.TestCase):
    # Explicit compatibility defaults; all other declared settings are required.
    ALLOWED_MISSING = {'Groups': {'ShareDiscovery'},
                       'InfectedLOD': {'EnableVirtualHerds', 'HerdWorld', 'VarietyNonCalmHoldSeconds'}}

    def image(self, module, version=1, omit=False):
        cfg = LoaderFixture(module, '{}').factory()
        values = vars(cfg).copy()
        values['SchemaVersion'] = version
        key = 'ShareDiscovery' if module == 'Groups' else 'EnableVirtualHerds'
        values[key] = False
        if omit:
            del values[key]
        return json.dumps(values), key

    def test_v1_generated_false_migrates_and_rewrites_v2_once(self):
        for module in ('Groups', 'InfectedLOD'):
            with self.subTest(module=module):
                image, key = self.image(module)
                h = LoaderFixture(module, image)
                cfg = h.run()
                self.assertIsNotNone(cfg)
                self.assertTrue(getattr(cfg, key), 'v1 generated false must migrate to owner default-on')
                self.assertEqual(2, json.loads(h.files[h.path])['SchemaVersion'])
                self.assertTrue(json.loads(h.files[h.path])[key])
                line = f'[HC {module}] settings migrated v1->v2 {key}=true (owner default-on; set false to opt out)'
                self.assertEqual([line], [s for s in h.logs if 'settings migrated' in s])
                h.run()
                self.assertEqual(1, len(h.saves))

    def test_v2_false_keeps_opt_out_and_file(self):
        for module in ('Groups', 'InfectedLOD'):
            image, key = self.image(module, version=2)
            h = LoaderFixture(module, image)
            cfg = h.run()
            self.assertIsNotNone(cfg)
            self.assertFalse(getattr(cfg, key))
            self.assertEqual(image, h.files[h.path])
            self.assertEqual([], h.saves)

    def test_every_missing_baseline_field_refuses_and_preserves_bytes(self):
        for module in ('Groups', 'InfectedLOD'):
            for version in (1, 2):
                image, _ = self.image(module, version)
                fields = json.loads(image)
                for key in fields.keys() - self.ALLOWED_MISSING[module]:
                    with self.subTest(module=module, version=version, missing=key):
                        partial = fields.copy()
                        del partial[key]
                        content = json.dumps(partial, indent=2) + '\n'
                        h = LoaderFixture(module, content)
                        self.assertIsNone(h.run(), f'{module} missing {key} must refuse')
                        self.assertEqual(content, h.files[h.path])
                        self.assertEqual([], h.saves)
                        self.assertFalse(any('settings migrated' in s for s in h.logs))
                        diagnostics = h.logs if module == 'Groups' else h.reasons
                        self.assertEqual(1, sum('settings_missing_baseline_fields' in s for s in diagnostics))

    def test_only_named_compatibility_fields_can_default(self):
        for module, allowed in self.ALLOWED_MISSING.items():
            for version in (1, 2):
                image, _ = self.image(module, version)
                full = json.loads(image)
                for key in allowed:
                    with self.subTest(module=module, version=version, missing=key):
                        partial = full.copy()
                        del partial[key]
                        h = LoaderFixture(module, json.dumps(partial))
                        cfg = h.run()
                        self.assertIsNotNone(cfg)
                        self.assertEqual(getattr(h.factory(), key), getattr(cfg, key))

    def test_explicit_false_baseline_booleans_are_kept_in_v2(self):
        for module in ('Groups', 'InfectedLOD'):
            image, _ = self.image(module, version=2)
            fields = json.loads(image)
            for key, value in fields.items():
                if isinstance(value, bool):
                    fields[key] = False
            content = json.dumps(fields, indent=2) + '\n'
            h = LoaderFixture(module, content)
            cfg = h.run()
            self.assertIsNotNone(cfg)
            for key, value in fields.items():
                if isinstance(value, bool):
                    self.assertIs(False, getattr(cfg, key))
            self.assertEqual(content, h.files[h.path])
            self.assertEqual([], h.saves)

    def test_missing_key_restores_on_for_both_versions(self):
        for module in ('Groups', 'InfectedLOD'):
            for version in (1, 2):
                image, key = self.image(module, version, omit=True)
                h = LoaderFixture(module, image)
                self.assertTrue(getattr(h.run(), key))

    def test_malformed_and_invalid_never_rewrite(self):
        for module in ('Groups', 'InfectedLOD'):
            image, key = self.image(module)
            bad = json.loads(image)
            bad['MaxGroups' if module == 'Groups' else 'ClassifyPerTick'] = -1
            for content in ('{broken', json.dumps(bad)):
                h = LoaderFixture(module, content)
                self.assertIsNone(h.run())
                self.assertEqual(content, h.files[h.path])
                self.assertEqual([], h.saves)

    def test_migration_write_failure_refuses_without_success_log(self):
        for module in ('Groups', 'InfectedLOD'):
            image, _ = self.image(module)
            h = LoaderFixture(module, image, save_ok=False)
            self.assertIsNone(h.run())
            self.assertFalse(any('settings migrated' in s for s in h.logs))

    def test_pending_temporary_refuses_without_rewriting(self):
        for module in ('Groups', 'InfectedLOD'):
            image, _ = self.image(module)
            h = LoaderFixture(module, image)
            h.files[h.path+'.tmp'] = 'synthetic interrupted migration'
            self.assertIsNone(h.run())
            self.assertEqual(image, h.files[h.path])
            self.assertEqual([], h.saves)

    def test_migrations_use_recovery_checked_verified_store(self):
        for path, kind in ((GROUP_STORE, 'HCGroupSettings'), (STORE, 'HCInfectedLODConfig')):
            text = path.read_text()
            self.assertIn(f'HCV2ThreatStore<{kind}>.CanOpen(path)', text)
            self.assertIn(f'HCV2ThreatStore<{kind}>.Save(path,', text)

    def test_unused_mission_templates_are_absent(self):
        for name in ('infected/lod.json', 'groups/settings.json'):
            self.assertFalse((ROOT / 'mission/hollow-country' / name).exists())


class LODWorkBudget(unittest.TestCase):
    def test_classify_yields_without_advancing_cursor_and_resumes(self):
        work = new_budget()
        work.HCReset(1)
        klass = budget_class()
        obj = N(m_Healthy=True, m_Actors=EArray([N(InfectedEntity=None) for _ in range(4)]), m_HCLODCursor=0)
        text = SERVICE.read_text().split('modded class HCInfectedModule', 1)[1].split('class HCInfectedLODModule', 1)[0]
        text = re.sub(r'\bHC\w+ (?=\w+\s*[;=])', 'HCEventHandle ', text)
        fn = translate(syntax_port(text), 'HCLODClassify', dict(HCServer=N(HCTickWork=lambda: work), HCUnitBudget=klass), member=True)
        obj.HCLODClassify = lambda *args: fn(obj, *args)
        work.HCTakeFor(0, 1)
        self.assertEqual(1, obj.HCLODClassify(EArray(), 1, 4, 300, 1000), 'one forced item, then yield')
        self.assertEqual(1, obj.m_HCLODCursor)
        self.assertEqual(0, obj.HCLODClassify(EArray(), 1, 4, 300, 1000))
        self.assertEqual(1, obj.m_HCLODCursor)
        work.HCReset(1)
        self.assertEqual(1, obj.HCLODClassify(EArray(), 2, 4, 300, 1000))
        self.assertEqual(2, obj.m_HCLODCursor)

    def test_herd_yields_whole_step_and_resumes_next_tick(self):
        work = new_budget()
        work.HCReset(1)
        calls = []
        infected = N(HCLODClassify=lambda *a: None)
        obj = N(m_Running=True, m_Config=N(ClassifyPerTick=12, FullRange=300, IdleRange=1000, MaxObservers=6),
                m_Herds=True, m_Store=N(Healthy=lambda: True), m_Sight=N(HCReset=lambda n: calls.append('sight'), Used=0),
                m_FoldTurn=False, m_Rays=0, m_RayPeak=0, m_RegrowAt=1000, m_StatsAt=1000, m_Experiment=None,
                HCLODPollLeases=lambda *a: calls.append('poll'), HCLODFoldStep=lambda *a: calls.append('fold'),
                HCLODMaterializeStep=lambda *a: calls.append('materialize'))
        env = dict(HCServer=N(HCTickWork=lambda: work), HCUnitBudget=budget_class(),
                   HCInfectedModule=N(Instance=infected), GetGame=lambda: N(GetTickTime=lambda: 10),
                   HCPerfPlayers=N(HCGet=lambda: EArray()), HCInfectedLOD=N(RAYS_PER_OBSERVER=6),
                   Math=N(Max=max))
        text = SERVICE.read_text().split('class HCInfectedLODModule : HCModule', 1)[1]
        text = re.sub(r'\bHC\w+ (?=\w+\s*[;=])', 'HCEventHandle ', text)
        for name in ('HCLODPollLeases', 'HCLODFoldStep', 'HCLODMaterializeStep', 'HCLODRegrow', 'HCLODStats'):
            text = re.sub(r'(?<![\w.])'+name+r'\(', 'self.'+name+'(', text)
        fn = translate(syntax_port(text), 'OnTick', env, member=True)
        obj.OnTick = lambda delta: fn(obj, delta)
        work.HCTakeFor(0, 1)
        obj.OnTick(1)
        self.assertEqual(['sight', 'poll', 'materialize'], calls)
        calls.clear()
        obj.OnTick(1)
        self.assertEqual([], calls, 'spent herd allowance skips poll, geometry, fold, materialize and regrow')
        self.assertTrue(obj.m_FoldTurn)
        work.HCReset(1)
        obj.OnTick(1)
        self.assertEqual(['sight', 'poll', 'fold'], calls)

    def test_consumer_ids_keep_existing_assignments(self):
        klass = budget_class()
        for index, name in enumerate(('INFECTED', 'INTERIORS', 'SEARCH_BIND', 'SEARCH_MAINT', 'SEARCH_REFRESH', 'SEARCH_DETACHED')):
            self.assertEqual(index, getattr(klass, 'HC_WORK_'+name))
        self.assertEqual(6, getattr(klass, 'HC_WORK_LOD_CLASSIFY', None))
        self.assertEqual(7, getattr(klass, 'HC_WORK_LOD_HERD', None))
        self.assertEqual(8, getattr(klass, 'HC_WORK_BASES', None))
        self.assertEqual(9, getattr(klass, 'HC_WORK_CONFLICT', None))
        self.assertEqual(10, getattr(klass, 'HC_WORK_TRADE', None))
        self.assertEqual(11, klass.HC_WORK_CONSUMERS)
        conflict = (ROOT / 'mods/HollowCountry/scripts/4_World/World/HCFactionConflict.c').read_text(encoding='utf-8')
        self.assertIn('HCTakeFor(HCUnitBudget.HC_WORK_CONFLICT, 1)', conflict)
