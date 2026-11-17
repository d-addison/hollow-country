"""Execute authored store/service methods using explicit synthetic native IO.

The memory filesystem implements native calls only, not a second store. This
does not establish native file durability, real restart or RPC transport proof.
"""
import copy
import json
import re
import unittest
from types import SimpleNamespace as N

from tests.unit.test_group_server import ROOT, EArray, body, execute_member, translated_rules


class NativeText(str):
    def Hash(self):
        # Synthetic deterministic hash, NOT native string.Hash or integrity.
        return sum((i + 1) * ord(c) for i, c in enumerate(self)) % 2147483647


class StoreHarness:
    def __init__(self):
        self.source = (ROOT/'4_World/Groups/HCGroupStore.c').read_text()
        self.rules = translated_rules()
        self.files = {}
        self.directories = set()
        self.writes = []
        self.fail_write = None
        self.fail_delete = False
        self.closed = 0
        self.logs = []
        self.literal_serial = 0
        self.env = dict(self.rules, GetGame=lambda: N(GetWorldName=lambda:'synthetic_world'),
                        Math=N(Max=max), FileAttr=N(DIRECTORY=1),
                        FindFileFlags=N(DIRECTORIES=1), Print=self.logs.append,
                        FileExist=lambda p:p in self.files or p in self.directories,
                        MakeDirectory=self.mkdir, DeleteFile=self.delete,
                        first=self.first, following=self.following, CloseFindFile=self.close,
                        read=self.read, load=self.load, encode=self.encode, decode=self.decode,
                        write=self.write, write_json=lambda p,v,n:self.write(p,self.encode(v),n),
                        str=str)

    def mkdir(self, path):
        self.directories.add(path)
        return True

    def delete(self, path):
        if self.fail_delete:
            return False
        self.files.pop(path, None)
        return True

    def first(self, pattern, *unused):
        root = pattern[:-1]
        names = sorted(p[len(root):] for p in self.files if p.startswith(root))
        iterator = iter(names)
        return iterator, next(iterator, ''), 0

    def following(self, iterator):
        name = next(iterator, '')
        return bool(name), name, 0

    def close(self, unused):
        self.closed += 1

    def read(self, path, limit):
        value = self.files.get(path)
        return NativeText(value) if value and len(value) <= limit else None

    def encode(self, value):
        return NativeText(json.dumps(value, default=vars, sort_keys=True, separators=(',',':')))

    def decode(self, text, kind):
        # Explicit synthetic JSON adapter: native class field initializers are
        # represented at every DTO level, including additive legacy defaults.
        children = {'Groups':'HCGroupRecord', 'Markers':'HCGroupMarker',
                    'Explorers':'HCGroupExplorer', 'Visits':'HCGroupPlace',
                    'Invitations':'HCGroupInvitation'}
        def dto(value, dto_kind=None):
            if isinstance(value, list):
                return EArray(dto(v, dto_kind) for v in value)
            if isinstance(value, dict):
                result = self.rules[dto_kind]() if dto_kind else N()
                result.__dict__.update({k:dto(v,children.get(k)) for k,v in value.items()})
                return result
            return value
        try:
            result = self.rules[kind]()
            result.__dict__.update(vars(dto(json.loads(text))))
            return result
        except (ValueError, TypeError):
            return None

    def load(self, path, limit):
        text = self.read(path, limit)
        return self.decode(text, 'HCGroupReceipt') if text is not None else None

    def write(self, path, text, limit):
        self.writes.append(path)
        if len(self.writes) == self.fail_write or path in self.files:
            return False
        if not 0 < len(text) <= limit:
            return False
        self.files[path] = NativeText(text)
        return True

    def store(self, settings):
        store = N(m_Root='/synthetic/groups/state',m_Settings=settings,m_Latest=0,m_Fault=False)
        for name in ('Fault','PathFor','RevisionInName','Open','Save'):
            setattr(store,name,lambda *a,n=name:self.invoke(store,n,*a))
        return store

    def invoke(self, instance, name, *args):
        match = re.search(r'\b(?:bool|int|string) '+name+r'\(([^)]*)\)\s*\{',self.source)
        text = re.sub(r'//[^\n]*','',body(self.source,match.end()))
        # Adapt native out parameters, retaining short-circuit evaluation.
        text = re.sub(r'JsonFileLoader<HCGroupState>\.MakeData\((\w+), (\w+), \w+\)',
                      r'((\2 := encode(\1)) != null)',text)
        text = re.sub(r'JsonFileLoader<HCGroupState>\.LoadData\((\w+), (\w+), \w+\)',
                      r'((\2 := decode(\1, "HCGroupState")) != null)',text)
        text = re.sub(r'HCGroupIO.Read\((.+?), (.+?), (\w+)\)',
                      r'((\3 := read(\1, \2)) != null)',text)
        text = re.sub(r'HCGroupJson<HCGroupReceipt>.Load\((.+?), (\d+), (\w+)\)',
                      r'((\3 := load(\1, \2)) != null)',text)
        text = text.replace('HCGroupIO.WriteNew(', 'write(')
        text = text.replace('array<ref HCGroupInvitation> invitations = ', 'invitations = ').replace('new array<ref HCGroupInvitation>()', 'EArray()')
        text = text.replace('HCGroupJson<HCGroupReceipt>.WriteNew(', 'write_json(')
        text = re.sub(r'FindFileHandle handle = FindFile\((.+?), filename, attr, (.+?)\)',
                      r'handle, filename, attr = first(\1, \2)',text)
        text = text.replace('found = FindNextFile(handle, filename, attr)',
                            'found, filename, attr = following(handle)')
        text = text.replace('FileAttr attr','int attr').replace('while (found)','while found:')
        for method in ('Save','RevisionInName'):
            text = re.sub(r'(?<![\w.])'+method+r'\(', 'self.'+method+'(',text)
        text = re.sub(r'(\w+)\.ToString\(\)',r'str(\1)',text)
        text = text.replace('name.IndexOf(prefix)','name.find(prefix)')
        text = text.replace('name.Substring(prefix.Length(), name.Length() - prefix.Length() - 5).ToInt()',
                            'int(name[len(prefix):-5]) if name[len(prefix):-5].isdigit() else 0')
        if name == 'Open':
            text = re.sub(r'return (.+?);',r'return \1, state;',text)
        def literal(match):
            key='_store_literal_'+str(self.literal_serial)
            self.literal_serial+=1
            self.env[key]=json.loads(match[0])
            return key
        text=re.sub(r'"(?:\\.|[^"\\])*"',literal,text)
        # execute_member already adapts the remaining Enforce syntax.
        wrapper = 'bool '+name+'('+match[1]+') {'+text+'}'
        return execute_member(wrapper,name,self.env,instance,*args)


class GroupPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.h = StoreHarness()
        self.cfg = self.h.rules['HCGroupSettings']()
        self.s = self.h.store(self.cfg)
        success,self.state = self.s.Open(self.cfg,None)
        self.assertTrue(success)

    def test_save_never_swaps_ref_arrays_the_native_compiler_rejects(self):
        # Native compile (Wine, Expansion stack) rejected Swap between
        # array<ref HCGroupInvitation> and its by-value form at hcgroupstore.c(153).
        source = (ROOT / '4_World/Groups/HCGroupStore.c').read_text()
        self.assertNotIn('.Swap(', source)

    def test_actual_store_roundtrip_retains_acl_expiry_watermark_not_invites(self):
        e=self.h.rules
        q=e['HCGroupRequest'](); q.Op=e['HCGroupOp'].CREATE;q.Name='Synthetic'
        self.assertEqual(0,e['Apply'](self.state,self.cfg,q,'alice',2000000001))
        q.Op=e['HCGroupOp'].INVITE;q.TargetId='bob';q.ExpectedRevision=1
        self.assertEqual(0,e['Apply'](self.state,self.cfg,q,'alice',2000000001))
        self.state.LastMutationUtc=2000000001;self.state.Revision+=1
        self.assertTrue(self.s.Save(self.state))
        self.assertEqual(1,len(self.state.Invitations))
        restarted=self.h.store(self.cfg)
        ok,loaded=restarted.Open(self.cfg,None)
        self.assertTrue(ok)
        self.assertEqual(['alice'],loaded.Groups[0].Members)
        self.assertEqual('alice',loaded.Groups[0].OwnerId)
        self.assertEqual(2000000001,loaded.LastMutationUtc)
        self.assertEqual([],loaded.Invitations)
        self.assertFalse(e['ClockAllows'](loaded,2000000000))
        self.assertTrue(e['ClockAllows'](loaded,2000000001))
        self.assertEqual(1,self.h.closed)

    def test_partial_highest_transaction_never_restores_an_older_acl(self):
        for fail in (2,3):
            with self.subTest(write=fail):
                h=StoreHarness();s=h.store(self.cfg)
                ok,state=s.Open(self.cfg,None);self.assertTrue(ok)
                state.Revision+=1
                h.fail_write=len(h.writes)+fail
                self.assertFalse(s.Save(state))
                reopened=h.store(self.cfg)
                self.assertFalse(reopened.Open(self.cfg,None)[0])
                self.assertTrue(reopened.m_Fault)

    def test_corrupt_highest_image_or_receipt_is_rejected_without_fallback(self):
        for basename in ('state_1.json','intent_1.json','commit_1.json'):
            with self.subTest(file=basename):
                files=copy.deepcopy(self.h.files)
                self.h.files[self.s.m_Root+'/'+basename]=NativeText('{}')
                self.assertFalse(self.h.store(self.cfg).Open(self.cfg,None)[0])
                self.h.files=files

    def test_preexisting_zero_watermark_migrates_without_resetting_acl(self):
        disk=json.loads(self.h.files[self.s.m_Root+'/state_1.json'])
        disk.pop('LastMutationUtc',None)
        image=NativeText(json.dumps(disk,sort_keys=True,separators=(',',':')))
        self.h.files[self.s.m_Root+'/state_1.json']=image
        for prefix in ('intent_','commit_'):
            receipt=json.loads(self.h.files[self.s.m_Root+'/'+prefix+'1.json'])
            receipt.update(Length=len(image),Hash=image.Hash())
            self.h.files[self.s.m_Root+'/'+prefix+'1.json']=self.h.encode(receipt)
        ok,loaded=self.h.store(self.cfg).Open(self.cfg,None)
        self.assertTrue(ok)
        self.assertEqual(0,loaded.LastMutationUtc)
        self.assertTrue(self.h.rules['ClockAllows'](loaded,2000000001))

    def test_unrecognized_paths_and_enumeration_over_budget_fail_closed(self):
        self.h.files[self.s.m_Root+'/not-owned.txt']=NativeText('synthetic')
        self.assertFalse(self.h.store(self.cfg).Open(self.cfg,None)[0])
        self.h.files.pop(self.s.m_Root+'/not-owned.txt')
        for i in range(2,self.cfg.KeepRevisions+4):
            for prefix in ('intent_','state_','commit_'):
                self.h.files[self.s.m_Root+'/'+prefix+str(i)+'.json']=NativeText('{}')
        self.assertFalse(self.h.store(self.cfg).Open(self.cfg,None)[0])

    def test_real_start_path_reopens_then_rejects_rollback_before_serving_peers(self):
        self.state.LastMutationUtc=2000000001
        self.state.Revision+=1
        self.assertTrue(self.s.Save(self.state))
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        for now,expected in [(2000000000,False),(2000000001,True),(2147483647,True)]:
            with self.subTest(now=now):
                instance=N(m_Healthy=False,m_State=None,m_Peers=EArray())
                runtime=N(instance=None)
                store=self.h.store(self.cfg)
                calls=[]
                def open_state(settings):
                    ok,instance.m_State=store.Open(settings,None)
                    return ok
                game=N(IsServer=lambda:True,GetWorld=lambda:N(GetWorldSize=lambda:15360.),
                       GetPlayers=lambda players:calls.append('GetPlayers'))
                env=dict(self.h.rules,GetGame=lambda:game,HCGroupClock=N(Utc=lambda:now),
                         HCGroupStore=lambda:store,open_state=open_state,runtime=runtime,
                         HCGroupPlaces=N(Load=lambda:N(Places=EArray())),
                         Math=N(RandomIntInclusive=lambda a,b:123),EArray=EArray,str=str,
                         Print=self.h.logs.append)
                match=re.search(r'bool Start\(([^)]*)\)\s*\{',source)
                text=body(source,match.end()).replace('s_Instance','runtime.instance')
                text=re.sub(r'\bthis\b','self',text)
                text=text.replace('m_Store.Open(config, m_State)','open_state(config)')
                text=text.replace('array<Man> players = new array<Man>()','players = EArray()')
                text=text.replace('PlayerBase player =','player =')
                text=text.replace('Math.RandomIntInclusive(1, 1000000000).ToString()',
                                  'str(Math.RandomIntInclusive(1, 1000000000))')
                text=text.replace('m_LastUtc.ToString()','str(m_LastUtc)')
                self.assertEqual(expected,execute_member('bool Start('+match[1]+') {'+text+'}',
                                                        'Start',env,instance,self.cfg))
                self.assertEqual(expected,instance.m_Healthy)
                self.assertEqual(['GetPlayers'] if expected else [],calls)


if __name__ == '__main__':
    unittest.main()
