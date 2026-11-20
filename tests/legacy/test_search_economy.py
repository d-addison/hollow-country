"""Authored search-economy methods with synthetic native ports, not engine proof."""
import copy
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.legacy.test_group_server import EArray, body, execute_member

SRC=Path(__file__).resolve().parents[2]/'mods/HollowCountry/scripts/4_World/Loot'


def invoke(filename,name,env,instance,*args):
    path=SRC/filename
    if not path.is_file():
        raise AssertionError('missing authored search economy: '+str(path))
    source=path.read_text()
    match=re.search(r'\b(?:static )?(\w+) '+name+r'\(([^)]*)\)\s*\{',source)
    if not match:
        raise AssertionError('missing authored method: '+name)
    text=body(source,match.end())
    text=re.sub(r'JsonFileLoader<HCSearchManifest>.MakeData\(([^,]+), (\w+), \w+\)',
                r'((\2 := encode(\1)) != null)',text)
    text=text.replace('HCSearchJson<HCSearchManifest>.Load(path, 8388608, m_Manifest)',
                      'load_manifest(self, path, 8388608)')
    text=text.replace('HCSearchJson<HCSearchManifest>.WriteNew(', 'write_json(')
    text=text.replace('HCSearchJson<HCSearchRecord>.WriteNew(', 'write_json(')
    text=re.sub(r'map<[^>]+> (\w+) = new map<[^>]+>',r'\1 = EMap()',text)
    text=re.sub(r'(\w+)\.Get\(index\)',r'\1[index]',text)
    text=text.replace('.IndexOf(','.find(')
    text=re.sub(r'([\w.]+)\.ToString\(\)',r'str(\1)',text)
    text=re.sub(r'int ([\w, ]+);',lambda m:' = '.join(m[1].replace(' ','').split(','))+' = 0;',text)
    text=re.sub(r'(\w+)\.GetPersistentID\(([^)]+)\)',r'\2 = \1.GetPersistentID()',text)
    text=re.sub(r'\b(?:HCSearch\w+|EntityAI|PlayerBase|InventoryLocation|CEItemProfile) (?=\w+\s*=)','',text)
    text=re.sub(r'\b(?:HCSearch\w+|EntityAI|PlayerBase|InventoryLocation|CEItemProfile) (\w+)\s*;',r'\1 = null;',text)
    text=re.sub(r'while \(([^\n]*)\)',r'while \1:',text)
    text=re.sub(r'new (HCSearch\w+|InventoryLocation)(?!\w)(?:\(\))?',r'\1()',text)
    for method in ('Fail','Index','Live','StillAuthorized','CanGrant','Record','Finish','PathFor','Matches','LoadRecord',
                   'Find','Unchanged','CandidateValid','CanTransfer'):
        text=re.sub(r'(?<![\w.])'+method+r'\(', 'self.'+method+'(',text)
    return execute_member('bool '+name+'('+match[2]+') {'+text+'}',name,env,instance,*args)


def manifest(entries=None):
    return N(Version=1,Epoch=1,WorldName='synthetic_world',Build='synthetic_build',
             SourceId='synthetic_spawner',SourcePin='a'*64,
             Entries=EArray(entries or [N(SiteId='site_a',SupplyId='1_2_3_4',ItemClass='SyntheticFood')]))


class SearchEconomyTests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.records={};self.failed=None;self.phase_result=2
        self.actor=N(GetIdentity=lambda:N(GetId=lambda:'actor'),IsAlive=lambda:True,
                     IsUnconscious=lambda:False)
        self.m=manifest()
        self.t=N(m_Enabled=True,m_Ready=True,m_Busy=False,m_Manifest=self.m,
                 m_Phases=EArray([0]))
        self.source=N(ReadyFor=lambda m:True,CanTransfer=lambda entry,actor:True,
                      Transfer=self.transfer)
        self.store=N(Healthy=lambda:True,Write=self.write)
        self.t.m_Source=self.source;self.t.m_Store=self.store
        self.env={'GetGame':lambda:N(IsServer=lambda:True),
                  'HCSearchRecord':lambda:N(Version=0,Phase=0,ActorId=''),
                  'Print':self.events.append}
        for name in ('Index','Live','CanGrant','Record','Finish','Fail'):
            setattr(self.t,name,lambda *a,n=name:self.call(n,*a))
        self.t.StillAuthorized=lambda *a:self.call('StillAuthorized',*a)
        self.env['HCSearchRules']=N(TextValid=lambda value,n:bool(value) and len(value)<=n)

    def call(self,name,*args):
        return invoke('HCSearchEconomy.c',name,self.env,self.t,*args)

    def write(self,index,kind,record):
        self.events.append(kind)
        if self.failed==kind or (index,kind) in self.records:
            return False
        self.records[index,kind]=copy.deepcopy(record)
        return True

    def transfer(self,entry,actor):
        self.events.append('native_move')
        return self.phase_result

    def test_same_handle_transfer_is_preceded_by_durable_intent_and_never_replayed(self):
        self.assertEqual(2,self.call('Grant','site_a',self.actor))
        self.assertEqual(['claim','attempt','native_move','result'],self.events)
        self.assertEqual('actor',self.records[0,'result'].ActorId)
        self.assertEqual(self.m.SourcePin,self.records[0,'result'].SourcePin)
        self.assertEqual(2,self.call('Grant','site_a',self.actor))
        self.assertEqual(1,self.events.count('native_move'))

    def test_claim_or_attempt_failure_never_calls_inventory_and_quarantines(self):
        for kind in ('claim','attempt'):
            with self.subTest(kind=kind):
                self.setUp();self.failed=kind
                self.assertEqual(3,self.call('Grant','site_a',self.actor))
                self.assertNotIn('native_move',self.events)
                self.assertFalse(self.t.m_Ready)
                self.assertEqual(3,self.t.m_Phases[0])

    def test_result_write_failure_cannot_refund_or_replay_a_native_transfer(self):
        self.failed='result'
        self.assertEqual(3,self.call('Grant','site_a',self.actor))
        self.assertEqual(1,self.events.count('native_move'))
        self.assertEqual(-2,self.call('Grant','site_a',self.actor))
        self.assertEqual(1,self.events.count('native_move'))

    def test_uncertain_or_retained_source_is_terminal_without_fabricated_refund(self):
        for phase in (3,4):
            with self.subTest(phase=phase):
                self.setUp();self.phase_result=phase
                self.assertEqual(phase,self.call('Grant','site_a',self.actor))
                self.assertEqual(phase,self.call('Grant','site_a',self.actor))
                self.assertEqual(1,self.events.count('native_move'))

    def test_no_result_site_is_finite_and_does_not_touch_inventory(self):
        self.m.Entries[0].SupplyId='';self.m.Entries[0].ItemClass=''
        self.assertEqual(2,self.call('Grant','site_a',self.actor))
        self.assertEqual(2,self.call('Grant','site_a',self.actor))
        self.assertNotIn('native_move',self.events)
        self.assertEqual(['claim','attempt','result'],self.events)

    def test_missing_source_or_capacity_or_actor_does_not_consume_allocation(self):
        for seam in ('provider','capacity','actor','server','disabled'):
            with self.subTest(seam=seam):
                self.setUp()
                if seam=='provider':self.source.ReadyFor=lambda m:False
                if seam=='capacity':self.source.CanTransfer=lambda e,a:False
                if seam=='actor':self.actor.IsAlive=lambda:False
                if seam=='server':self.env['GetGame']=lambda:N(IsServer=lambda:False)
                if seam=='disabled':self.t.m_Enabled=False
                self.assertLess(self.call('Grant','site_a',self.actor),0)
                self.assertEqual([0],self.t.m_Phases)
                self.assertEqual([],self.events)

    def test_reentrant_grant_cannot_allocate_another_site_during_native_callback(self):
        attempted=[]
        self.m.Entries.Insert(N(SiteId='site_b',SupplyId='5_6_7_8',ItemClass='SyntheticMagazine'))
        self.t.m_Phases.Insert(0)
        def callback(entry,actor):
            attempted.append(self.call('Grant','site_b',actor))
            return 2
        self.source.Transfer=callback
        self.assertEqual(2,self.call('Grant','site_a',self.actor))
        self.assertLess(attempted[0],0)
        self.assertEqual([2,0],self.t.m_Phases)

    def test_cancel_after_claim_is_terminal_without_native_attempt(self):
        original=self.write
        def cancel(index,kind,record):
            result=original(index,kind,record)
            if kind=='claim':self.actor.IsAlive=lambda:False
            return result
        self.store.Write=cancel
        self.assertEqual(4,self.call('Grant','site_a',self.actor))
        self.assertNotIn('native_move',self.events)
        self.assertNotIn('attempt',self.events)
        self.assertEqual(4,self.t.m_Phases[0])

    def test_disable_or_identity_change_after_attempt_cannot_call_native_port(self):
        for event in ('disable','identity','stop'):
            with self.subTest(event=event):
                self.setUp();original=self.write
                def callback(index,kind,record):
                    result=original(index,kind,record)
                    if kind=='attempt':
                        if event=='disable':self.t.m_Enabled=False
                        if event=='stop':self.t.m_Ready=False
                        if event=='identity':self.actor.GetIdentity=lambda:N(GetId=lambda:'changed')
                    return result
                self.store.Write=callback
                self.assertEqual(4,self.call('Grant','site_a',self.actor))
                self.assertNotIn('native_move',self.events)


if __name__=='__main__':
    unittest.main()
