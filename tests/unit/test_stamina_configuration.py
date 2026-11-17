"""Authored methods with synthetic native adapters; no engine proof."""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.unit.test_group_server import execute_member
from tests.unit.test_crafting_completion import execute_flat

ROOT=Path(__file__).resolve().parents[2]/'mods/HollowCountry/scripts'
SOURCE=ROOT/'3_Game/Survival/HCStaminaConfiguration.c'
SETTINGS=ROOT/'3_Game/Survival/HCStaminaSettings.c'

class ConfigurationTests(unittest.TestCase):
    def settings(self,**kw):
        x=N(SchemaVersion=1,Enabled=False,ContinuousExertionScale=1.,RecoveryScale=1.)
        vars(x).update(kw)
        x.Validate=lambda:execute_flat(str(SETTINGS),'Validate','',vars(x))()
        return x

    def setUp(self):
        self.src=SOURCE.read_text()
        self.c=N(m_Candidate=None,m_Active=False,m_Server=False,m_LoadAttempted=False,
                 m_Experimental=False,m_Suspended=False)
        self.calls=[]
        self.cfg=N(m_Data=None)
        self.e=dict(HCStaminaSettings=self.settings,CfgGameplayHandler=self.cfg,
                    HCStaminaProfile=lambda:N(SchemaVersion=0,Profile='',Experimental=False,Settings=None),
                    Print=lambda text:self.calls.append(text),
                    IsServer=lambda:self.c.m_Server,NativeData=lambda:self.cfg.m_Data,
                    native=N(OnRPC=lambda *a:self.calls.append(a)),
                    ERPCs=N(RPC_CFG_GAMEPLAY_SYNC=77),
                    MPSessionStartEventTypeID=1,MPSessionEndEventTypeID=2,
                    MPSessionFailEventTypeID=3,WorldCleaupEventTypeID=4)
        for n in re.findall(r'static \w+ (\w+)\(',self.src):
            self.e[n]=lambda *a,n=n:self.call(n,*a)
        self.call('Reset',True,False)

    def call(self,n,*args):
        s=self.src.replace('CfgGameplayHandler.m_Data','NativeData()')
        s=re.sub(r'\bs_', 'm_', s)
        s=s.replace('HCStaminaConfiguration.','').replace('super.','native.')
        s=s.replace('data == previous','data is previous')
        s=re.sub(r'static (?:HCStaminaSettings|HCStaminaProfile|float) (\w+)\(',r'static bool \1(',s)
        s=re.sub(r'\b(?:HCStaminaSettings|HCStaminaProfile|ITEM_StaminaData|CfgGameplayJson|FileHandle) (?=\w+\s*=)',
                 'HCGroupNative ',s)
        s=s.replace('int count = ReadFile(handle, text, 16385)',
                    'count, text = ReadChunk(handle, 16385)')
        s=s.replace('JsonFileLoader<HCStaminaProfile>.LoadData(text, profile, error)',
                    'Decode(text, profile)')
        s=s.replace('JsonFileLoader<HCStaminaProfile>.SaveFile(path, profile, error)',
                    'SaveProfile(path, profile)')
        return execute_member(s,n,self.e,self.c,*args)

    def profile_io(self, payload=None, *, directory_ok=True, save_ok=True):
        import json
        self.files={} if payload is None else {'$profile:HollowCountry/stamina.json':payload}
        self.writes=[]
        self.dirs=set() if payload is None else {'$profile:HollowCountry'}
        def save(path,profile):
            self.writes.append(path)
            if not save_ok:return False
            fields={k:v for k,v in vars(profile.Settings).items() if k!='Validate'}
            self.files[path]=json.dumps(dict(SchemaVersion=profile.SchemaVersion,
                Profile=profile.Profile,Experimental=profile.Experimental,Settings=fields))
            return True
        def decode(text,profile):
            try:
                data=json.loads(text)
                vars(profile).update(data)
                profile.Settings=self.settings(**data.get('Settings',{}))
                return True
            except (ValueError,TypeError):return False
        def mkdir(path):
            if directory_ok:self.dirs.add(path)
            return directory_ok
        self.e.update(FileExist=lambda path:path in self.files or path in self.dirs,
            MakeDirectory=mkdir,SaveProfile=save,Decode=decode,FileMode=N(READ=0),
            OpenFile=lambda path,mode:path if path in self.files else None,
            ReadChunk=lambda path,limit:(min(len(self.files[path]),limit),self.files[path][:limit]),
            CloseFile=lambda handle:None)

    def test_fresh_server_creates_enabled_moderate_profile_and_transports_values(self):
        self.profile_io()
        self.cfg.m_Data=self.wire(HCSchemaVersion=0,HCEnabled=False,HCExperimental=False)
        self.call('ServerLoaded')
        self.assertEqual(['$profile:HollowCountry/stamina.json'],self.writes)
        self.assertTrue(self.call('Enabled'))
        self.assertEqual(.5,self.call('ExertionScale'))
        self.assertEqual(1.25,self.call('RecoveryScale'))
        wire=self.cfg.m_Data.PlayerData.StaminaData
        self.assertEqual((1,True,True,.5,1.25),(wire.HCSchemaVersion,wire.HCEnabled,
            wire.HCExperimental,wire.HCContinuousExertionScale,wire.HCRecoveryScale))
        self.assertFalse(self.call('Qualified'))
        self.assertFalse(self.call('LoadServer'))

    def test_operator_template_matches_actual_default_profile(self):
        import json
        profile=self.call('DefaultProfile')
        template=json.loads((ROOT.parents[2]/'config/hollow-country-stamina.json').read_text())
        self.assertTrue(self.call('ProfileValid',profile))
        self.assertEqual((template['SchemaVersion'],template['Profile'],template['Experimental']),
                         (profile.SchemaVersion,profile.Profile,profile.Experimental))
        for key,value in template['Settings'].items():
            self.assertEqual(value,getattr(profile.Settings,key),key)

    def test_existing_explicit_disable_or_invalid_file_is_never_overwritten(self):
        import json
        disabled=json.dumps(dict(SchemaVersion=1,Profile='vanilla',Experimental=False,
            Settings=dict(SchemaVersion=1,Enabled=False,ContinuousExertionScale=1.,RecoveryScale=1.)))
        for payload in (disabled,'{','x'*16385):
            with self.subTest(payload=payload[:12]):
                self.profile_io(payload)
                self.cfg.m_Data=self.wire(HCExperimental=True)
                self.call('ServerLoaded')
                self.assertFalse(self.call('Enabled'))
                self.assertEqual([],self.writes)
                self.assertEqual(payload,self.files['$profile:HollowCountry/stamina.json'])
                self.assertFalse(self.cfg.m_Data.PlayerData.StaminaData.HCExperimental)

    def test_profile_creation_failure_does_not_activate_or_publish_defaults(self):
        for directory_ok,save_ok in ((False,True),(True,False)):
            with self.subTest(directory_ok=directory_ok,save_ok=save_ok):
                self.profile_io(directory_ok=directory_ok,save_ok=save_ok)
                self.cfg.m_Data=self.wire(HCExperimental=True)
                self.call('ServerLoaded')
                self.assertFalse(self.call('Enabled'))
                self.assertEqual(0,self.cfg.m_Data.PlayerData.StaminaData.HCSchemaVersion)
                self.assertTrue(any('stamina' in str(c).lower() for c in self.calls))

    def wire(self,**kw):
        x=N(HCSchemaVersion=1,HCEnabled=True,HCExperimental=False,
            HCContinuousExertionScale=.499992,HCRecoveryScale=1.75)
        vars(x).update(kw)
        return N(PlayerData=N(StaminaData=x))

    def test_private_default_off_snapshot(self):
        x=self.settings(Enabled=True,ContinuousExertionScale=2.)
        self.assertTrue(self.call('Stage',x,False))
        x.ContinuousExertionScale=3.
        view=self.call('Snapshot');view.ContinuousExertionScale=4.
        self.assertEqual(2.,self.call('Snapshot').ContinuousExertionScale)
        self.assertFalse(self.call('Enabled'))
        self.assertEqual(1.,self.call('ExertionScale'))

    def test_profiles_and_bounds(self):
        p=N(SchemaVersion=1,Profile='vanilla',Settings=self.settings())
        self.assertTrue(self.call('ProfileValid',p))
        p.Settings.Enabled=True
        self.assertFalse(self.call('ProfileValid',p))
        p.Profile='custom'
        self.assertTrue(self.call('ProfileValid',p))
        for value in (0.,5.01,float('nan'),float('inf')):
            p.Settings.RecoveryScale=value
            self.assertFalse(self.call('ProfileValid',p))

    def test_invalid_native_receipts(self):
        data=self.wire()
        self.assertTrue(self.call('NativeReceipt',data,None))
        self.assertFalse(self.call('NativeReceipt',data,data))
        self.assertIsNone(self.call('Snapshot'))
        for data in (None,self.wire(HCSchemaVersion=0),
                     self.wire(HCContinuousExertionScale=float('nan'))):
            self.assertFalse(self.call('NativeReceipt',data,None))

    def test_session_resets(self):
        for event in (1,2,3,4):
            self.call('Reset',True,False)
            self.call('Stage',self.settings(),False)
            self.call('SessionEvent',event,False)
            self.assertIsNone(self.call('Snapshot'))
            self.assertEqual(event==1,self.call('ClientActive'))

    def test_cfg_authentication(self):
        for sender,target,ctx in ((True,None,True),(None,True,True),(None,None,None)):
            self.call('OnRPC',sender,target,77,ctx)
        self.call('Reset',False,False)
        self.call('OnRPC',None,None,77,True)
        self.assertEqual([],self.calls)

    def test_decode_failure(self):
        self.call('Stage',self.settings(),False)
        self.cfg.m_Data=self.wire()
        self.call('OnRPC',None,None,77,True)
        self.assertEqual(1,len(self.calls))
        self.assertIsNone(self.call('Snapshot'))

    def test_experimental_activation(self):
        self.assertTrue(self.call('NativeReceipt',self.wire(),None))
        self.assertFalse(self.call('Enabled'))
        self.assertTrue(self.call('NativeReceipt',self.wire(HCExperimental=True),None))
        self.assertTrue(self.call('Enabled'))
        self.assertEqual(.499992,self.call('ExertionScale'))
        self.assertFalse(self.call('Qualified'))
        self.assertTrue(self.call('InstallTrusted',self.call('Snapshot')))
        self.assertFalse(self.call('InstallTrusted',self.settings(Enabled=True)))

    def test_drop_and_reconnect(self):
        self.call('NativeReceipt',self.wire(HCExperimental=True),None)
        self.call('ConnectionState',0)
        self.assertFalse(self.call('Enabled'))
        self.call('ConnectionState',-1)
        self.assertTrue(self.call('Enabled'))
        self.call('SessionEvent',2,False)
        self.call('SessionEvent',1,False)
        self.assertFalse(self.call('Enabled'))
        self.assertIsNone(self.call('Snapshot'))

    def test_bounded_server_loader_and_operator_opt_in(self):
        import json
        opened=[];closed=[]
        def decode(text,p):
            try:d=json.loads(text)
            except ValueError:return False
            vars(p).update(d)
            p.Settings=self.settings(**d.get('Settings',{}))
            return True
        self.e.update(
            HCStaminaProfile=lambda:N(SchemaVersion=0,Profile='',Experimental=False,Settings=None),
            FileExist=lambda path:True,
            FileMode=N(READ=0),OpenFile=lambda p,m:opened.append(p) or 1,
            ReadChunk=lambda h,n:(min(len(self.payload),n),self.payload[:n]),
            CloseFile=lambda h:closed.append(h),Decode=decode)
        d=dict(SchemaVersion=1,Profile='custom',Experimental=True,
               Settings=dict(Enabled=True,ContinuousExertionScale=2.,RecoveryScale=1.))
        self.payload=json.dumps(d)
        self.cfg.m_Data=self.wire()
        self.call('Reset',True,True)
        self.assertTrue(self.call('LoadServer'))
        self.assertTrue(self.call('Enabled'))
        self.assertTrue(self.cfg.m_Data.PlayerData.StaminaData.HCExperimental)
        self.assertFalse(self.call('LoadServer'))
        self.assertEqual((1,1),(len(opened),len(closed)))
        for payload in ('x'*16385,'{',json.dumps(dict(d,Profile='unknown'))):
            self.payload=payload
            self.call('ServerLoaded')
            self.assertFalse(self.call('Enabled'))
            self.assertFalse(self.cfg.m_Data.PlayerData.StaminaData.HCExperimental)
