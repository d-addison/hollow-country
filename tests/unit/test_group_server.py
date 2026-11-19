"""Synthetic execution of authored group rules, plus native seam contracts.

The restricted translator follows existing scalar-policy tests and additionally
supports DTOs/arrays/foreach. It supplies language/container scaffolding, never a
second group implementation. It is not an Enforce compiler or network evidence.
"""
from pathlib import Path
import json
import math
import re
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'


class EArray(list):
    def __bool__(self): return True  # Native managed array reference, even empty.
    def Insert(self, item): self.append(item)
    def Count(self): return len(self)
    def Get(self, index): return self[index]
    def Find(self, item): return self.index(item) if item in self else -1
    def Remove(self, index): self.pop(index)
    def RemoveOrdered(self, index): self.pop(index)
    def Clear(self): self.clear()
    def Swap(self, other): self[:], other[:] = list(other), list(self)


def body(source, start):
    depth, end = 1, start
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end-1]


def execute_member(source, name, env, *args):
    """Execute an actual member body with explicit synthetic native adapters.

    Only language syntax and native output parameters are adapted. This never
    supplies transaction, replay, permission or pruning decisions.
    """
    match=re.search(r'\b(?:bool|int|void|HCGroupMember|HCGroupEquipment) '+name+r'\(([^)]*)\)\s*\{',source)
    if args and hasattr(args[0], '__dict__'):
        receiver=args[0]
        for helper in ('Equipment','LOSAllows','EvictExplorers'):
            if not hasattr(receiver, helper) and re.search(r'\b'+helper+r'\(',source):
                setattr(receiver,helper,lambda *values,helper=helper:execute_member(source,helper,dict(env),receiver,*values))
    statements=body(source,match.end())
    statements=re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)',r'foreach (int \1 : reverse_indices(\2))',statements)
    env.setdefault('reverse_indices',lambda n:range(n,-1,-1))
    # Preserve string contents (including semicolons/braces) as literals before
    # translating statement/block syntax. Nested authored calls use unique keys.
    def literal(match):
        index=len(env)
        key='_authored_literal_'+str(index)
        while key in env:
            index+=1
            key='_authored_literal_'+str(index)
        env[key]=json.loads(match[0])
        return key
    statements=re.sub(r'"(?:\\.|[^"\\])*"',literal,statements)
    parameters=[a.split('=')[0].split()[-1] for a in match[1].split(',') if a.strip()]
    # Inline Enforce guards use the same block syntax as the rule translator.
    cursor=0
    while True:
        found=re.search(r'\b(if|foreach) \(',statements[cursor:])
        if not found:break
        guard=cursor+found.start()
        start=cursor+found.end();end=start;depth=1
        while depth:
            depth+=(statements[end]=='(')-(statements[end]==')');end+=1
        next_statement=end
        while statements[next_statement].isspace():next_statement+=1
        if statements[next_statement]!='{':
            finish=statements.index(';',next_statement)+1
            statements=statements[:end]+' {'+statements[end:finish]+' }'+statements[finish:]
        cursor=end+2
    lines=[f'def member(self, {", ".join(parameters)}):'];indent=1
    for token in re.split(r'([{};])',re.sub(r'//[^\n]*','',statements)):
        token=token.strip()
        if not token or token==';': continue
        if token=='{': indent+=1;continue
        if token=='}': indent-=1;continue
        token=re.sub(r'new (\w+)(?:\(\))?',r'\1()',token)
        # Native JSON's three output parameters become an adapter tuple.
        token=re.sub(r'bool (\w+) = JsonFileLoader<HCGroupState>\.MakeData\((\w+), (\w+), (\w+)\)',r'\1, \3, \4 = serialize(\2)',token)
        bare=re.fullmatch(r'(int|float|bool|string|HCGroup\w+) (\w+)',token)
        if bare:
            token=bare[2]+' = '+{'int':'0','float':'0.0','bool':'False','string':"''"}.get(bare[1],'None')
        token=re.sub(r'\b(?:int|float|bool|string|vector|ScriptRPC|HCUnitBudget|HCGroup\w+)\s+(?=\w+\s*=)','',token)
        token=re.sub(r'\bm_\w+\b',lambda m:'self.'+m[0],token)
        for method in ('Fault','PathFor','Live','Peer','HasGPS','Member','SendSnapshot','VisibilityAllows','Equipment','LOSAllows','EvictExplorers'):
            token=re.sub(r'(?<![\w.])'+method+r'\(', 'self.'+method+'(',token)
        token=token.replace('HCGroupRules.','')
        token=token.replace('&&',' and ').replace('||',' or ')
        token=re.sub(r'!(?!=)','not ',token)
        for original,target in [('true','True'),('false','False'),('null','None')]:
            token=re.sub(r'\b'+original+r'\b',target,token)
        if token.startswith('if ('): token='if '+token[4:-1]+':'
        elif token.startswith('while ('): token='while '+token[7:-1]+':'
        elif token.startswith('foreach ('):
            loop=re.fullmatch(r'foreach \(\w+ (\w+) : (.+)\)',token)
            token=f'for {loop[1]} in {loop[2]}:'
        elif token=='else': token+=':'
        token=re.sub(r'([\w.]+)\+\+$',r'\1 += 1',token)
        token=re.sub(r'([\w.]+)\.Length\(\)',r'len(\1)',token)
        lines.append('    '*indent+token)
    exec(compile('\n'.join(lines),'authored-native-member:'+name,'exec'),env)
    return env['member'](*args)


def translated_rules():
    data = (ROOT/'3_Game/Groups/HCGroupData.c').read_text()
    protocol = (ROOT/'3_Game/Groups/HCGroupProtocol.c').read_text()
    source = (ROOT/'4_World/Groups/HCGroupRules.c').read_text()
    env = {'EArray': EArray, 'len': len}
    env['HCGroupProtocol']=SimpleNamespace(**{k:int(v) for k,v in
        re.findall(r'static const int (\w+) = (\d+);',protocol)})
    for match in re.finditer(r'enum (\w+)\s*\{([^}]+)\}', protocol):
        env[match[1]] = SimpleNamespace(**{k: int(v) for k,v in
            re.findall(r'(\w+)\s*=\s*(\d+)', match[2])})
    for match in re.finditer(r'class (\w+)\s*\{', data):
        fields = body(data, match.end())
        defaults = []
        for field in re.finditer(r'^\s*(?:ref )?([\w<> ]+?) (\w+)(?:\s*=\s*([^;]+))?;', fields, re.M):
            typ, name, value = field.groups()
            defaults.append((typ, name, value))
        def make(defaults=defaults):
            instance = SimpleNamespace()
            for typ, name, value in defaults:
                if 'array<' in typ: result = EArray()
                elif typ == 'vector': result = [0., 0., 0.]
                elif value is None:
                    result = {'string': '', 'bool': False, 'int': 0, 'float': 0.}.get(typ)
                else: result = json.loads(value.replace('false','false').replace('true','true'))
                setattr(instance, name, result)
            return instance
        env[match[1]] = make
    source = re.sub(r'//[^\n]*', '', source)
    for match in re.finditer(r'static ([\w<> ]+?) (\w+)\(([^)]*)\)\s*\{', source):
        args = [a.strip().split()[-1] for a in match[3].split(',') if a.strip()]
        lines, indent = [f'def {match[2]}({", ".join(args)}):'], 1
        for token in re.split(r'([{};])', body(source, match.end())):
            token = token.strip()
            if not token or token == ';': continue
            if token == '{': indent += 1; continue
            if token == '}': indent -= 1; continue
            token = re.sub(r'new array<[^;]+>\(\)', 'EArray()', token)
            token = re.sub(r'new (HCGroup\w+)(?:\(\))?', r'\1()', token)
            token = token.replace('HCGroupRules.', '')
            token = token.replace('&&', ' and ').replace('||', ' or ')
            token = re.sub(r'!(?!=)', 'not ', token)
            token = re.sub(r'\btrue\b', 'True', token)
            token = re.sub(r'\bfalse\b', 'False', token)
            token = re.sub(r'\bnull\b', 'None', token)
            if token.startswith('foreach ('):
                loop = re.fullmatch(r'foreach \((?:\w+) (\w+) : (.+)\)', token)
                token = f'for {loop[1]} in {loop[2]}:'
            else:
                bare = re.fullmatch(r'(?:int|float|bool|string|vector|HCGroup\w+) (\w+)', token)
                if bare:
                    token = bare[1] + ' = None'
                token = re.sub(r'\b(?:int|float|bool|string|vector|HCGroup\w+)\s+(?=\w+\s*=)', '', token)
                token = re.sub(r'array<[\w ]+>\s+(?=\w+\s*=)', '', token)
                if token.startswith(('if (','while (')):
                    prefix, expression = token.split(' (',1)
                    token = f'{prefix} {expression[:-1]}:'
                elif token == 'else': token += ':'
            token = re.sub(r'([\w.]+)\.Trim\(\)\.Length\(\)', r'len(\1.strip())', token)
            token = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', token)
            token = re.sub(r'([\w.]+)\.Contains\(([^)]+)\)', r'(\2 in \1)', token)
            token = re.sub(r'([\w.]+)\.Trim\(\)', r'\1.strip()', token)
            lines.append('    '*indent + token)
        exec(compile('\n'.join(lines), str(ROOT/'4_World/Groups/HCGroupRules.c'), 'exec'), env)
    env['HCMenuInput'] = SimpleNamespace(Lock=lambda: None, Unlock=lambda: None, BackPressed=lambda: False)
    return env


class GroupServerTests(unittest.TestCase):
    def setUp(self):
        self.e = translated_rules()
        self.state = self.e['HCGroupState']()
        self.state.WorldName = 'chernarusplus'  # Explicit synthetic world fixture.
        self.cfg = self.e['HCGroupSettings']()
        self.cfg.Enabled = True
        self.op = self.e['HCGroupOp']
        self.code = self.e['HCGroupCode']

    def request(self, op, **fields):
        q = self.e['HCGroupRequest']()
        q.Op = op
        for k,v in fields.items(): setattr(q,k,v)
        return q

    def apply(self, actor, op, **fields):
        group = self.e['FindGroup'](self.state, actor)
        fields.setdefault('ExpectedRevision', group.Revision if group else 0)
        return self.e['Apply'](self.state, self.cfg, self.request(op, **fields), actor, 1000)

    def create(self, actor='alice'):
        self.assertEqual(self.code.OK, self.apply(actor,self.op.CREATE,Name='Travelers'))
        return self.e['FindGroup'](self.state,actor)

    def joined(self):
        g=self.create()
        self.assertEqual(0,self.apply('alice',self.op.INVITE,TargetId='bob'))
        invite=self.state.Invitations[0]
        self.assertEqual(0,self.apply('bob',self.op.ACCEPT,EntityId=invite.Id))
        return g

    def test_create_invite_accept_and_account_membership(self):
        g=self.joined()
        self.assertEqual('alice',g.OwnerId)
        self.assertEqual(['alice','bob'],g.Members)
        self.assertEqual([],self.state.Invitations)
        self.assertEqual(self.code.CONFLICT,self.apply('bob',self.op.CREATE,Name='Other'))

    def test_decline_expiry_outsider_and_duplicate_invites(self):
        self.create()
        self.assertEqual(0,self.apply('alice',self.op.INVITE,TargetId='bob'))
        invite=self.state.Invitations[0]
        self.assertEqual(self.code.DENIED,self.apply('mallory',self.op.ACCEPT,EntityId=invite.Id))
        self.assertEqual(self.code.CONFLICT,self.apply('alice',self.op.INVITE,TargetId='bob'))
        self.assertEqual(0,self.apply('bob',self.op.DECLINE,EntityId=invite.Id))
        self.assertEqual([],self.state.Invitations)
        self.apply('alice',self.op.INVITE,TargetId='bob')
        self.state.Invitations[0].ExpiresUtc=1000
        self.assertEqual(self.code.NOT_FOUND,self.apply('bob',self.op.ACCEPT,EntityId=self.state.Invitations[0].Id))

    def test_member_cannot_kick_transfer_disband_rename_or_invite(self):
        self.joined()
        for op in (self.op.KICK,self.op.TRANSFER,self.op.DISBAND,self.op.RENAME,self.op.INVITE):
            self.assertEqual(self.code.DENIED,self.apply('bob',op,TargetId='alice',Name='Other'))

    def test_leave_kick_owner_transfer_and_disband(self):
        g=self.joined()
        self.assertEqual(self.code.DENIED,self.apply('alice',self.op.LEAVE))
        self.assertEqual(0,self.apply('alice',self.op.TRANSFER,TargetId='bob'))
        self.assertEqual('bob',g.OwnerId)
        self.assertEqual(0,self.apply('alice',self.op.LEAVE))
        self.assertIsNone(self.e['FindGroup'](self.state,'alice'))
        self.assertEqual(0,self.apply('bob',self.op.INVITE,TargetId='alice'))
        self.assertEqual(0,self.apply('alice',self.op.ACCEPT,EntityId=self.state.Invitations[0].Id))
        self.assertEqual(0,self.apply('bob',self.op.KICK,TargetId='alice'))
        self.assertEqual(0,self.apply('bob',self.op.DISBAND))
        self.assertEqual([],self.state.Groups)

    def test_marker_notes_crud_owner_creator_permissions_and_revision(self):
        g=self.joined()
        self.assertEqual(0,self.apply('bob',self.op.MARKER_CREATE,Name='Water',Note='Near the road',Position=[100.,0.,200.]))
        marker=g.Markers[0]
        self.assertEqual('bob',marker.CreatorId)
        self.assertEqual('Near the road',marker.Note)
        self.assertEqual(self.code.CONFLICT,self.apply('bob',self.op.MARKER_UPDATE,EntityId=marker.Id,Name='Changed',ExpectedRevision=g.Revision-1))
        self.assertEqual(0,self.apply('alice',self.op.MARKER_UPDATE,EntityId=marker.Id,Name='Rally',Note='Updated',Position=[200.,0.,300.]))
        self.assertEqual('Updated',marker.Note)
        self.assertEqual(self.code.DENIED,self.apply('mallory',self.op.MARKER_DELETE,EntityId=marker.Id))
        self.assertEqual(0,self.apply('bob',self.op.MARKER_DELETE,EntityId=marker.Id))
        self.assertEqual([],g.Markers)

    def test_other_member_cannot_edit_someone_elses_marker(self):
        g=self.joined()
        self.assertEqual(0,self.apply('alice',self.op.MARKER_CREATE,Name='Owner note'))
        self.assertEqual(self.code.DENIED,self.apply('bob',self.op.MARKER_UPDATE,EntityId=g.Markers[0].Id,Name='Hijack'))
        self.assertEqual(self.code.DENIED,self.apply('bob',self.op.MARKER_DELETE,EntityId=g.Markers[0].Id))

    def test_caps_invalid_numbers_and_retention_are_enforced(self):
        g=self.joined()
        self.cfg.MaxMembers=2
        self.assertEqual(self.code.LIMIT,self.apply('alice',self.op.INVITE,TargetId='charlie'))
        self.cfg.MaxMarkers=1
        self.assertEqual(0,self.apply('alice',self.op.MARKER_CREATE,Name='A',TtlSeconds=10))
        self.assertEqual(1010,g.Markers[0].ExpiresUtc)
        self.assertEqual(self.code.LIMIT,self.apply('bob',self.op.MARKER_CREATE,Name='B'))
        self.apply('alice',self.op.MARKER_DELETE,EntityId=g.Markers[0].Id)
        for position in ([math.nan,0,0],[0,math.inf,0],[0,0,-1],[50001,0,0]):
            self.assertEqual(self.code.INVALID,self.apply('alice',self.op.MARKER_CREATE,Name='Bad',Position=position))
        self.assertEqual(self.code.INVALID,self.apply('alice',self.op.MARKER_CREATE,Name='A',Note='x'*513))

    def test_validated_settings_reject_invalid_bounds(self):
        self.assertTrue(self.e['SettingsValid'](self.cfg))
        for field,value in [('MaxMembers',0),('MaxMembers',91),('MaxMarkers',257),('PositionIntervalSeconds',math.nan),('KeepRevisions',1)]:
            c=self.e['HCGroupSettings']();setattr(c,field,value)
            self.assertFalse(self.e['SettingsValid'](c))
        self.assertTrue(self.e['HCGroupSettings']().Enabled)
        self.assertFalse(self.e['HCGroupSnapshot']().Enabled)

    def test_rule_expressions_keep_small_native_compiler_complexity_budget(self):
        # Probe031 actually rejected the long SettingsValid formula. This is
        # a conservative source regression guard, not an Enforce compiler model.
        source=(ROOT/'4_World/Groups/HCGroupRules.c').read_text()
        source=re.sub(r'//[^\n]*','',source)
        for expression in re.split(r'[;{}]',source):
            count=len(re.findall(r'&&|\|\|',expression))
            self.assertLessEqual(count,4,expression.strip())

    def test_settings_boundaries_finite_values_and_cross_field_staleness(self):
        valid=self.e['SettingsValid']
        self.assertFalse(valid(None))
        bounds={
            'MaxGroups':(1,90),'MaxMembers':(1,90),'MaxMarkers':(1,256),
            'MaxInvites':(1,256),'MaxRequestsPerSecond':(1,16),
            'MaxStoreBytes':(16384,1048576),'KeepRevisions':(2,32),
            'InviteSeconds':(10,3600),'MarkerRetentionSeconds':(0,2592000),
            'PositionIntervalSeconds':(1.,30.),'MaxIconDistance':(10.,5000.),
        }
        for field,(low,high) in bounds.items():
            for value,expected in [(low,True),(high,True),(low-1,False),(high+1,False)]:
                with self.subTest(field=field,value=value):
                    config=self.e['HCGroupSettings']()
                    # Isolate the interval bound from its dependent stale time.
                    config.PositionStaleSeconds=120.
                    setattr(config,field,value)
                    self.assertEqual(expected,valid(config))
        for field in ('PositionIntervalSeconds','PositionStaleSeconds','MaxIconDistance'):
            for value in (math.nan,math.inf,-math.inf):
                with self.subTest(field=field,value=value):
                    config=self.e['HCGroupSettings']();setattr(config,field,value)
                    self.assertFalse(valid(config))
        for stale,expected in [(2.,True),(120.,True),(1.99,False),(120.01,False)]:
            config=self.e['HCGroupSettings']();config.PositionStaleSeconds=stale
            self.assertEqual(expected,valid(config))
        for field in ('RequireLOS','RequireRadio'):
            config=self.e['HCGroupSettings']();setattr(config,field,True)
            self.assertTrue(valid(config))
        config=self.e['HCGroupSettings']();config.SchemaVersion=2
        self.assertFalse(valid(config))

    def test_disabled_policy_and_invalid_version_never_mutate(self):
        self.cfg.Enabled=False
        self.assertEqual(self.code.DISABLED,self.apply('alice',self.op.CREATE,Name='A'))
        self.assertEqual([],self.state.Groups)
        self.cfg.Enabled=True
        self.assertEqual(self.code.INVALID,self.apply('alice',self.op.CREATE,Name='A',Version=1))
        self.assertEqual([],self.state.Groups)

    def test_persisted_acl_rejects_duplicate_members_or_missing_owner(self):
        g=self.joined()
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        g.Members.Insert('bob')
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        g.Members.Remove(2)
        g.OwnerId='mallory'
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_highest_revision_torn_write_or_length_hash_drift_never_rewinds(self):
        p=self.e['LatestComplete']
        self.assertTrue(p(5,5,5,5,5,120,120,17,17))
        for args in [(6,5,5,5,5,120,120,17,17),(5,6,5,5,5,120,120,17,17),
                     (5,5,6,5,5,120,120,17,17),(5,5,5,4,5,120,120,17,17),
                     (5,5,5,5,4,120,120,17,17),(5,5,5,5,5,120,121,17,17),
                     (5,5,5,5,5,120,120,17,18)]:
            self.assertFalse(p(*args))

    def test_corrupt_null_group_or_duplicate_entity_id_is_refused(self):
        g=self.joined()
        self.state.Groups.Insert(None)
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        self.state.Groups.Remove(1)
        self.apply('alice',self.op.MARKER_CREATE,Name='A')
        g.Markers[0].Id=g.Id
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_world_identity_is_required_and_cross_map_never_reused(self):
        self.assertEqual('',self.e['HCGroupState']().WorldName)
        self.create()
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'enoch'))
        self.state.WorldName=''
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,''))

    def test_offline_membership_capacity_is_not_concurrent_player_limit(self):
        self.cfg.MaxGroups=32
        self.cfg.MaxMembers=8
        for i in range(13):
            owner=f'owner{i}'
            group=self.create(owner)
            for j in range(6):
                uid=f'member{i}-{j}'
                self.assertEqual(0,self.apply(owner,self.op.INVITE,TargetId=uid))
                self.assertEqual(0,self.apply(uid,self.op.ACCEPT,EntityId=self.state.Invitations[-1].Id))
        self.assertEqual(91,sum(len(g.Members) for g in self.state.Groups))
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_retention_increase_skips_absent_old_triple_but_delete_failure_faults(self):
        source=(ROOT/'4_World/Groups/HCGroupStore.c').read_text()
        save=source[source.index('    bool Save('):]
        # Execute actual Save pruning tail, after synthetic successful rev101.
        tail=save[save.index('        int old ='):save.rfind('    }')]
        method='bool Prune() {'+tail+'}'
        paths={f'{p}{r}' for p in ('intent_','state_','commit_') for r in range(93,102)}
        deleted=[]
        def delete(path):
            deleted.append(path)
            if path not in paths:return False
            paths.remove(path);return True
        store=SimpleNamespace(m_Latest=101,m_Settings=SimpleNamespace(KeepRevisions=9),
            PathFor=lambda p,r:p+str(r),Fault=lambda:False)
        env={'FileExist':lambda p:p in paths,'DeleteFile':delete}
        self.assertTrue(execute_member(method,'Prune',env,store))
        self.assertEqual([],deleted)
        paths.add('intent_92')
        self.assertTrue(execute_member(method,'Prune',env,store))
        self.assertEqual(['intent_92'],deleted)
        paths.add('intent_92');env['DeleteFile']=lambda p:False
        self.assertFalse(execute_member(method,'Prune',env,store))

    def test_budget_rejection_has_no_store_write_or_state_replacement(self):
        self.create()
        self.cfg.MaxStoreBytes=16384
        group=self.state.Groups[0]
        for i in range(32):
            self.assertEqual(0,self.apply('alice',self.op.MARKER_CREATE,Name='Cache',Note='x'*512))
        self.assertLess(len(group.Markers),self.cfg.MaxMarkers)
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        writes=[]
        current=self.e['HCGroupState']();current.WorldName='chernarusplus';current.Revision=10
        service=SimpleNamespace(m_State=current,m_Config=self.cfg,m_LastUtc=1000,
            m_Store=SimpleNamespace(Save=lambda s:writes.append(s) or True))
        def serialize(value):
            return True,json.dumps(value,default=lambda v:vars(v)),''
        env={**self.e,'serialize':serialize,
             'GetGame':lambda:SimpleNamespace(GetWorldName=lambda:'chernarusplus'),
             'HCGroupNative':SimpleNamespace(WorldName=lambda:'chernarusplus')}
        self.assertEqual(self.code.LIMIT,execute_member(source,'Commit',env,service,self.state))
        self.assertIs(current,service.m_State)
        self.assertEqual([],writes)

    def test_invite_expiry_reaches_max_and_overflow_is_rejected_before_mutation(self):
        group=self.create()
        for now,expected in [(2147483527,0),(2147483528,self.code.INVALID)]:
            self.state.Invitations.Clear()
            before=(self.state.NextId,group.Revision)
            q=self.request(self.op.INVITE,TargetId='bob',ExpectedRevision=group.Revision)
            result=self.e['Apply'](self.state,self.cfg,q,'alice',now)
            self.assertEqual(expected,result)
            if result==0:
                self.assertEqual(2147483647,self.state.Invitations[0].ExpiresUtc)
                self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
            else:
                self.assertEqual(before,(self.state.NextId,group.Revision))
                self.assertEqual([],self.state.Invitations)

    def test_marker_deadline_boundary_and_forever_at_final_second(self):
        group=self.create()
        self.cfg.MarkerRetentionSeconds=0
        for ttl,now,expected in [(10,2147483637,0),(10,2147483638,self.code.INVALID),
                                 (2592000,2144891647,0),(2592000,2144891648,self.code.INVALID),
                                 (0,2147483647,0)]:
            group.Markers.Clear()
            before=(self.state.NextId,group.Revision)
            q=self.request(self.op.MARKER_CREATE,Name='Boundary',TtlSeconds=ttl,
                           ExpectedRevision=group.Revision)
            result=self.e['Apply'](self.state,self.cfg,q,'alice',now)
            self.assertEqual(expected,result,(ttl,now))
            if result==0:
                self.assertEqual(2147483647 if ttl else 0,group.Markers[0].ExpiresUtc)
                self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
            else:
                self.assertEqual(before,(self.state.NextId,group.Revision))
                self.assertEqual([],group.Markers)

    def test_restart_clock_accepts_legacy_zero_but_rejects_rollback_of_commit(self):
        allowed=self.e['ClockAllows']
        self.assertTrue(allowed(self.state,1000))
        self.state.LastMutationUtc=2000000001
        for now,expected in [(0,False),(2000000000,False),(2000000001,True),
                             (2147483647,True),(2147483648,False)]:
            self.assertEqual(expected,allowed(self.state,now))
        self.state.LastMutationUtc=-1
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_commit_persists_authoritative_clock_and_refuses_rollback(self):
        import copy
        self.create()
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        writes=[]
        self.state.LastMutationUtc=2000000001
        service=SimpleNamespace(m_State=self.state,m_Config=self.cfg,m_LastUtc=2000000002,
            m_Store=SimpleNamespace(Save=lambda s:writes.append(copy.deepcopy(s)) or True))
        env={**self.e,'serialize':lambda s:(True,json.dumps(s,default=vars),''),
             'GetGame':lambda:SimpleNamespace(GetWorldName=lambda:'chernarusplus')}
        candidate=copy.deepcopy(self.state)
        self.assertEqual(0,execute_member(source,'Commit',env,service,candidate))
        self.assertEqual(2000000002,writes[0].LastMutationUtc)
        service.m_LastUtc=2000000001
        self.assertEqual(self.code.STORAGE,execute_member(source,'Commit',env,service,copy.deepcopy(candidate)))
        self.assertEqual(1,len(writes))

    def test_request_rate_clock_rejects_rollback_nan_and_infinity_without_admission(self):
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        for now in (99.,math.nan,math.inf,-math.inf):
            peer=SimpleNamespace(RateWindow=100.,RateCount=0)
            service=SimpleNamespace(m_Config=self.cfg,m_GlobalWindow=100.,m_GlobalCount=0)
            env={**self.e,'GetGame':lambda:SimpleNamespace(GetTickTime=lambda:now),'HCRefuse':lambda reason:False}
            self.assertFalse(execute_member(source,'Admit',env,service,peer),now)
            self.assertEqual(0,peer.RateCount)
            self.assertEqual(0,service.m_GlobalCount)

    def test_missing_group_preferences_and_failed_start_are_reported(self):
        source=(ROOT/'4_World/Groups/HCGroupModule.c').read_text()
        messages=[]
        service=SimpleNamespace(Start=lambda c:False)
        module=SimpleNamespace(m_Config=None,m_Service=None)
        env={**self.e,'Print':messages.append,
             'HCGroupStore':SimpleNamespace(LoadSettings=lambda:None),
             'HCGroupService':lambda:service}
        self.assertFalse(execute_member(source,'IsEnabled',env,module,
                                       SimpleNamespace(EnableGroups=True)))
        self.assertTrue(messages)
        messages.clear()
        execute_member(source,'OnStart',env,module,SimpleNamespace())
        self.assertTrue(messages)
        self.assertIsNone(module.m_Service)

    def test_mismatched_replay_cannot_replace_cached_committed_result(self):
        self.create()
        sent=[]
        class RPC:
            def Write(self,value):self.value=value
            def Send(self,*args):sent.append(self.value)
        peer=SimpleNamespace(Id='alice',Session='fresh',LastRequest=1,LastReply=None,Identity=object())
        service=SimpleNamespace(m_State=self.state,Live=lambda p:True)
        env={**self.e,'ScriptRPC':RPC,'HCGroupProtocol':SimpleNamespace(RPC_REPLY=4853703)}
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        execute_member(source,'Reply',env,service,peer,1,self.code.OK,True)
        original=peer.LastReply
        execute_member(source,'Reply',env,service,peer,1,self.code.CONFLICT,False)
        self.assertIs(original,peer.LastReply)
        self.assertEqual(self.code.OK,peer.LastReply.Code)
        self.assertEqual([0,4],[r.Code for r in sent])

    def test_native_member_projection_never_publishes_dead_offline_or_forbidden_position(self):
        class Player:
            def __init__(self,pos):self.position=pos;self.alive=True
            def GetPosition(self):return self.position
            def IsAlive(self):return self.alive
        source=SimpleNamespace(Player=Player([100.,0.,100.]),online=True,gps=True)
        recipient=SimpleNamespace(Player=Player([101.,0.,100.]),online=True,gps=True)
        service=SimpleNamespace(m_Config=self.cfg,m_LastUtc=1000,
            m_Names=SimpleNamespace(Get=lambda uid:'Alice'),Peer=lambda uid:source,
            Live=lambda p:p.online,HasGPS=lambda p:p.gps,VisibilityAllows=lambda s,r:True)
        text=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        def projected():return execute_member(text,'Member',dict(self.e),service,'alice',recipient,True)
        self.assertTrue(projected().HasPosition)
        self.assertEqual(1000,projected().SampleUtc)
        for target,field in [(source.Player,'alive'),(source,'online'),(recipient.Player,'alive'),(recipient,'online'),(source,'gps'),(recipient,'gps')]:
            setattr(target,field,False)
            member=projected()
            self.assertFalse(member.HasPosition)
            self.assertEqual([0.,0.,0.],member.Position)
            self.assertEqual(0,member.SampleUtc)
            setattr(target,field,True)
        self.cfg.MapIcons=False;self.cfg.WorldIcons=False
        self.assertFalse(projected().HasPosition)
        self.cfg.WorldIcons=True;self.cfg.MaxIconDistance=10.
        recipient.Player.position=[300.,0.,300.]
        self.assertFalse(projected().HasPosition)
        self.cfg.MapIcons=True
        self.assertTrue(projected().HasPosition)

    def test_invitation_candidate_projection_never_reads_or_exposes_life_state(self):
        reads=[]
        class Player:
            def IsAlive(self):reads.append('alive');return True
            def GetPosition(self):reads.append('position');return [999.,0.,999.]
        source=SimpleNamespace(Player=Player())
        service=SimpleNamespace(m_Config=self.cfg,m_LastUtc=1000,
            m_Names=SimpleNamespace(Get=lambda uid:'Invite target'),Peer=lambda uid:source,
            Live=lambda peer:True,HasGPS=lambda peer:True)
        text=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        member=execute_member(text,'Member',dict(self.e),service,'stranger',source,False)
        self.assertEqual('stranger',member.Id)
        self.assertEqual('Invite target',member.Name)
        self.assertFalse(member.Alive)
        self.assertFalse(member.HasPosition)
        self.assertEqual([0.,0.,0.],member.Position)
        self.assertEqual(0,member.SampleUtc)
        self.assertEqual([],reads)

    def test_rename_refreshes_pending_invitation_names_only_for_its_group(self):
        self.create('alice')
        self.assertEqual(0,self.apply('alice',self.op.INVITE,TargetId='bob'))
        self.create('charlie')
        self.assertEqual(0,self.apply('charlie',self.op.INVITE,TargetId='dave'))
        self.assertEqual(0,self.apply('alice',self.op.RENAME,Name='New name'))
        self.assertEqual(['New name','Travelers'],[i.GroupName for i in self.state.Invitations])
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_invitation_validation_rejects_stale_group_name(self):
        self.create()
        self.assertEqual(0,self.apply('alice',self.op.INVITE,TargetId='bob'))
        self.state.Invitations[0].GroupName='Stale name'
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def projection_fixture(self):
        """Synthetic RPC transport only; projection runs the authored method."""
        sent=[]
        class RPC:
            def Write(self,value):self.value=value
            def Send(self,*args):sent.append(self.value)
        peer=SimpleNamespace(Id='alice',Session='fresh',LastRequest=5,
            LastReply=None,Identity=object(),Sequence=0,LastGroup=0,
            Player=SimpleNamespace(IsAlive=lambda:True))
        service=SimpleNamespace(m_State=self.state,m_Config=self.cfg,
            m_Healthy=True,m_LastUtc=1000,m_Peers=EArray(),m_Places=None,Live=lambda p:True)
        source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        env={**self.e,'ScriptRPC':RPC}
        service.SendSnapshot=lambda p,k,r:execute_member(source,'SendSnapshot',env,service,p,k,r)
        return source,env,service,peer,sent

    def test_wire3_floor_schema_defaults_and_durable_schema_stays1(self):
        self.assertEqual(3,self.e['HCGroupProtocol'].VERSION)
        for name in ('HCGroupRequest','HCGroupSnapshot','HCGroupReply'):
            self.assertEqual(3,self.e[name]().Version)
        for name in ('HCGroupSnapshot','HCGroupReply'):
            self.assertEqual(0,self.e[name]().LastMutationId)
        self.assertEqual(1,self.e['HCGroupState']().Version)
        self.assertEqual(1,self.e['HCGroupReceipt']().Version)

    def test_every_snapshot_kind_projects_floor_without_consuming_or_resetting_it(self):
        source,env,service,peer,sent=self.projection_fixture()
        for kind in (0,1,2):
            service.SendSnapshot(peer,kind,900001)
            self.assertEqual(kind,sent[-1].Kind)
            self.assertEqual(5,sent[-1].LastMutationId)
            self.assertEqual(900001,sent[-1].RequestId)
            self.assertEqual(5,peer.LastRequest)
        self.assertEqual([1,2,3],[frame.Sequence for frame in sent])

    def test_reply_projects_actual_floor_for_counterahead_conflict_and_all_errors(self):
        source,env,service,peer,sent=self.projection_fixture()
        for code in range(10):
            execute_member(source,'Reply',env,service,peer,8,code,False)
            self.assertEqual(8,sent[-1].RequestId)
            self.assertEqual(code,sent[-1].Code)
            self.assertEqual(5,sent[-1].LastMutationId)
            self.assertEqual(5,peer.LastRequest)

    def test_sync_floor_is_observation_not_ack_and_later_reply_does_not_rewrite_it(self):
        source,env,service,peer,sent=self.projection_fixture()
        branch=re.search(r'if \(request.Op == HCGroupOp.SYNC\)\s*\{',source)
        sync='void Sync(HCGroupRequest request, HCGroupPeer peer) {'+body(source,branch.end())+'}'
        request=self.request(self.op.SYNC,RequestId=900001,Session='fresh')
        execute_member(sync,'Sync',env,service,request,peer)
        frame=sent[-1]
        self.assertEqual(5,frame.LastMutationId)
        self.assertEqual(5,peer.LastRequest)
        # Explicit synthetic subsequent consumption; this test covers projection,
        # while the client worker covers delayed-frame recovery/generation.
        peer.LastRequest=6
        execute_member(source,'Reply',env,service,peer,6,self.code.OK,True)
        self.assertEqual(6,sent[-1].LastMutationId)
        self.assertEqual(5,frame.LastMutationId)
        self.assertEqual(6,peer.LastRequest)

    def test_mutation_floor_bounds_and_invalid_internal_counter_never_emits(self):
        valid=self.e['MutationIdValid']
        self.assertTrue(valid(0));self.assertTrue(valid(1000000))
        self.assertFalse(valid(-1));self.assertFalse(valid(1000001))
        source,env,service,peer,sent=self.projection_fixture()
        for counter in (0,1000000):
            peer.LastRequest=counter
            service.SendSnapshot(peer,0,900001)
            execute_member(source,'Reply',env,service,peer,8,self.code.CONFLICT,False)
            self.assertEqual([counter,counter],[frame.LastMutationId for frame in sent])
            self.assertEqual(counter,peer.LastRequest)
            sent.clear()
        for counter in (-1,1000001):
            peer.LastRequest=counter
            service.SendSnapshot(peer,0,900001)
            execute_member(source,'Reply',env,service,peer,1,self.code.CONFLICT,False)
            self.assertEqual([],sent)

    def test_marker_updates_preserve_original_deadline_as_server_time_advances(self):
        g=self.create()
        self.assertEqual(0,self.apply('alice',self.op.MARKER_CREATE,Name='Timed',TtlSeconds=100))
        marker=g.Markers[0]
        self.assertEqual(1100,marker.ExpiresUtc)
        for now in (1020,1050,1099):
            q=self.request(self.op.MARKER_UPDATE,EntityId=marker.Id,Name='Edited',
                Note='Revised',Position=[123.,0.,456.],ExpectedRevision=g.Revision)
            self.assertEqual(0,self.e['Apply'](self.state,self.cfg,q,'alice',now))
            self.assertEqual(1100,marker.ExpiresUtc)
        q=self.request(self.op.MARKER_UPDATE,EntityId=marker.Id,Name='Expired',ExpectedRevision=g.Revision)
        self.assertEqual(self.code.NOT_FOUND,self.e['Apply'](self.state,self.cfg,q,'alice',1100))
        self.assertEqual(1100,marker.ExpiresUtc)

    def test_marker_update_rejects_explicit_ttl_and_never_assigns_policy_to_forever_marker(self):
        self.cfg.MarkerRetentionSeconds=0
        g=self.create()
        self.assertEqual(0,self.apply('alice',self.op.MARKER_CREATE,Name='Forever'))
        marker=g.Markers[0]
        self.assertEqual(0,marker.ExpiresUtc)
        self.cfg.MarkerRetentionSeconds=60
        self.assertEqual(0,self.apply('alice',self.op.MARKER_UPDATE,EntityId=marker.Id,Name='Edited'))
        self.assertEqual(0,marker.ExpiresUtc)
        before=g.Revision
        for ttl in (10,-1,2592001):
            self.assertEqual(self.code.INVALID,self.apply('alice',self.op.MARKER_UPDATE,
                EntityId=marker.Id,Name='Rejected',TtlSeconds=ttl))
            self.assertEqual(0,marker.ExpiresUtc)
            self.assertEqual(before,g.Revision)

    def test_corrupt_invitation_null_or_cross_group_authority_is_refused(self):
        self.create()
        self.apply('alice',self.op.INVITE,TargetId='bob')
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        invite=self.state.Invitations[0]
        self.state.Invitations[0]=None
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))
        self.state.Invitations[0]=invite;invite.InviterId='mallory'
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))

    def test_creating_own_group_cancels_pending_other_group_invitations(self):
        self.create('alice')
        self.assertEqual(0,self.apply('alice',self.op.INVITE,TargetId='bob'))
        self.assertEqual(0,self.apply('bob',self.op.CREATE,Name='Independent'))
        self.assertEqual([],self.state.Invitations)
        self.assertTrue(self.e['StateValid'](self.state,self.cfg,'chernarusplus'))


    def test_native_rpc_authority_targeting_and_lifecycle_are_explicit(self):
        service=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        module=(ROOT/'4_World/Groups/HCGroupModule.c').read_text()
        connections=(ROOT/'5_Mission/Groups/HCGroupConnections.c').read_text()
        self.assertIn('sender.GetId()',service)
        self.assertIn('Event_OnRPC.Insert',module)
        self.assertIn('Event_OnRPC.Remove',module)
        self.assertNotRegex(service,r'\.Send\([^;]+,\s*null\s*\)')
        for hook in ('OnClientNewEvent','OnClientReadyEvent','OnClientReconnectEvent','OnClientDisconnectedEvent'):
            self.assertIn(hook,connections)

    def test_immutable_store_reads_are_bounded_and_latest_corruption_has_no_fallback(self):
        store=(ROOT/'4_World/Groups/HCGroupStore.c').read_text()+(ROOT/'3_Game/Groups/HCGroupIO.c').read_text()
        self.assertIn('ReadFile(handle, text, limit + 1)',store)
        self.assertIn('intent_',store)
        self.assertIn('commit_',store)
        self.assertIn('state_',store)
        self.assertIn('if (FileExist(path)) return false',store)
        self.assertNotIn('JsonFileLoader<HCGroupState>.LoadFile',store)
        self.assertIn('m_Fault = true',store)


if __name__=='__main__': unittest.main()


def load_tests(loader, standard_tests, pattern):
    # Keep the stable groups BDD binding while extending its behavior coverage.
    from tests.unit import test_v1_groups
    standard_tests.addTests(loader.loadTestsFromModule(test_v1_groups))
    return standard_tests
