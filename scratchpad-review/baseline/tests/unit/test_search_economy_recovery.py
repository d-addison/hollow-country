"""Execute authored recovery decisions with explicitly synthetic file records."""
import copy
import json
import unittest
from types import SimpleNamespace as N

from tests.unit.test_search_economy import invoke, manifest
from tests.unit.test_search_economy_policy import EMap


class RecoveryFixture:
    def setUp(self):
        self.m=manifest();self.files={}
        self.s=N(m_Root='/synthetic',m_Manifest=self.m,m_Fault=False)
        self.env={'FileExist':lambda path:path in self.files,'str':str,
                  'HCSearchRules':N(TextValid=lambda value,n:bool(value) and len(value)<=n)}
        for name in ('PathFor','Matches'):
            setattr(self.s,name,lambda *a,n=name:invoke('HCSearchEconomyStore.c',n,self.env,self.s,*a))
        self.s.LoadRecord=lambda i,k:self.files.get(self.s.PathFor(i,k))

    def record(self,phase=1,**kw):
        e=self.m.Entries[0]
        result=N(Version=1,Epoch=1,WorldName=self.m.WorldName,Build=self.m.Build,
                 SourceId=self.m.SourceId,SourcePin=self.m.SourcePin,SiteId=e.SiteId,
                 SupplyId=e.SupplyId,ItemClass=e.ItemClass,ActorId='actor',Phase=phase)
        for k,v in kw.items():setattr(result,k,v)
        return result

    def put(self,kind,record):
        self.files[self.s.PathFor(0,kind)]=record

    def recover(self):
        return invoke('HCSearchEconomyStore.c','Recover',self.env,self.s,0)


class SearchRecoveryTests(RecoveryFixture, unittest.TestCase):
    def test_only_no_records_are_available_and_pending_never_replays(self):
        self.assertEqual(0,self.recover())
        self.put('claim',self.record())
        self.assertEqual(3,self.recover())
        self.put('attempt',self.record())
        self.assertEqual(3,self.recover())


class SearchStoreOpenTests(unittest.TestCase):
    def setUp(self):
        self.files={};self.directories=set();self.messages=[]
        self.policy=N()
        self.env={'EMap':EMap,'str':str,'encode':lambda v:json.dumps(v,default=vars,sort_keys=True),
                  'FileExist':lambda p:p in self.files or p in self.directories,
                  'MakeDirectory':self.mkdir,'write_json':self.write_json,
                  'load_manifest':self.load_manifest,'GetGame':lambda:N(IsServer=lambda:True),
                  'Print':self.messages.append,'HCSearchRules':self.policy}
        for name in ('TextValid','PinValid','ManifestValid'):
            setattr(self.policy,name,lambda *a,n=name:invoke('HCSearchRules.c',n,self.env,N(),*a))

    def store(self):
        s=N(m_Root='',m_Manifest=None,m_Fault=False)
        s.Fail=lambda reason:invoke('HCSearchEconomyStore.c','Fail',self.env,s,reason)
        return s

    def mkdir(self,path):
        self.directories.add(path)
        return True

    def write_json(self,path,value,limit):
        if path in self.files:return False
        text=json.dumps(value,default=vars,sort_keys=True)
        if len(text)>limit:return False
        self.files[path]=text
        return True

    def load_manifest(self,s,path,limit):
        if path not in self.files or len(self.files[path])>limit:return False
        try:
            from tests.unit.test_group_server import EArray
            data=json.loads(self.files[path]);data['Entries']=EArray(N(**e) for e in data['Entries'])
            s.m_Manifest=N(**data)
            return True
        except (ValueError,KeyError,TypeError):return False

    def opened(self,expected=None,initialize=True):
        s=self.store()
        return s,invoke('HCSearchEconomyStore.c','Open',self.env,s,expected or manifest(),initialize)

    def test_new_epoch_is_explicit_and_existing_empty_root_is_never_refilled(self):
        s,ok=self.opened(initialize=False)
        self.assertFalse(ok)
        self.assertNotIn(s.m_Root,self.directories)
        self.directories.add('$profile:HollowCountry/SearchEconomy/epoch_1')
        s,ok=self.opened(initialize=True)
        self.assertFalse(ok)
        self.assertEqual({},self.files)

    def test_loaded_manifest_is_a_fresh_clone_and_reopen_never_writes(self):
        expected=manifest();s,ok=self.opened(expected);self.assertTrue(ok)
        expected.Entries[0].ItemClass='ChangedCallerClass'
        self.assertEqual('SyntheticFood',s.m_Manifest.Entries[0].ItemClass)
        before=copy.deepcopy(self.files)
        reopened,ok=self.opened(initialize=False)
        self.assertTrue(ok)
        self.assertEqual(before,self.files)

    def test_changed_source_build_map_or_allocation_never_adopts_previous_state(self):
        s,ok=self.opened();self.assertTrue(ok)
        before=copy.deepcopy(self.files)
        for key,value in [('SourcePin','b'*64),('WorldName','other'),('Build','other'),('SourceId','other')]:
            m=manifest();setattr(m,key,value)
            with self.subTest(field=key):
                candidate,ok=self.opened(m)
                self.assertFalse(ok)
                self.assertTrue(candidate.m_Fault)
                self.assertEqual(before,self.files)
        m=manifest();m.Entries[0].SupplyId='new_native_item'
        self.assertFalse(self.opened(m)[1])


class SearchRecoveryTerminalTests(RecoveryFixture, unittest.TestCase):
    def test_completed_exact_attempt_and_result_are_terminal(self):
        self.put('claim',self.record());self.put('attempt',self.record())
        for phase in (2,3,4):
            self.put('result',self.record(phase))
            self.assertEqual(phase,self.recover())

    def test_retained_cancellation_can_complete_without_an_inventory_attempt(self):
        self.put('claim',self.record());self.put('result',self.record(4))
        self.assertEqual(4,self.recover())
        self.put('result',self.record(2))
        self.assertEqual(3,self.recover())

    def test_result_without_claim_or_mismatched_actor_is_quarantined(self):
        self.put('result',self.record(2))
        self.assertEqual(3,self.recover())
        self.put('claim',self.record());self.put('attempt',self.record(ActorId='outsider'))
        self.assertEqual(3,self.recover())
        self.put('attempt',self.record());self.put('result',self.record(2,ActorId='outsider'))
        self.assertEqual(3,self.recover())

    def test_wrong_schema_source_world_build_class_or_allocation_is_never_adopted(self):
        self.put('claim',self.record());self.put('attempt',self.record())
        for key,value in [('Version',0),('Version',2),('Epoch',2),('WorldName','other_world'),
                          ('Build','other_build'),('SourcePin','b'*64),('SourceId','other_source'),
                          ('SupplyId','other_item'),('SiteId','other_site'),('ItemClass','Other')]:
            with self.subTest(key=key):
                self.put('result',self.record(2,**{key:value}))
                self.assertEqual(3,self.recover())

    def test_malformed_or_corrupt_native_load_is_terminal(self):
        self.put('claim',None)
        self.assertEqual(3,self.recover())
        self.put('claim',self.record());self.put('attempt',None)
        self.put('result',self.record(2))
        self.assertEqual(3,self.recover())


if __name__=='__main__':
    unittest.main()
