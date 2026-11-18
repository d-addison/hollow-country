"""Execute authored interior/economy integration with explicit synthetic ports.

These are transaction/admission regressions, not Enforce, native I/O, geometry,
CE provenance, rendering, or multiplayer acceptance.
"""
import copy
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.test_group_server import EArray, body, execute_member
from tests.unit import test_search_economy as economy_tests
from tests.unit.build_identity_support import translate as build_identity


SOURCE = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c'


class NativeRef(N):
    # Native aliases for the shared helper, outside the integration translator.
    @property
    def m_Player(self): return self.player_arg
    @property
    def m_Target(self): return self.target_arg
    m_MainItem = None

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other


STORE_SOURCE = SOURCE.with_name('HCInteriorStore.c')


def invoke(name, env, instance, *args, path=None):
    source = (path or SOURCE).read_text()
    match = re.search(r'\b(?:static )?\w+ '+name+r'\(([^)]*)\)\s*\{', source)
    if not match:
        raise AssertionError('missing authored integration method: '+name)
    text = body(source, match.end())
    # Execute the normal-build branch. Diagnostic proofs are not enabled here;
    # startup tests supply explicit synthetic proof/API ports below.
    text = re.sub(r'#ifdef DIAG_DEVELOPER\s*.*?#endif', '', text, flags=re.S)
    # HCInteriorStore: native JSON out-parameters become walrus assignments from synthetic ports.
    text = re.sub(r'HCInteriorJson<\w+>\.Load\((m_Root \+ "[^"]*"|path), (\w+)\)',
                  r'((\2 := load_json(\1)) is not null)', text)
    text = re.sub(r'HCInteriorJson<\w+>\.WriteNew\(', 'write_new(', text)
    text = re.sub(r'JsonFileLoader<\w+>\.MakeData\((\w+), (\w+), error\)',
                  r'((\2 := serialize(\1)) is not null)', text)
    text = re.sub(r'\bs_Instance\b', 'self.s_Instance', text)
    text = re.sub(r'\bthis\b', 'self', text)
    # Member prefixes on ActionData are native fields, not this module's state.
    text = text.replace('.m_Player', '.player_arg').replace('.m_Target', '.target_arg')
    text = re.sub(r'HCInteriorActionData.Cast\(([^)]+)\)', r'\1', text)
    text = text.replace('HCInteriorJson<HCInteriorManifest>.Load(', 'load_manifest(')
    text = text.replace('HCInteriorJson<HCInteriorConfig>.Load("$profile:HollowCountry/interiors.json", m_Config)',
                        'load_config()')
    text = text.replace('load_manifest(root + "/manifest.json", previous)',
                        '((previous := load_manifest(root + "/manifest.json")) != null)')
    text = re.sub(r'\b(?:HCSettings|HCInterior\w+|HCSearch\w+|PlayerBase|ActionData|InventoryLocation|EntityAI|ItemBase) (?=\w+\s*=)', '', text)
    text = re.sub(r'\b(?:HCInterior\w+|HCSearch\w+) (\w+);', r'\1 = null;', text)
    for method in ('SearchGate', 'FindSite', 'ValidateTarget', 'CanStart', 'CanContinue',
                   'Reject', 'SearchBindingValid', 'SearchSession', 'SessionValid',
                   'PreserveLegacyManifest', 'RestoreLayoutManifest', 'SetSession',
                   'IsEnabled', 'ValidateConfig', 'AllocateManifest', 'PlaceCandidate',
                   'ResolveBuilding', 'InspectProp', 'Fail', 'OpenJournal', 'ReconcileAll'):
        text = re.sub(r'(?<![\w.])'+method+r'\(', 'self.'+method+'(', text)
    # PlaceCandidate-only syntax: untyped locals, managed arrays, and the native
    # `out Object reusable` parameter (the synthetic port returns (decision, object)).
    text = re.sub(r'array<\w+> (\w+) = new array<\w+>;', r'\1 = EArray();', text)
    text = re.sub(r'\bObject (\w+);', r'\1 = null;', text)
    text = re.sub(r'\bObject (?=\w+\s*=)', '', text)
    text = re.sub(r'if \(self\.InspectProp\((.+), reusable\) == 3\)',
                  r'inspected = self.InspectProp(\1); reusable = inspected[1]; if (inspected[0] == 3)', text)
    text = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', text)
    text = re.sub(r'while \(([^\n]+)\)', r'while \1:', text)
    return execute_member('bool '+name+'('+match[1]+') {'+text+'}', name, env, instance, *args)


class SearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.server = True
        self.events = []
        self.settings = N(EnableInteriors=True, EnableSearch=True)
        self.actor = N(IsAlive=lambda:True, IsUnconscious=lambda:False,
                       GetIdentity=lambda:N(GetId=lambda:'actor', GetPlayer=lambda:self.actor),
                       MessageStatus=lambda msg:self.events.append(('message', msg)))
        self.site = N(Id='instance_storage_v1', SlotId=0, Item='SyntheticFood', Phase=0,
                      Owner=None, StartedAt=90.0, Deadline=105.0, Target=N(GetType=lambda:'SyntheticStorage'))
        self.target = N(GetObject=lambda:self.site.Target)
        self.data = NativeRef(player_arg=self.actor, target_arg=self.target, Site=self.site)
        self.site.Owner = self.data
        self.lease = N(Site=self.site, Owner=self.data, Actor=self.actor, ActorId='actor')
        self.assignment = N(SlotId=0, InstanceId='instance', LayoutId='pantry', History='family',
                            MeasuredRecordSha256='b'*64, Item='')
        self.layout = N(SchemaVersion=1, CatalogVersion=1, MapName='synthetic_world',
                        Build='1.30.164289', Epoch=1, Seed=42, Assignments=EArray([self.assignment]))
        self.manifest = N(Version=1, Epoch=1, WorldName='synthetic_world', Build='1.30.164289.70',
                          SourcePin='a'*64, Entries=EArray([N(SiteId=self.site.Id,
                          SupplyId='1_2_3_4', ItemClass='SyntheticFood')]))
        self.context = N(InstanceId='instance', LayoutId='pantry', History='family', Room='kitchen',
                         GroupId='food_group', SourcePin='a'*64, EvidencePin='c'*64,
                         MeasuredRecordSha256='b'*64, Items=EArray(['SyntheticFood', 'SyntheticTool']))
        self.source = N(ReadyFor=lambda manifest:True)
        self.phase = 2
        self.economy = N(CanGrant=lambda site,actor:True, Grant=self.grant,
                         Open=lambda m,s,f:True, SetEnabled=lambda b:None,
                         Stop=lambda:self.events.append('economy_stop'))
        self.t = N(m_Ready=True, m_SearchProof=True, m_Config=N(MapName='synthetic_world',
                   Build='1.30.164289', Epoch=1), m_Manifest=self.layout,
                   m_Store=N(Healthy=lambda:True), m_Economy=self.economy,
                   m_Sites=EArray([self.site]), m_SearchSessions=EArray([self.lease]),
                   m_SearchBound=False, m_Objects=EArray([]), s_Instance=None)
        self.env = {'HCBuildIdentity':build_identity(),
                    'GetGame':lambda:N(IsServer=lambda:self.server, GetTickTime=lambda:self.now),
                    'HCServer':N(Get=lambda:N(GetSettings=lambda:self.settings)),
                    'HCInteriorRules':N(MaySearch=lambda *a:all(a)),
                    'HCInteriorCatalog':N(ItemAllowed=lambda s:s in ('','Rag','Battery9V')),
                    'HCSearchRules':N(ManifestValid=lambda m:bool(m and m.Entries),
                        TextValid=lambda s,n:bool(s) and len(s)<=n,
                        PinValid=lambda s:isinstance(s,str) and bool(re.fullmatch('[0-9a-f]{64}',s))),
                    'HCInteriorMeasuredCatalog':N(MeasuredBuildMatches=lambda actual,base:actual==base or actual.startswith(base+'.'),
                        MeasuredClear=lambda:self.events.append('measured_clear')),
                    'HCSearchEconomy':lambda:self.economy,
                    'HCInteriorSearchSession':lambda:N(), 'Print':self.events.append,
                    'HCSearchBinding':N(PlacementComplete=lambda *args:None),
                    's_Instance':None}
        from tests.unit.test_refusal_report import install_refusal
        install_refusal(self.env)
        for name in ('SearchGate','CanStart','CanContinue','SearchSession','SessionValid',
                     'SearchBindingValid','PreserveLegacyManifest','SetSession'):
            setattr(self.t,name,lambda *a,n=name:self.call(n,*a))
        self.t.FindSite=lambda target:self.site if target is self.site.Target else None
        self.t.ValidateTarget=lambda player,*a:player.IsAlive() and not player.IsUnconscious()
        self.t.Reject=lambda reason:self.events.append(reason) or False

    def call(self,name,*args):
        return invoke(name,self.env,self.t,*args)

    def grant(self,site,actor):
        self.events.append(('grant',site,actor))
        return self.phase

    def bind(self):
        self.t.m_Economy=None
        return self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False)

    def assert_refusal_window(self, callback, reason):
        for _ in range(3): callback()
        messages = [e for e in self.events if isinstance(e, tuple) and e[0] == 'message']
        lines = [e for e in self.events if isinstance(e, str) and e.startswith('refused reason=')]
        self.assertEqual(1, len(messages))
        self.assertEqual(['refused reason=' + reason + ' class=SyntheticStorage'], lines)
        self.now += 5
        callback()
        self.assertEqual(2, len([e for e in self.events if isinstance(e, tuple) and e[0] == 'message']))
        self.assertEqual(2, len([e for e in self.events if isinstance(e, str) and e.startswith('refused reason=')]))

    def test_pilot_start_refusals_use_shared_reason_windows(self):
        for reason in ('service', 'busy', 'no_site'):
            with self.subTest(reason=reason):
                self.setUp()
                self.site.Owner = None
                if reason == 'service': self.t.m_SearchProof = False
                if reason == 'busy': self.site.Owner = object()
                if reason == 'no_site': self.t.ValidateTarget = lambda *a: False
                self.assert_refusal_window(lambda:self.call('CanStart', self.actor, self.target), reason)

    def test_pilot_begin_session_capacity_is_reported_once(self):
        self.site.Owner = None
        self.t.SetSession = lambda *a: False  # Explicit synthetic full session table.
        self.assert_refusal_window(lambda:self.call('BeginSearch', self.data), 'capacity')

    def test_pilot_commit_refusals_pair_message_and_id_free_line(self):
        for reason in ('session_changed', 'too_early', 'supply_changed', 'storage_unavailable'):
            with self.subTest(reason=reason):
                self.setUp()
                if reason == 'session_changed': self.t.ValidateTarget = lambda *a: False
                if reason == 'supply_changed': self.phase = -4
                if reason == 'storage_unavailable': self.phase = 4
                def attempt():
                    # Explicit fresh synthetic attempts at the same failing boundary.
                    self.site.Phase = 0
                    if reason == 'too_early': self.site.StartedAt = self.now - 1
                    self.call('CommitSearch', self.data)
                self.assert_refusal_window(attempt, reason)

    def test_completed_search_calls_only_economy_once_and_depletes(self):
        self.call('CommitSearch',self.data)
        self.assertEqual(1,len([e for e in self.events if isinstance(e,tuple) and e[0]=='grant']))
        self.assertEqual(2,self.site.Phase)
        self.call('CommitSearch',self.data)
        self.assertEqual(1,len([e for e in self.events if isinstance(e,tuple) and e[0]=='grant']))

    def test_retained_or_uncertain_transfer_is_held_and_never_retried(self):
        for phase in (1,3,4,99):
            with self.subTest(phase=phase):
                self.setUp();self.phase=phase
                self.call('CommitSearch',self.data)
                self.assertEqual(3,self.site.Phase)
                self.call('CommitSearch',self.data)
                self.assertEqual(1,len([e for e in self.events if isinstance(e,tuple) and e[0]=='grant']))

    def test_reentrant_finish_cannot_grant_twice(self):
        def callback(site,actor):
            self.events.append('native_attempt')
            self.call('CommitSearch',self.data)
            return 2
        self.economy.Grant=callback
        self.call('CommitSearch',self.data)
        self.assertEqual(1,self.events.count('native_attempt'))

    def test_negative_pretransfer_refusal_does_not_deplete(self):
        self.phase=-4
        self.call('CommitSearch',self.data)
        self.assertEqual(0,self.site.Phase)
        self.assertFalse(any('Found' in str(e) for e in self.events))

    def test_missing_provider_and_legacy_held_states_fail_closed(self):
        for state in ('provider','store','proof','disabled','legacy_spent','legacy_hold'):
            with self.subTest(state=state):
                self.setUp()
                if state=='provider':self.t.m_Economy=None
                if state=='store':self.t.m_Store.Healthy=lambda:False
                if state=='proof':self.t.m_SearchProof=False
                if state=='disabled':self.settings.EnableSearch=False
                if state=='legacy_spent':self.site.Phase=2
                if state=='legacy_hold':self.site.Phase=3
                self.assertFalse(self.call('SearchGate',self.actor,self.site))

    def test_elapsed_los_ownership_deadline_and_session_still_enforced(self):
        for reason in ('too_early','los','owner','expired','rollback','identity','actor','dead',
                       'unconscious','identity_player','nan_time'):
            with self.subTest(reason=reason):
                self.setUp()
                if reason=='too_early':self.site.StartedAt=95.0
                if reason=='los':self.t.ValidateTarget=lambda *a:False
                if reason=='owner':self.site.Owner=object()
                if reason=='expired':self.now=106.0
                if reason=='rollback':self.now=89.0
                if reason=='identity':self.lease.ActorId='old_session'
                if reason=='actor':self.lease.Actor=object()
                if reason=='dead':self.actor.IsAlive=lambda:False
                if reason=='unconscious':self.actor.IsUnconscious=lambda:True
                if reason=='identity_player':self.actor.GetIdentity=lambda:N(GetId=lambda:'actor',GetPlayer=lambda:None)
                if reason=='nan_time':self.now=float('nan')
                self.call('CommitSearch',self.data)
                self.assertFalse(any(isinstance(e,tuple) and e[0]=='grant' for e in self.events))

    def test_identity_change_during_final_target_validation_cannot_grant(self):
        def changed(*args):
            self.actor.GetIdentity=lambda:N(GetId=lambda:'changed',GetPlayer=lambda:self.actor)
            return True
        self.t.ValidateTarget=changed
        self.call('CommitSearch',self.data)
        self.assertFalse(any(isinstance(e,tuple) and e[0]=='grant' for e in self.events))

    def test_disable_during_final_target_validation_cannot_grant(self):
        def changed(*args):
            self.settings.EnableSearch=False
            return True
        self.t.ValidateTarget=changed
        self.call('CommitSearch',self.data)
        self.assertFalse(any(isinstance(e,tuple) and e[0]=='grant' for e in self.events))

    def test_begin_and_end_bind_release_only_the_owning_session(self):
        self.site.Owner=None;self.data.Site=None;self.t.m_SearchSessions.Clear()
        self.call('BeginSearch',self.data)
        self.assertIs(self.data,self.site.Owner)
        self.assertIs(self.site,self.data.Site)
        self.assertEqual(115.0,self.site.Deadline)
        self.assertTrue(self.call('SessionValid',self.data,self.site))
        stranger=NativeRef(player_arg=self.actor,target_arg=self.target,Site=self.site)
        self.call('EndSearch',stranger)
        self.assertIs(self.data,self.site.Owner)
        self.assertTrue(self.call('SessionValid',self.data,self.site))
        self.call('EndSearch',self.data)
        self.assertIsNone(self.site.Owner)
        self.assertIsNone(self.data.Site)
        self.assertFalse(self.call('SessionValid',self.data,self.site))

    def test_session_storage_is_bounded_and_reuses_same_site_after_cancel(self):
        for _ in range(30):
            self.assertTrue(self.call('SetSession',self.data,self.site))
        self.assertEqual(1,len(self.t.m_SearchSessions))
        self.t.m_SearchSessions=EArray([N(Site=object()) for _ in range(12)])
        self.assertFalse(self.call('SetSession',self.data,self.site))
        self.assertEqual(12,len(self.t.m_SearchSessions))

    def test_stop_disables_adapter_before_clearing_sessions_and_sites(self):
        self.call('OnStop')
        self.assertFalse(self.t.m_Ready)
        self.assertEqual('economy_stop',self.events[0])
        self.assertEqual([],self.t.m_SearchSessions)
        self.assertEqual([],self.t.m_Sites)
        self.assertIsNone(self.site.Owner)
        self.assertFalse(self.call('SearchGate',self.actor,self.site))

    def test_bound_manifest_accepts_explicit_context_group_class_not_pilot_allowlist(self):
        self.assertTrue(self.bind())
        self.assertIs(self.economy,self.t.m_Economy)
        self.assertTrue(self.t.m_SearchBound)

    def test_context_or_source_drift_and_unadmitted_classes_are_rejected_before_open(self):
        for field in ('InstanceId','LayoutId','History','Room','GroupId','SourcePin',
                      'EvidencePin','MeasuredRecordSha256','Items'):
            with self.subTest(field=field):
                self.setUp();setattr(self.context,field, EArray(['OtherClass']) if field=='Items' else '')
                self.assertFalse(self.bind())
                self.assertIsNone(self.t.m_Economy)

    def test_binding_rejects_missing_extra_reordered_sites_wrong_epoch_build_and_source(self):
        for reason in ('missing','extra','site','epoch','build','source'):
            with self.subTest(reason=reason):
                self.setUp()
                if reason=='missing':self.manifest.Entries.Clear()
                if reason=='extra':self.manifest.Entries.Insert(copy.deepcopy(self.manifest.Entries[0]))
                if reason=='site':self.manifest.Entries[0].SiteId='unknown_site'
                if reason=='epoch':self.manifest.Epoch=2
                if reason=='build':self.manifest.Build='wrong_build'
                if reason=='source':self.source.ReadyFor=lambda m:False
                self.assertFalse(self.bind())

    def test_binding_cannot_replace_existing_service_or_retry_failed_open(self):
        self.t.m_SearchBound=True
        self.assertFalse(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))
        self.setUp();self.economy.Open=lambda *a:False
        self.assertFalse(self.bind())
        self.assertTrue(self.t.m_SearchBound)
        self.assertIsNone(self.t.m_Economy)
        self.assertFalse(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))

    def startup_ports(self, failure=None):
        """Synthetic native/config/placement ports; authored OnStart decides readiness."""
        self.t.m_Config.Candidates=EArray([])
        self.t.IsEnabled=lambda settings:settings.EnableInteriors
        self.t.ValidateConfig=lambda settings:failure!='config'
        self.t.AllocateManifest=lambda:self.layout
        self.t.RestoreLayoutManifest=lambda:failure!='restore'
        self.env['load_config']=lambda:True
        self.env['FileExist']=lambda path:True
        # OnStart asks the Admitted() forms (Accepted OR a local-acceptance marker); stub both.
        self.env['HCInteriorRules'].PlacementAccepted=lambda:failure!='placement'
        self.env['HCInteriorRules'].SearchAccepted=lambda:False
        self.env['HCInteriorRules'].PlacementAdmitted=lambda:failure!='placement'
        self.env['HCInteriorRules'].SearchAdmitted=lambda:False
        self.env['HCInteriorMeasuredCatalog'].MeasuredEnsureLoaded=lambda:None
        self.env['HCInteriorStore']=lambda:N(Open=lambda *args:failure!='store',Healthy=lambda:True)

    def test_successful_binding_clean_stop_actual_start_allows_one_fresh_bind(self):
        self.assertTrue(self.bind())
        self.call('OnStop')
        self.assertFalse(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))
        self.startup_ports()
        self.call('OnStart',self.settings)
        self.assertTrue(self.t.m_Ready)
        fresh_source=N(ReadyFor=lambda manifest:True)
        opens=[]
        fresh=N(Open=lambda *args:opens.append(args) or True)
        self.env['HCSearchEconomy']=lambda:fresh
        self.assertTrue(self.call('BindSearchEconomy',fresh_source,self.manifest,EArray([self.context]),False))
        self.assertIs(fresh,self.t.m_Economy)
        self.assertEqual([(self.manifest,fresh_source,False)],opens)
        self.assertFalse(self.call('BindSearchEconomy',fresh_source,self.manifest,EArray([self.context]),False))
        self.assertEqual(1,len(opens))

    def test_failed_open_stays_sticky_across_repeated_stop_and_actual_start(self):
        self.economy.Open=lambda *args:False
        self.assertFalse(self.bind())
        self.call('OnStop');self.call('OnStop')
        self.startup_ports();self.call('OnStart',self.settings)
        self.assertTrue(self.t.m_Ready)
        self.assertTrue(self.t.m_SearchBound)
        self.env['HCSearchEconomy']=lambda:self.fail('failed Open must not be retried')
        self.assertFalse(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))

    def test_clean_stop_with_failed_restart_cannot_rebind(self):
        for failure in ('config','restore','store','placement','disabled','server'):
            with self.subTest(failure=failure):
                self.setUp();self.assertTrue(self.bind());self.call('OnStop')
                self.startup_ports(failure)
                if failure=='disabled':self.settings.EnableInteriors=False
                if failure=='server':self.server=False
                self.call('OnStart',self.settings)
                self.assertFalse(self.t.m_Ready)
                self.assertFalse(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))

    def test_restarted_service_revalidates_fresh_source_and_context_before_open(self):
        self.assertTrue(self.bind());self.call('OnStop')
        self.startup_ports();self.call('OnStart',self.settings)
        fresh=N(ReadyFor=lambda manifest:False)
        opens=[]
        self.env['HCSearchEconomy']=lambda:N(Open=lambda *args:opens.append(args) or True)
        self.assertFalse(self.call('BindSearchEconomy',fresh,self.manifest,EArray([self.context]),False))
        fresh.ReadyFor=lambda manifest:True
        self.context.Items=EArray(['UnadmittedClass'])
        self.assertFalse(self.call('BindSearchEconomy',fresh,self.manifest,EArray([self.context]),False))
        self.assertEqual([],opens)
        self.context.Items=EArray(['SyntheticFood'])
        self.assertTrue(self.call('BindSearchEconomy',fresh,self.manifest,EArray([self.context]),False))
        self.assertEqual(1,len(opens))

    def test_aborted_stop_cannot_release_binding_until_cleanup_completes(self):
        for stage in ('economy','decoration'):
            with self.subTest(stage=stage):
                self.setUp();self.assertTrue(self.bind())
                def aborted(*args):
                    raise RuntimeError('synthetic callback abort; no Enforce catch claimed')
                game=self.env['GetGame']()
                game.ObjectDelete=lambda obj:None
                self.env['GetGame']=lambda:game
                if stage=='economy':self.economy.Stop=aborted
                if stage=='decoration':
                    self.t.m_Objects.Insert(object());game.ObjectDelete=aborted
                with self.assertRaises(RuntimeError):self.call('OnStop')
                self.assertTrue(self.t.m_SearchBound)
                self.assertIs(self.economy,self.t.m_Economy)
                self.assertFalse(self.t.m_Ready)
                self.economy.Stop=lambda:None;game.ObjectDelete=lambda obj:None
                self.call('OnStop')
                self.startup_ports();self.call('OnStart',self.settings)
                self.env['HCSearchEconomy']=lambda:N(Open=lambda *args:True)
                self.assertTrue(self.call('BindSearchEconomy',self.source,self.manifest,EArray([self.context]),False))

    def test_recovered_legacy_items_are_preserved_but_not_newly_allocated(self):
        old=copy.deepcopy(self.layout);old.Assignments[0].Item='Rag'
        self.assertTrue(self.call('PreserveLegacyManifest',self.layout,old))
        self.assertEqual('Rag',self.assignment.Item)

    def test_legacy_layout_identity_changes_do_not_rewind_depletion(self):
        for field in ('InstanceId','SlotId','LayoutId','History','MeasuredRecordSha256'):
            with self.subTest(field=field):
                self.setUp();old=copy.deepcopy(self.layout)
                setattr(old.Assignments[0],field,-1 if field=='SlotId' else 'changed')
                self.assertFalse(self.call('PreserveLegacyManifest',self.layout,old))

    def test_legacy_header_changes_missing_and_oversized_manifests_are_rejected(self):
        for field in ('SchemaVersion','CatalogVersion','MapName','Build','Epoch','Seed','Assignments'):
            with self.subTest(field=field):
                self.setUp();old=copy.deepcopy(self.layout)
                setattr(old,field,None if field=='Assignments' else 'changed')
                self.assertFalse(self.call('PreserveLegacyManifest',self.layout,old))
        self.assertFalse(self.call('PreserveLegacyManifest',self.layout,None))

    def test_layout_state_never_recreates_existing_missing_corrupt_or_changed_manifest(self):
        self.env['FileExist']=lambda path:True
        self.env['load_manifest']=lambda path:None
        self.assertFalse(self.call('RestoreLayoutManifest'))
        old=copy.deepcopy(self.layout);old.Assignments[0].History='changed'
        self.env['load_manifest']=lambda path:old
        self.assertFalse(self.call('RestoreLayoutManifest'))
        old=copy.deepcopy(self.layout);old.Assignments[0].Item='Battery9V'
        self.env['load_manifest']=lambda path:old
        self.assertTrue(self.call('RestoreLayoutManifest'))
        self.assertEqual('Battery9V',self.assignment.Item)
        self.env['FileExist']=lambda path:False
        self.env['load_manifest']=lambda path:self.fail('fresh root must not read/fallback')
        self.assertTrue(self.call('RestoreLayoutManifest'))

    def test_context_bounds_empty_opportunities_and_caller_mutation_after_bind(self):
        self.context.Items=EArray(['SyntheticFood']*4097)
        self.assertFalse(self.bind())
        self.setUp();self.manifest.Entries[0].ItemClass='';self.manifest.Entries[0].SupplyId=''
        self.assertTrue(self.bind())
        # Binding does not retain mutable caller context arrays.
        self.context.Items.Clear()
        self.assertFalse(hasattr(self.t,'m_Contexts'))

    def test_recovered_adapter_depletion_and_capacity_refusal_veto_start(self):
        self.economy.CanGrant=lambda *a:False
        self.site.Owner=None
        self.assertFalse(self.call('CanStart',self.actor,self.target))
        self.assertFalse(self.call('SearchGate',self.actor,self.site))

    def authored_economy(self):
        fixture=economy_tests.SearchEconomyTests()
        fixture.setUp()
        fixture.m.Entries[0].SiteId=self.site.Id
        self.t.m_Economy=N(CanGrant=lambda *args:fixture.call('CanGrant',*args),
                           Grant=lambda *args:fixture.call('Grant',*args))
        return fixture

    def test_action_routes_through_authored_claim_attempt_transfer_result_and_replay_veto(self):
        fixture=self.authored_economy()
        self.call('CommitSearch',self.data)
        self.assertEqual(['claim','attempt','native_move','result'],fixture.events)
        self.assertEqual(2,self.site.Phase)
        # Even if the local phase were reset, the adapter's recovered terminal
        # state vetoes this action; legacy state cannot manufacture availability.
        self.site.Phase=0
        self.call('CommitSearch',self.data)
        self.assertEqual(1,fixture.events.count('native_move'))

    def test_action_empty_allocation_never_reaches_native_and_is_finite(self):
        fixture=self.authored_economy()
        fixture.m.Entries[0].SupplyId='';fixture.m.Entries[0].ItemClass=''
        self.call('CommitSearch',self.data)
        self.assertEqual(['claim','attempt','result'],fixture.events)
        self.assertEqual(2,self.site.Phase)

    def test_action_result_write_failure_is_held_with_no_compensating_or_second_transfer(self):
        fixture=self.authored_economy();fixture.failed='result'
        self.call('CommitSearch',self.data)
        self.assertEqual(3,self.site.Phase)
        self.assertFalse(fixture.t.m_Ready)
        self.call('CommitSearch',self.data)
        self.assertEqual(1,fixture.events.count('native_move'))

    def test_no_reward_creation_or_pilot_allocation_remains_in_module(self):
        source=SOURCE.read_text()
        for forbidden in ('CreateInInventory','FindFirstFreeLocationForNewEntity',
                          'm_Store.Reserve(', 'm_Store.BeginGrant(', 'm_Store.Finish(',
                          'HCInteriorRules.Allocation(', 'MeasuredAllocation('):
            self.assertFalse(forbidden in source, forbidden)


class PlacementPathgraphTests(unittest.TestCase):
    """Executes the authored PlaceCandidate with explicit synthetic native ports.

    Proves only when HCInteriorPathgraph.Schedule is reached and with which props;
    pathgraph rebuild behaviour inside DayZ is not established here.
    """
    class Prop(N):
        def __hash__(self):
            return id(self)

    def setUp(self):
        self.events = []
        self.scheduled = []
        self.created = []
        self.deleted = []
        self.fail_create_at = None
        self.building = N(GetOrientation=lambda:[10.0, 0.0, 0.0], ModelToWorld=lambda p:('world',)+tuple(p))
        self.props = [N(Type='Synthetic_%d' % i, Position=[float(i), 0.0, 0.0], Orientation=[0.0, 0.0, 0.0],
                        Searchable=i == 0, SearchPoint=[0.0, 1.0, 0.0]) for i in range(3)]
        self.layout = N(Id='pantry', History='family', Props=EArray(self.props))
        self.candidates = EArray([N(SlotId=7, Position=[1.0, 2.0, 3.0], Orientation=[0.0, 0.0, 0.0])])
        self.assignment = N(SlotId=7, InstanceId='instance', LayoutId='pantry', History='family',
                            MeasuredRecordSha256='b'*64, Item='')
        self.held = {}
        self.store = N(Healthy=lambda:True, IsHeld=lambda slot:slot in self.held,
                       HoldSlot=lambda slot, reason:self.held.setdefault(slot, reason),
                       RecoverSite=lambda site:0)
        self.t = N(m_Store=self.store, m_Config=N(Candidates=self.candidates, Seed=42, DiagnosticPlacementTrial=False),
                   m_Manifest=N(Assignments=EArray([self.assignment])), m_Objects=EArray([]), m_Sites=EArray([]))
        self.resolved = self.building
        self.t.ResolveBuilding = lambda candidate:self.resolved
        self.t.InspectProp = self.inspect
        self.t.FindSite = lambda target:None
        self.decision = {}
        self.game = N(CreateObjectEx=self.create_object, ObjectDelete=self.deleted.append)
        self.env = {'GetGame':lambda:self.game, 'Print':self.events.append, 'EArray':EArray,
                    'ECE_SETUP':1, 'ECE_KEEPHEIGHT':2, 'ECE_CREATEPHYSICS':4, 'ECE_UPDATEPATHGRAPH':8,
                    'ECE_NOLIFETIME':16, 'ECE_DYNAMIC_PERSISTENCY':32,
                    # Installed 1.30.164289: 3_Game/CE/CentralEconomy.c:31.
                    'ECE_NOPERSISTENCY_WORLD':8388608, 'RF_IGNORE':0,
                    'HCInteriorSite':lambda:N(), 'HCInteriorPathgraph':N(Schedule=self.schedule),
                    'HCInteriorRules':N(Layout=lambda *a:0, Quantize=lambda v:v, Yaw=lambda v:v),
                    'HCInteriorCatalog':N(GetFor=lambda choice, candidate, trial:self.layout),
                    'HCInteriorMeasuredCatalog':N(MeasuredDigest=lambda candidate:'b'*64)}

    def schedule(self, objects):
        self.events.append('schedule')
        self.scheduled.append(list(objects))
        return len(objects)

    def create_object(self, type_name, position, flags, ratio):
        if self.fail_create_at is not None and len(self.created) == self.fail_create_at:
            return None
        self.assertEqual(flags & 8, 8)  # authored creation keeps the vanilla pathgraph flag too
        self.assertEqual(flags & 8388608, 8388608)  # furnishings never persist as world loot
        created = NativeRef(Type=type_name, SetOrientation=lambda o:None, ModelToWorld=lambda p:p)
        self.created.append(created)
        return created

    def inspect(self, point, orientation, type_name, *rest):
        # (decision, object): an HC-owned prop already standing at that slot is reusable.
        for owned in self.t.m_Objects:
            if owned.Type == type_name:
                return (1, owned)
        return (self.decision.get(type_name, 0), None)

    def place(self):
        invoke('PlaceCandidate', self.env, self.t, 0)

    def flatten(self):
        return [prop for batch in self.scheduled for prop in batch]

    def test_fully_created_layout_schedules_exactly_those_props_once_after_bookkeeping(self):
        self.place()
        self.assertEqual(3, len(self.created))
        self.assertEqual([self.created], self.scheduled)
        self.assertEqual(self.created, list(self.t.m_Objects))
        self.assertEqual([], self.deleted)

    def test_refused_or_rolled_back_placements_never_schedule(self):
        # partial creation failure rolls back and must not touch the pathgraph
        self.fail_create_at = 1
        self.place()
        self.assertEqual([], self.scheduled)
        self.assertEqual(self.created, self.deleted)
        self.assertEqual('partial-placement', self.held[7])
        self.assertEqual([], list(self.t.m_Objects))

    def test_other_refusals_never_schedule(self):
        for name in ('unhealthy', 'held', 'unresolved', 'binding', 'foreign'):
            with self.subTest(refusal=name):
                self.setUp()
                if name == 'unhealthy': self.store.Healthy = lambda:False
                if name == 'held': self.held[7] = 'earlier'
                if name == 'unresolved': self.resolved = None
                if name == 'binding': self.assignment.LayoutId = 'other'
                if name == 'foreign': self.decision['Synthetic_1'] = 3
                self.place()
                self.assertEqual([], self.scheduled)
                self.assertEqual([], self.created)

    def test_reused_props_are_not_scheduled_and_nothing_is_scheduled_twice(self):
        self.place()
        first = list(self.created)
        self.assertEqual([first], self.scheduled)
        # Re-running the same slot reuses every owned prop: no creation, no second schedule of any prop.
        self.place()
        self.assertEqual(first, self.created)
        for prop in first:
            self.assertEqual(1, self.flatten().count(prop))
        # Mixed: one prop vanished from ownership, so only the new replacement is scheduled.
        removed = self.t.m_Objects[1]
        self.t.m_Objects.Remove(1)
        before = len(self.created)
        self.place()
        self.assertEqual(before + 1, len(self.created))
        self.assertEqual([self.created[-1]], self.scheduled[-1])
        self.assertNotIn(removed, self.scheduled[-1])
        self.assertEqual(1, self.flatten().count(self.created[-1]))

    def test_each_call_schedules_a_fresh_array_never_prior_state(self):
        self.place()
        self.t.m_Objects.Clear()
        self.place()
        self.assertEqual(2, len(self.scheduled))
        self.assertEqual(3, len(self.scheduled[1]))
        self.assertFalse(set(map(id, self.scheduled[0])) & set(map(id, self.scheduled[1])))
        self.assertIsNot(self.scheduled[0], self.scheduled[1])


ALIAS_NATIVE = '1.30.164289.70'
ALIAS_PINNED = '1.30.164289'


def plain(value):
    """Order-stable serialization of synthetic namespaces: the exact-comparison port."""
    if isinstance(value, N):
        return {k: plain(v) for k, v in sorted(vars(value).items()) if not callable(v)}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


class BuildAliasRecoveryTests(unittest.TestCase):
    """Executes authored interior recovery with the real HCBuildIdentity statics.

    Alias-only build spelling changes must keep the layouts, epoch and seed;
    this is offline logic, not DayZ evidence.
    """
    def manifest(self, build):
        assignment = N(SlotId=0, InstanceId='instance', LayoutId='pantry', History='family',
                       MeasuredRecordSha256='b'*64, Item='')
        return N(SchemaVersion=1, CatalogVersion=1, MapName='chernarusplus', Build=build, Epoch=1, Seed=42,
                 Assignments=EArray([assignment]))

    def setUp(self):
        self.events = []
        self.env = {'HCBuildIdentity': build_identity(), 'Print': self.events.append, 'EArray': EArray,
                    'HCInteriorManifest': lambda:N(Assignments=EArray()),
                    'HCInteriorAssignment': lambda:N(),
                    'GetGame': lambda:N(ConfigIsExisting=lambda path:True),
                    'HCInteriorCatalog': N(VERSION=1, GetFor=lambda *a:N(Id='pantry', History='family', Props=EArray([N(Type='Prop')]))),
                    'HCInteriorRules': N(Layout=lambda *a:0, Quantize=lambda v:v, Yaw=lambda v:v),
                    'HCInteriorMeasuredCatalog': N(MeasuredDigest=lambda candidate:'b'*64, MeasuredRequested=lambda:False)}
        candidate = N(SlotId=0, Position=[1.0, 2.0, 3.0], Orientation=[0.0, 0.0, 0.0], Id=lambda epoch:'instance')
        self.module = N(m_Config=N(MapName='chernarusplus', Build=ALIAS_NATIVE, Epoch=1, Seed=42,
                                   DiagnosticPlacementTrial=False, Candidates=EArray([candidate])),
                        m_PropLimit=24)
        self.module.Reject = lambda reason:self.events.append(reason) or False

    def preserve(self, expected, actual):
        return invoke('PreserveLegacyManifest', self.env, self.module, expected, actual)

    def test_alias_only_build_change_keeps_the_legacy_layouts_in_both_directions(self):
        for current, stored in ((ALIAS_PINNED, ALIAS_NATIVE), (ALIAS_NATIVE, ALIAS_PINNED),
                                (ALIAS_PINNED, ALIAS_PINNED), (ALIAS_NATIVE, ALIAS_NATIVE)):
            with self.subTest(current=current, stored=stored):
                old = self.manifest(stored)
                old.Assignments[0].Item = 'Rag'
                expected = self.manifest(current)
                self.assertTrue(self.preserve(expected, old))
                self.assertEqual('Rag', expected.Assignments[0].Item)
                self.assertEqual(stored, old.Build)  # the stored image is never rewritten

    def test_non_alias_build_changes_and_blank_builds_still_refuse(self):
        for current, stored in ((ALIAS_PINNED, '1.30.164290'), (ALIAS_NATIVE, '1.30.1642890'),
                                (ALIAS_PINNED, ALIAS_NATIVE + ' '), (ALIAS_PINNED, ''), ('', '')):
            with self.subTest(current=current, stored=stored):
                self.assertFalse(self.preserve(self.manifest(current), self.manifest(stored)))

    def test_allocated_manifest_always_stamps_the_canonical_build_spelling(self):
        for configured in (ALIAS_NATIVE, ALIAS_PINNED):
            with self.subTest(configured=configured):
                self.module.m_Config.Build = configured
                manifest = invoke('AllocateManifest', self.env, self.module)
                self.assertEqual(self.env['HCBuildIdentity'].Canonical(), manifest.Build)
                self.assertEqual(ALIAS_PINNED, manifest.Build)
                self.assertEqual((1, 'chernarusplus', 1, 42), (manifest.SchemaVersion, manifest.MapName,
                                                                manifest.Epoch, manifest.Seed))


class StoreBuildAliasTests(unittest.TestCase):
    """HCInteriorStore.Open/OpenJournal exact serialization comparisons under build aliases."""
    def manifest(self, build, seed=42):
        assignment = N(SlotId=0, InstanceId='instance', LayoutId='pantry', History='family',
                       MeasuredRecordSha256='b'*64, Item='')
        return N(SchemaVersion=1, CatalogVersion=1, MapName='chernarusplus', Build=build, Epoch=1, Seed=seed,
                 Assignments=EArray([assignment]))

    def setUp(self):
        self.events = []
        self.disk = {}
        self.writes = []
        self.env = {'HCBuildIdentity': build_identity(), 'Print': self.events.append, 'EArray': EArray,
                    'HCInteriorSearchPool': lambda:N(Open=lambda manifest:True),
                    'HCInteriorJournalIdentity': lambda:N(),
                    'FileExist': lambda path:True,
                    'load_json': lambda path:copy.deepcopy(self.disk.get(path)),  # a load is a fresh in-memory copy
                    'write_new': lambda path, data:self.writes.append(path) or False,
                    'serialize': lambda value:repr(plain(value)),
                    'HCInteriorRules': N(MigrationAllowed=lambda *a:True, JournalVersionAccepted=lambda *a:True),
                    'HCInteriorJson': N()}
        self.store = N(m_Fault=False)
        self.store.Fail = lambda reason:self.events.append(reason) or False
        self.store.ReconcileAll = lambda:True
        self.store.OpenJournal = lambda *a:invoke('OpenJournal', self.env, self.store, *a, path=STORE_SOURCE)
        self.root = '$profile:HollowCountry/interiors_s1_e1'

    def config(self, build):
        return N(MapName='chernarusplus', Build=build, Epoch=1, Seed=42,
                 InitializeNewEpoch=False, MigrateLegacyJournal=False)

    def journal(self, manifest):
        return N(SchemaVersion=2, SourceSchema=1, Manifest=manifest)

    def open(self, config_build, expected, stored_manifest, stored_journal):
        self.disk[self.root + '/manifest.json'] = stored_manifest
        self.disk[self.root + '/journal-v2.json'] = stored_journal
        return invoke('Open', self.env, self.store, self.config(config_build), expected, path=STORE_SOURCE)

    def test_alias_only_spelling_differences_between_config_and_stored_images_open_cleanly(self):
        for config_build, stored in ((ALIAS_NATIVE, ALIAS_NATIVE), (ALIAS_NATIVE, ALIAS_PINNED),
                                     (ALIAS_PINNED, ALIAS_NATIVE), (ALIAS_PINNED, ALIAS_PINNED)):
            with self.subTest(config=config_build, stored=stored):
                self.setUp()
                stored_manifest = self.manifest(stored)
                stored_journal = self.journal(self.manifest(stored))
                expected = self.manifest(ALIAS_PINNED)  # AllocateManifest writes only the canonical spelling
                self.assertTrue(self.open(config_build, expected, stored_manifest, stored_journal), self.events)
                self.assertEqual([], self.events)
                self.assertEqual([], self.writes)                 # nothing is rewritten
                self.assertEqual(stored, stored_manifest.Build)   # stored images keep their spelling
                self.assertEqual(stored, stored_journal.Manifest.Build)
                self.assertEqual(ALIAS_PINNED, expected.Build)

    def test_real_manifest_and_journal_differences_still_fail_the_exact_comparison(self):
        expected = self.manifest(ALIAS_PINNED)
        self.assertFalse(self.open(ALIAS_NATIVE, expected, self.manifest(ALIAS_NATIVE, seed=43),
                                   self.journal(self.manifest(ALIAS_NATIVE))))
        self.assertIn('manifest changed; layout/identity changes require a separate reviewed migration', self.events[-1])
        self.setUp()
        self.assertFalse(self.open(ALIAS_NATIVE, self.manifest(ALIAS_PINNED), self.manifest(ALIAS_NATIVE),
                                   self.journal(self.manifest(ALIAS_NATIVE, seed=43))))
        self.assertIn('journal allocation binding changed', self.events[-1])
        self.setUp()
        self.assertFalse(self.open(ALIAS_NATIVE, self.manifest(ALIAS_PINNED), self.manifest('1.30.164290'),
                                   self.journal(self.manifest(ALIAS_NATIVE))))
        self.assertIn('manifest changed', self.events[-1])

    def test_config_build_that_is_not_an_admitted_alias_of_the_manifest_is_refused(self):
        self.assertFalse(self.open('1.30.164290', self.manifest(ALIAS_PINNED), self.manifest(ALIAS_PINNED),
                                   self.journal(self.manifest(ALIAS_PINNED))))
        self.assertIn('manifest/config world/build/epoch/seed mismatch', self.events[-1])


class FixupRefreshHistoryTests(unittest.TestCase):
    """T015/FR-006: bounded timer reclamation must retain pilot routing history."""

    def refresh(self):
        from tests.unit import test_search_economy_houses as houses
        source = (SOURCE.parents[1] / 'Loot/HCSearchRefresh.c').read_text()
        # Mechanical syntax adapters only; policy is the actual authored module.
        source = source.replace('bool onlyMissing = false', 'bool onlyMissing')
        source = source.replace('m_Pending--', 'm_Pending = m_Pending - 1')
        class RefreshSyntax(houses.Translator):
            def expr(self, text, names):
                code = super().expr(text, names).replace('self.s_Instance', '_refresh_state.s_Instance')
                return code.replace('self.m_Index.Find(self.Key(scope, siteId), index)',
                    '((_found := find_out(self.m_Index, self.Key(scope, siteId))) and '
                    '((index := _found[1]) is not None) and _found[0])')
        env = dict(HCModule=object, EArray=houses.EArray, HMap=houses.HMap,
                   find_out=houses.find_out, Print=lambda message: None,
                   HCGroupClock=N(Utc=lambda: 1000), _refresh_state=N(s_Instance=None),
                   HCSearchRules=N(TextValid=lambda value, cap: bool(value) and len(value) <= cap))
        for code in RefreshSyntax(source, only=('HCSearchRefreshRow', 'HCSearchRefreshState',
                                                'HCSearchRefreshModule')).classes():
            exec(code, env)
        api = env['HCSearchRefreshModule']
        obj = api()
        obj.m_Settings = N(EnableWorld=True)
        obj.m_State = env['HCSearchRefreshState']()
        obj.m_State.LastUtc = 1000
        self.saved = []
        obj.m_Store = N(Healthy=lambda: True, Save=lambda state: self.saved.append(copy.deepcopy(state)) or True)
        env['_refresh_state'].s_Instance = obj
        # A small synthetic cap exercises the actual cap branch without 4096 fixtures.
        obj.MAX_RECORDS = 1
        row = env['HCSearchRefreshRow']()
        row.Scope, row.SiteId = 'synthetic_scope', 'synthetic_pilot_site'
        row.SearchedUtc, row.Ready, row.Revisited = 100, True, True
        obj.m_State.Rows.Insert(row)
        obj.m_Index.Set(api.Key(row.Scope, row.SiteId), 0)
        return api, obj, row

    def test_forget_compacted_preserves_persistent_revisited_history(self):
        api, obj, row = self.refresh()
        api.ForgetCompacted(row.Scope, row.SiteId)
        self.assertTrue(api.Revisited(row.Scope, row.SiteId))
        self.assertIn(row, obj.m_State.Rows)
        self.assertTrue(row.Revisited)
        self.assertEqual(0, obj.m_Pending)
        obj.RemoveReadyTimer(row)  # The shared removal helper also protects routing history.
        self.assertIn(row, obj.m_State.Rows)
        obj.m_Store.Save(obj.m_State)
        self.assertTrue(self.saved[-1].Rows[0].Revisited)

    def test_full_timer_ledger_preserves_history_and_cap_instead_of_eviction(self):
        api, obj, row = self.refresh()
        self.assertFalse(obj.RecycleReadyTimer())
        obj.RecordSearch('synthetic_scope', 'synthetic_new_site', False)
        self.assertTrue(api.Revisited(row.Scope, row.SiteId))
        self.assertEqual([row], obj.m_State.Rows)
        self.assertLessEqual(obj.m_State.Rows.Count(), obj.MAX_RECORDS)
        self.assertIsNone(obj.FindRow('synthetic_scope', 'synthetic_new_site'))
        # A new cooldown on the same site preserves the route after timer readiness clears.
        obj.RecordSearch(row.Scope, row.SiteId, False)
        self.assertTrue(api.Revisited(row.Scope, row.SiteId))
        self.assertFalse(row.Ready)
        self.assertEqual(1, obj.m_Pending)
        self.assertTrue(self.saved[-1].Rows[0].Revisited)


if __name__ == '__main__':
    unittest.main()
