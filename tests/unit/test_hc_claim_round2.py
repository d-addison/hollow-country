"""HC-17 review regressions; every engine/IO fixture here is synthetic.

Execute authored handlers, never a second Python gameplay policy. These checks
do not establish Enforce compilation, native persistence or client delivery.
"""
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_hc_building_claim import ROOT, CLAIMS, run
from tools.validate.enforce_source import clean

WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'
OWNED = ('Camps/HCBuildingClaim.c', 'Camps/HCCampStore.c', 'Camps/HCCampScan.c',
         'Camps/HCCampTiers.c', 'Camps/HCCampMailbox.c', 'Camps/HCCampModule.c',
         'Actions/HCClaimBuildingActions.c', 'Crafting/HCNoConstruction.c',
         'Crafting/HCRecipeRegistration.c')


def adapted(source):
    # Language-only declaration aliases for the restricted group translator.
    source = re.sub(r'\b(?:HCCampData|HCOperationalStatus)\b', 'HCGroupMember', source)
    source = re.sub(r'\bHCBuildingClaim (?=\w+\s*=)', 'HCGroupClaim ', source)
    source = re.sub(r'\b(?:Building|HCGroupService) (?=\w+\s*=)', 'HCGroupObject ', source)
    source = source.replace('new array<ref HCBuildingClaimRecord>()', 'new HCGroupClaimArray')
    source = re.sub(r'(?<![.\w])(Fail|Commit|IsEnabled|ActionCondition|HCReleaseRequest)\(', r'self.\1(', source)
    source = re.sub(r'\b(bool|void) self\.', r'\1 ', source)
    source = source.replace('s_Instance', 'self.s_Instance').replace('this', 'self')
    return source


class ClaimReviewBehavior(unittest.TestCase):
    def test_owned_statements_respect_native_plus_limit(self):
        # Semicolons inside literals/comments are blanked before splitting.
        self.assertEqual(0, clean('"+;+"; /* + */ // +\n').count('+'))
        violations = []
        for relative in OWNED:
            source = clean((WORLD / relative).read_text())
            for statement in re.split(r'[;{}]', source):
                if statement.count('+') > 9:
                    violations.append((relative, statement.count('+'), statement.strip()))
        self.assertEqual([], violations)

    def test_legacy_store_load_migrates_only_empty_claims_and_preserves_camps(self):
        source = adapted((WORLD / 'Camps/HCCampStore.c').read_text())
        source = source.replace('HCV2ThreatStore<HCGroupMember>.', 'Store.')
        source = source.replace('Store.Load(PATH, BYTES, data)', 'load_data()')
        camps = EArray([NS(Id='synthetic-original-fire', Tier=2, Members=EArray(['native-ref']))])
        row = NS(ClaimsVersion=0, Claims=None, Camps=camps)
        before = repr(camps)
        for empty in (None, EArray()):
            row.ClaimsVersion, row.Claims = 0, empty
            env = dict(PATH='synthetic/camps.json', BYTES=1048576,
                       Store=NS(CanOpen=lambda path: True), FileExist=lambda path: True,
                       Print=lambda line: None, HCGroupClaimArray=EArray,
                       load_data=lambda: True, Valid=lambda data, now: data.ClaimsVersion == 1 and data.Claims is not None)
            # JSON out-param is the only IO adaptation; retain the actual Load flow.
            fixture = source.replace('HCGroupMember data;', 'HCGroupMember data = fixture_data;')
            env['fixture_data'] = row
            if 'HCClaimsMigrate(' in source:
                env['HCClaimsMigrate'] = lambda data: run(source, 'HCClaimsMigrate', NS(), env, data)
            loaded = run(fixture, 'Load', NS(), env, 1000)
            self.assertIs(row, loaded)
            self.assertEqual(1, row.ClaimsVersion)
            self.assertEqual([], row.Claims)
            self.assertIs(camps, row.Camps)
            self.assertEqual(before, repr(camps))
        # Never relabel populated unknown metadata as a supported schema.
        row.ClaimsVersion, row.Claims = 0, EArray([NS(GroupId=7)])
        self.assertIsNone(run(fixture, 'Load', NS(), env, 1000))

    def test_partial_config_defaults_once_and_nonzero_invalid_refuses(self):
        source = CLAIMS.read_text().split('class HCBuildingClaim\n')[0]
        class Number(float):
            def ToString(self): return format(self, 'g')
        logs = []
        env = dict(UAMaxDistances=NS(DEFAULT=2), Print=logs.append)
        # Bind authored scalar constants; only native reach/ToString are stubs.
        for name, expression in re.findall(r'static const (?:int|float) (\w+) = ([^;]+);', source):
            env[name] = Number(eval(expression, {'__builtins__': {}}, env))
        fields = ('Version', 'ExpiryDays', 'VisitRadiusMeters', 'ActionReachMeters')
        for field in fields:
            source = re.sub(r'"(?:\\.|[^"\\])*"|(?<![.\w])' + field + r'\b',
                            lambda match: match[0] if match[0].startswith('"') else 'self.' + field, source)
        config = NS(**dict.fromkeys(fields, 0))
        self.assertTrue(run(source, 'HCValid', config, env))
        self.assertEqual([1, 30, 25, 2], [getattr(config, key) for key in fields])
        self.assertEqual(['[HC Plan] HC-17 policy ' + key + ' absent; default ' + value
                          for key, value in zip(fields, ('1', '30', '25', '2'))], logs)
        self.assertTrue(run(source, 'HCValid', config, env))
        self.assertEqual(4, len(logs))
        for key, bad in zip(fields, (2, 6, 1001, 3)):
            original = getattr(config, key)
            setattr(config, key, bad)
            self.assertFalse(run(source, 'HCValid', config, env), key)
            setattr(config, key, original)
        logs.clear()
        config.ExpiryDays, config.VisitRadiusMeters = 60, 0
        self.assertTrue(run(source, 'HCValid', config, env))
        self.assertEqual(60, config.ExpiryDays)
        self.assertEqual(['[HC Plan] HC-17 policy VisitRadiusMeters absent; default 25'], logs)

    def test_boot_grace_prevents_downtime_expiry_without_renewing_visits(self):
        source = CLAIMS.read_text()
        boot = 1000 + 90 * 86400
        state = NS(m_BootUtc=boot, m_Config=NS(ExpiryDays=30))
        row = NS(LastVisitUtc=1000)
        expire = lambda now, group=1: run(source, 'HCShouldExpire', state, {}, row, now, group)
        self.assertFalse(expire(boot))
        self.assertFalse(expire(boot + 30 * 86400 - 1))
        self.assertTrue(expire(boot + 30 * 86400))
        self.assertFalse(expire(boot + 30 * 86400, -1))
        self.assertTrue(expire(boot, 0))
        row.LastVisitUtc = boot + 20 * 86400
        self.assertFalse(expire(boot + 30 * 86400))
        self.assertTrue(expire(boot + 50 * 86400))
        row.LastVisitUtc = 1000
        self.assertEqual(1000, row.LastVisitUtc)
        self.assertIn('service.m_BootUtc = service.m_LastUtc;', source)

    def test_native_commit_refusals_are_observable_without_condition_logs(self):
        source = (WORLD / 'Crafting/HCNoConstruction.c').read_text()
        logs, calls = [], []
        env = dict(HCNoConstruction=NS(HCDeniedRecipe=lambda name: True),
                   ClassName=lambda: 'CraftFenceKit', Print=logs.append,
                   super=NS(PerformRecipe=lambda *args: calls.append(args)))
        run(source, 'PerformRecipe', NS(ClassName=lambda: 'CraftFenceKit'), env, None, None, None)
        self.assertEqual([], calls)
        self.assertTrue(logs, 'denied native recipe must log a reason')
        for owner in ('ActionBuildPart', 'ActionDeployObject', 'ActionDeployBase'):
            part = source.split('modded class ' + owner + '\n')[1].split('modded class ')[0]
            logs.clear()
            env['super'].OnFinishProgressServer = lambda data: calls.append(data)
            run(part, 'OnFinishProgressServer', NS(), env, None)
            self.assertTrue(logs, owner)
        # Preview conditions run every frame: ordinary false is quiet.
        for condition in re.findall(r'override bool ActionCondition[^\{]+\{(.*?)\n    }', source, re.S):
            self.assertNotIn('Print(', condition)

    def test_release_gates_actual_building_and_reports_server_refusal(self):
        source = CLAIMS.read_text()
        actions = adapted((WORLD / 'Actions/HCClaimBuildingActions.c').read_text())
        logs, messages = [], []
        actor = NS(MessageStatus=messages.append)
        env = dict(Print=logs.append, HCBuildingClaim=NS(HCGet=lambda: None))
        action = NS(ActionCondition=lambda *args: False)
        data = NS(Player=actor, Target=None, MainItem=None)
        actions = actions.replace('action_data.m_', 'action_data.')
        run(actions, 'OnFinishProgressServer', action, env, data)
        self.assertTrue(messages)
        self.assertIn('HCHoldsClaim(', actions.split('override bool ActionCondition')[1].split('override void')[0])
        state = NS(m_Data=NS(Claims=EArray([NS(GroupId=7, BuildingId='held')])))
        for group, key, expected in ((7, 'held', True), (7, 'other', False), (8, 'held', False)):
            self.assertEqual(expected, run(source, 'HCHoldsClaim', state, {}, group, key))
        # Execute the real server preview with a deliberately unowned building.
        selected = ['other']
        building = NS(GetDoorIndex=lambda component: 0)
        target = NS(GetObject=lambda: building, GetParent=lambda: None, GetComponentIndex=lambda: 0)
        service = NS(HCHoldsClaim=lambda group, key: run(source, 'HCHoldsClaim', state, {}, group, key))
        groups = NS(HCClaimActorGroup=lambda player, manager: 7)
        env.update(GetGame=lambda: NS(IsServer=lambda: True), UAMaxDistances=NS(DEFAULT=2),
                   Building=NS(Cast=lambda value: value), HCGroupService=NS(Get=lambda: groups),
                   HCBuildingClaim=NS(HCGet=lambda: service, HCActor=lambda player: True,
                                      HCDoor=lambda obj, index: True, HCIdentity=lambda obj: selected[0]),
                   IsInReach=lambda *args: True)
        action.HCReleaseRequest = lambda: True
        self.assertFalse(run(actions, 'ActionCondition', action, env, actor, target, None))
        selected[0] = 'held'
        self.assertTrue(run(actions, 'ActionCondition', action, env, actor, target, None))
        # Authoritative commit refusal is delivered through native MessageStatus.
        service.HCRequest = lambda *args: False
        action.ActionCondition = lambda *args: True
        run(actions, 'OnFinishProgressServer', action, env, data)
        self.assertEqual(2, len(messages))
        condition = actions.split('override bool ActionCondition')[1].split('override void')[0]
        self.assertNotIn('Print(', condition)
        self.assertNotIn('MessageStatus(', condition)

    def test_camp_lifecycle_drives_claims_before_gate_and_flushes_before_stop(self):
        source = adapted((WORLD / 'Camps/HCCampModule.c').read_text())
        events, logs = [], []
        data = NS(Camps=EArray())
        state = NS(m_Running=False, m_AdmissionPrinted=True, m_LastUtc=0, m_LastSaved=0,
                   m_Elapsed=0, s_Instance=None, m_Players=EArray(),
                   IsEnabled=lambda settings: settings.EnableCamps)
        service = NS(HCStep=lambda delta: events.append(('step', delta)),
                     HCFail=lambda: events.append('fail'))
        def start(owner, loaded):
            self.assertTrue(owner.m_Running)
            self.assertIs(owner, owner.s_Instance)
            self.assertIs(data, loaded)
            events.append('start')
            return False  # claim refusal does not disable fire camps
        def stop():
            events.append(('stop', state.m_Running))
        # Explicit synthetic collaborator for this HCCampModule translator.
        claims = NS(HCStart=start, HCGet=lambda: service, HCStop=stop,
                    HCObservedStatus=lambda: 'synthetic-observed-status')
        env = dict(HCBuildingClaim=claims, Print=logs.append, Math=NS(Min=min),
                   GetGame=lambda: NS(IsServer=lambda: True), HCWorldClock=NS(UTC=lambda: 1000),
                   HCCampStore=NS(Load=lambda now: data), HCV2Admission=NS(Line=lambda *args: ''),
                   HCV2Gates=NS(Qualified=lambda gate: False))
        # ToString is a native scalar operation, not policy.
        source = source.replace('m_Data.Camps.Count().ToString()', 'str(m_Data.Camps.Count())')
        state.Fail = lambda: run(source, 'Fail', state, env)
        for enabled in (False, True):
            events.clear()
            state.m_Running = False
            run(source, 'OnStart', state, env, NS(EnableCamps=True, EnableGroups=enabled))
            self.assertEqual(['start'] if enabled else [], events)
            self.assertTrue(state.m_Running)
        self.assertTrue(any('claims_start_refused' in log for log in logs))
        self.assertTrue(any('mailbox=off' in log for log in logs))
        events.clear()
        run(source, 'OnTick', state, env, 1)
        self.assertEqual([('step', 1)], events)
        self.assertEqual('synthetic-observed-status', run(source, 'HCGetOperationalStatus', state, env))
        run(source, 'Fail', state, env)
        self.assertEqual('fail', events[-1])
        state.m_Running = True
        state.Commit = lambda now: events.append('commit')
        run(source, 'OnStop', state, env)
        self.assertEqual([('stop', True), 'commit'], events[-2:])
        run(source, 'OnStop', state, env)
        self.assertEqual(('stop', False), events[-1])

    def test_native_construction_recipes_unregistered_on_every_peer(self):
        source = (WORLD / 'Crafting/HCRecipeRegistration.c').read_text()
        self.assertNotRegex(source, r'#if|IsServer\(')
        events = []
        recipes = re.findall(r'RegisterRecipe\(new (\w+)\)', source)
        env = dict(super=NS(RegisterRecipies=lambda: events.append('native')),
                   UnregisterRecipe=lambda name: events.append(name), RegisterRecipe=lambda recipe: None)
        env.update({name: lambda: object() for name in recipes})
        run(source, 'RegisterRecipies', NS(), env)
        self.assertEqual(['native', 'CraftFenceKit', 'CraftWatchtowerKit',
                          'CraftTerritoryFlagKit', 'CraftShelterKit'], events)
