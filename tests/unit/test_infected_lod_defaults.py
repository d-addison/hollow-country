"""#135: authored seed/migration decisions with synthetic JSON and filesystem ports.

These fixtures execute source bodies; they establish no native DayZ behaviour.
"""
import json
import re
import unittest
from types import SimpleNamespace as NS

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_defaults_round2 import syntax_port
from tests.unit.test_infected_lod import ROOT, STORE, SERVICE, policy
from tests.unit.test_infected_lod_followups import lod_config
from tests.unit.json_loader_port import overlay, json_fields_port
from tests.unit.test_hc_status_review_round1 import bind
from tests.unit.test_hc_module_readiness_wave16 import FakeStatus


class Profile:
    """Explicit synthetic filesystem, serializer and installed-class catalogue."""
    def __init__(self, image=None, save_ok=True):
        self.image = image
        self.logs = []
        self.reasons = []
        self.saves = []
        self.save_ok = save_ok
        text = STORE.read_text().split('class HCInfectedLODHerd\n')[0]
        self.env = dict(EArray=EArray, HCLODPolicy=policy(), indices=range,
                        Print=self.logs.append, HCJsonFields=json_fields_port(),
                        HCInfectedVarietyPolicy=NS(ValidNonCalmHold=lambda n: 30 <= n <= 3600),
                        GetGame=lambda: NS(ConfigIsExisting=lambda t: True, IsKindOf=lambda *a: True))
        fields = re.findall(r'^    (?:int|float|bool|string) (\w+) =',
                            text.split('class HCInfectedLODConfig', 1)[1].split('static string DefaultMemberType')[0], re.M) + ['Herds', 'MemberTypes']
        valid_text = re.sub(r'for \(int (\w+) = 0; \1 < ([^;]+); \1\+\+\)',
                            r'foreach (int \1 : indices(\2))', text)
        valid_text = re.sub(r'HCInfectedLODHerdSeed (?=seed)', 'HCEventHandle ', valid_text)
        for field in fields:
            valid_text = re.sub(r'(?<![\w.])' + field + r'\b', 'm_' + field, valid_text)
        valid = translate(valid_text, 'IsValid', self.env, member=True)
        def factory():
            raw, _ = lod_config()
            cfg = NS(**{k: getattr(raw, k) for k in fields})
            cfg.IsValid = lambda: valid(NS(**{'m_' + k: getattr(cfg, k) for k in fields}))
            return cfg
        self.factory = factory
        self.env['HCInfectedLODConfig'] = factory
        self.env['HCInfectedLODHerdSeed'] = lambda: NS(Id='', X=0., Z=0., Radius=60., HeadCount=12)
        for name in ('HCSeed', 'HCSeedDefaults', 'HCRestoreMissingDefaults'):
            if re.search(r'void ' + name + r'\(', text):
                adapted = re.sub(r'\bHCInfected\w+ (?=\w+\s*[;=])', 'HCEventHandle ', text)
                fn = translate(adapted, name, self.env, owner='HCInfectedLODConfig')
                setattr(factory, name, fn)
                self.env[name] = fn
        adapted = text.replace('new array<ref HCInfectedLODHerdSeed>;', 'new array<ref HCInfectedLODHerdSeed>();')
        adapted = re.sub(r'([\w.]+)\.Count\(\)\.ToString\(\)', r'str(\1.Count())', adapted)
        adapted = re.sub(r'reason = ("[^"]*");', r'reason = refusal(\1);', adapted)
        adapted = adapted.replace('HCInfectedStore.ReadBounded(path, content)', '((content := read()) != null)')
        adapted = re.sub(r'JsonFileLoader<\w+>.LoadData\(content, config, error\)',
                         '((config := decode(content)) != null)', adapted)
        adapted = re.sub(r'(?:JsonFileLoader|HCV2ThreatStore)<\w+>', 'StorePort', adapted)
        adapted = re.sub(r'\bHCInfected\w+ (?=\w+\s*[;=])', 'HCEventHandle ', adapted)
        adapted = adapted.replace('static HCInfectedLODConfig Load', 'static HCEventHandle Load')
        self.env.update(FileExist=lambda p: self.image is not None, MakeDirectory=lambda p: True,
                        read=lambda: self.image, decode=self.decode,
                        refusal=lambda reason: self.reasons.append(reason) or reason,
                        HCInfectedStore=NS(ROOT='synthetic-profile', DIRECTORY='synthetic-profile/Infected'),
                        StorePort=NS(CanOpen=lambda p: True, Save=self.save,
                                     SaveFile=lambda p,c,e: self.save(p,c,65536)))
        self.load = translate(syntax_port(adapted), 'Load', self.env)

    def decode(self, content):
        cfg = overlay(json.loads(content), self.factory(), EArray)
        cfg.IsValid = lambda: self.validate(cfg)
        return cfg

    def validate(self, cfg):
        fresh = self.factory()
        for key, value in vars(cfg).items():
            if key != 'IsValid': setattr(fresh, key, value)
        return fresh.IsValid()

    def save(self, path, cfg, limit):
        self.saves.append(path)
        if not self.save_ok: return False
        self.image = json.dumps(cfg, default=lambda obj: {k:v for k,v in vars(obj).items() if not callable(v)})
        return True

    def run(self):
        return self.load('')


def legacy(version=2, **changes):
    profile = Profile()
    values = {k:v for k,v in vars(profile.factory()).items() if not callable(v)}
    values.update(SchemaVersion=version, Herds=[])
    values.update(changes)
    return json.dumps(values)


class DefaultHerds(unittest.TestCase):
    def test_fresh_profile_gets_eight_bounded_unique_inland_seeds(self):
        profile = Profile()
        cfg = profile.run()
        self.assertIsNotNone(cfg)
        self.assertEqual(8, len(cfg.Herds), 'fresh profile must seed eight herds')
        self.assertEqual(3, cfg.SchemaVersion)
        self.assertTrue(cfg.EnableVirtualHerds)
        self.assertEqual(8, len({seed.Id for seed in cfg.Herds}))
        for seed in cfg.Herds:
            self.assertTrue(policy().ValidHerd(seed.X, seed.Z, seed.Radius, seed.HeadCount, seed.HeadCount))
            self.assertGreater(seed.Z, 4000, 'no south coastal spawns')
        self.assertEqual(8, len(json.loads(profile.image)['Herds']))

    def test_empty_v2_migrates_once_and_logs_after_verified_save(self):
        profile = Profile(legacy())
        cfg = profile.run()
        self.assertIsNotNone(cfg)
        self.assertEqual(8, len(cfg.Herds))
        self.assertEqual(3, cfg.SchemaVersion)
        self.assertIn('[HC InfectedLOD] settings migrated v2->v3 herds=8 runtime=PENDING', profile.logs)
        profile.run()
        self.assertEqual(1, len(profile.saves))

    def test_absent_legacy_herds_migrates_but_other_baseline_omissions_refuse(self):
        for version in (1, 2):
            values = json.loads(legacy(version))
            del values['Herds']
            cfg = Profile(json.dumps(values)).run()
            self.assertIsNotNone(cfg)
            self.assertEqual(8, len(cfg.Herds))
            for key in values.keys() - {'EnableVirtualHerds', 'HerdWorld', 'VarietyNonCalmHoldSeconds'}:
                with self.subTest(version=version, missing=key):
                    partial = dict(values)
                    del partial[key]
                    image = json.dumps(partial)
                    profile = Profile(image)
                    self.assertIsNone(profile.run())
                    self.assertEqual(image, profile.image)
                    self.assertFalse(profile.saves)

    def test_explicit_nonempty_seeds_are_preserved(self):
        seed = dict(Id='synthetic-custom', X=7000, Z=8000, Radius=90, HeadCount=23)
        profile = Profile(legacy(Herds=[seed]))
        cfg = profile.run()
        self.assertEqual([seed], json.loads(profile.image)['Herds'])
        self.assertEqual(23, cfg.Herds[0].HeadCount)

    def test_v2_operator_opt_out_survives_seed_migration(self):
        cfg = Profile(legacy(EnableVirtualHerds=False)).run()
        self.assertIsNotNone(cfg)
        self.assertFalse(cfg.EnableVirtualHerds)
        starts, logs = [], []
        owner = NS(m_Running=False, m_Herds=False, m_Store=None,
                   m_Refusal='', m_Operational=FakeStatus())
        bind(owner, SERVICE, 'HCInfectedLODModule', ['OnStart', 'IsEnabled'], dict(
            Print=logs.append, GetGame=lambda: NS(IsServer=lambda: True, GetTickTime=lambda: 10),
            HCInfectedLODConfig=NS(Load=lambda reason: cfg),
            HCV2Admission=NS(Line=lambda *a: 'synthetic admission',
                            Admitted=lambda preference: preference, OnOff=lambda enabled: 'off'),
            HCV2Gates=NS(Qualified=lambda gate: False),
            HCInfectedLOD=NS(HCSet=lambda config: None), HCLODSightBudget=lambda: NS(),
            HCInfectedLODStore=lambda: starts.append('store-created'),
            HCInfectedLODExperiment=lambda: NS(HCArm=lambda: False)))
        owner.OnStart(NS(EnableInfected=True, EnableDebugSnapshot=False))
        self.assertTrue(owner.m_Running, 'LOD classification remains enabled')
        self.assertFalse(owner.m_Herds)
        self.assertEqual([], starts, 'opt-out must not even create the herd store')
        self.assertTrue(any('herds=off' in line for line in logs))
        text = SERVICE.read_text()
        self.assertIn('bool herdPreference = m_Config.EnableVirtualHerds && lodPreference;', text)
        self.assertIn('if (HCV2Admission.Admitted(herdPreference))', text)
        self.assertIn('if (m_Herds && m_Store.Healthy() && HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_LOD_HERD, 1))', text)

    def test_invalid_null_and_current_partial_files_are_preserved(self):
        for changes in ({'Herds': None}, {'FullRange': 0}, {'SchemaVersion': 99},
                        {'Herds': [dict(Id='bad', X=0, Z=0, Radius=1, HeadCount=999)]}):
            image = legacy(**changes)
            profile = Profile(image)
            self.assertIsNone(profile.run())
            self.assertEqual(image, profile.image)
            self.assertFalse(profile.saves)
        values = json.loads(legacy(3))
        del values['Herds']
        self.assertIsNone(Profile(json.dumps(values)).run())

    def test_migration_write_failure_refuses_without_success_log(self):
        profile = Profile(legacy(), save_ok=False)
        self.assertIsNone(profile.run())
        self.assertFalse(any('settings migrated' in line for line in profile.logs))

    def test_each_seed_cites_an_exact_existing_rural_or_woodland_anchor(self):
        cfg = Profile().run()
        catalogue = ROOT / 'mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c'
        lines = catalogue.read_text().splitlines()
        text = STORE.read_text()
        self.assertEqual(8, len(cfg.Herds))
        for seed in cfg.Herds:
            pattern = r'// .*HCShelterCatalog.c:(\d+)[^\n]*\n\s*HCSeed\(config, "' + re.escape(seed.Id) + r'"'
            match = re.search(pattern, text)
            self.assertIsNotNone(match, seed.Id)
            anchor = re.search(r'"([\d.]+) [\d.]+ ([\d.]+)"', lines[int(match[1]) - 1])
            self.assertEqual((seed.X, seed.Z), tuple(map(float, anchor.groups())))
