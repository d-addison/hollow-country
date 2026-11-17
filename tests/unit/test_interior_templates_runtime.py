"""Synthetic translated Enforce checks; never DayZ geometry/runtime evidence."""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray, body
from tests.unit.test_interior_measured_catalog import EMap as BaseMap, statements
from tests.unit.build_identity_support import translate as build_identity

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors'
METADATA = {"Synthetic": True}


class EMap(BaseMap):
    def __missing__(self, key): return 0
    def Get(self, key): return self.get(key, 0)
    def GetKey(self, index): return list(self)[index]
    def GetElement(self, index): return list(self.values())[index]
    def Set(self, key, value): self[key] = value


class Array(EArray):
    def Sort(self): self.sort()


def authored(include_read=False):
    """Translate authored control flow, replacing only native I/O/config boundaries."""
    files = [SRC / name for name in ('HCInteriorTemplatesData.c',
             'HCInteriorTemplatesStrict.c', 'HCInteriorTemplates.c',
             'HCInteriorTemplatePlacement.c')]
    sources = '\n'.join(path.read_text() for path in files)
    env = dict(EArray=Array, EMap=EMap, NS=NS, ord=ord, len=len)
    for match in re.finditer(r'class (HC\w+)\s*\{', files[0].read_text()):
        fields = re.findall(r'^\s*(?:ref )?([\w<>, ]+?) (\w+)(?:\s*=\s*([^;]+))?;',
                            body(files[0].read_text(), match.end()), re.M)
        def make(fields=fields):
            result = NS()
            for typ, key, initial in fields:
                value = EArray() if 'array<' in typ else EMap() if 'map<' in typ else (
                    json.loads(initial) if initial else
                    {'string': '', 'int': 0, 'float': 0., 'bool': False}.get(typ))
                setattr(result, key, value)
            return result
        env[match[1]] = make
    sources = re.sub(r'//[^\n]*', '', sources)
    for match in re.finditer(r'static ([\w<> ]+?) (\w+)\(([^)]*)\)\s*\{', sources):
        name = match[2]
        if name in {'EngineClasses', 'Spawn', 'Available', 'Schedule'} or (name == 'Read' and not include_read):
            continue  # Native byte/config/spawn boundaries are explicit in fixture().
        args = [arg.split('=')[0].strip().split()[-1] + ('='+arg.split('=')[1].strip() if '=' in arg else '') for arg in re.sub(r'<[^>]*>', '', match[3]).split(',') if arg.strip()]
        lines = [f'def {name}({", ".join(args)}):',
                 '    global s_Attempted, s_Loaded, s_Index, s_Bytes, s_Files, s_Reason, s_Placed, s_Capped, s_Started, s_ResolveReason, s_MaxProps']
        indent = 1
        for token in statements(body(sources, match.end())):
            token = token.strip()
            if not token or token == ';': continue
            if token == '{': indent += 1; continue
            if token == '}': indent -= 1; continue
            literals = []
            def protect(m):
                literals.append(m[0]); return f'__LITERAL_{len(literals)-1}__'
            token = re.sub(r'"(?:\\.|[^"\\])*"', protect, token)
            token = re.sub(r'JsonFileLoader<(\w+)>\.LoadData\(', r'NativeLoad("\1", ', token)
            token = re.sub(r'int (\w+) = ReadFile\(([^,]+), (\w+), ([^)]+)\)', r'\1, \3 = NativeRead(\2, \4)', token)
            token = re.sub(r'new array<[^;]+>\(\)', 'EArray()', token)
            token = re.sub(r'new (HC\w+)(?:\(\))?', r'\1()', token)
            token = re.sub(r'(?:array<[^>]+>|HC\w+|int|float|bool|string|vector|Object|FileHandle)\s+(?=\w+\s*=)', '', token)
            bare = re.fullmatch(r'(int|float|bool|string|vector|Object|HC\w+) (\w+)', token)
            if bare:
                token = bare[2] + ' = ' + {'int': '0', 'float': '0.', 'bool': 'False', 'string': "''", 'vector': '[0.,0.,0.]'}.get(bare[1], 'None')
            token = re.sub(r'([\w.]+)\.Get\(([^)]+)\)', r'\1[\2]', token)
            token = re.sub(r'(\w+)\.ToAscii\(\)', r'ord(\1)', token)
            token = re.sub(r'([\w.]+)\.Substring\(([^,]+), ([^)]+)\)', r'\1[\2:(\2)+(\3)]', token)
            token = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', token)
            token = re.sub(r'(s_Refused.GetElement\([^)]+\))\.ToString\(\)', r'str(\1)', token)
            token = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', token)
            split = re.fullmatch(r'(\w+)\.Split\(([^,]+), (\w+)\)', token)
            if split: token = split[3] + '.extend(part for part in ' + split[1] + '.split(' + split[2] + ') if part)'
            lower = re.fullmatch(r'(\w+)\.ToLower\(\)', token)
            if lower: token = lower[1] + ' = ' + lower[1] + '.lower()'
            token = token.replace('&&', ' and ').replace('||', ' or ')
            token = re.sub(r'!(?!=)', 'not ', token)
            for old, new in [('true','True'), ('false','False'), ('null','None')]:
                token = re.sub(r'\b'+old+r'\b', new, token)
            if token.startswith(('if (', 'while (')):
                prefix, condition = token.split(' (', 1); token = prefix + ' ' + condition[:-1] + ':'
            elif token.startswith('foreach ('):
                loop = re.fullmatch(r'foreach \(\w+ (\w+) : (.+)\)', token)
                if not loop: raise AssertionError(token)
                token = f'for {loop[1]} in {loop[2]}:'
            elif token == 'else': token += ':'
            for index, literal in enumerate(literals): token = token.replace(f'__LITERAL_{index}__', literal)
            lines.append('    '*indent + token)
        exec(compile('\n'.join(lines), 'authored-templates:'+name, 'exec'), env)
    env.update(HCInteriorTemplates=NS(**env), HCInteriorTemplatesStrict=NS(**env))
    # Proxies need live globals, never copies of published pack state.
    return env


def pack():
    pin = 'a'*64
    index = dict(SchemaVersion=2, Kind='hc-interior-templates', WorldName='chernarusplus',
                 Build='1.30.164289', PackId='b'*32, SourcePin=pin, Frame='rot90', Provisional=True,
                 Sources={key:pin for key in ('mapgroupproto','mapgrouppos','types','cfgspawnabletypes',
                          'cfglimitsdefinition','census-'+'c'*32,'generator','search-generator')},
                 ClassFiles=[dict(File='classes-000.json',Sha256=pin)],
                 TemplateFiles=[dict(File='t-0000.json',BuildingClass='Land_House_1W01',Sha256=pin)],
                 FurnishFiles=[dict(File='furnish-000.json',Sha256=pin)],
                 GroupFiles=[dict(File='search-groups-000.json',Sha256=pin)])
    box = dict(Min=[-5,-1,-5], Max=[5,3,5])
    template = dict(SchemaVersion=2, BuildingClass='Land_House_1W01', TemplateId='synthetic-v1',
                    Box=box, Evidence=[dict(Kind='native-room-survey-v1',RunId='c'*32,Sha256=pin)],
                    Rooms=[dict(Id=1,Label='room',Min=[-4,-.5,-4],Max=[4,2.5,4],
                                Anchor=[0,0,0],FloorY=0,Cells=16)],
                    KeepOuts=[dict(Kind='door',Index=0,Min=[3,-.5,3],Max=[4,2,4])],
                    PropSlots=[dict(Id=1,Room=1,Type='StaticObj_Furniture_case_a',Position=[-2,0,-2],
                                    Orientation=[90,0,0],Bounds=dict(Min=[-2.5,0,-2.5],Max=[-1.5,2,-1.5]),History=['family'])],
                    SearchSites=[dict(Id=1,Room=1,Center=[1,1,1],Radius=.8,Source='lootshelves',Points=[0],Groups=['g-0000'])])
    return {'index.json':index, 'classes-000.json':dict(SchemaVersion=2,Chunk=0,Rows=[dict(
                BuildingClass='Land_House_1W01',Rooms='covered',Furniture='covered',Search='covered')]),
            't-0000.json':template, 'furnish-000.json':dict(SchemaVersion=2,Chunk=0,Rows=[dict(
                Slot=0,BuildingClass='Land_House_1W01',Position=[100,0,100],Yaw=15,Props=[1],History='family')]),
            'search-groups-000.json':dict(SchemaVersion=2,Chunk=0,Groups=[dict(Id='g-0000',Usages=['Village'],
                Container='lootshelves',Categories=['tools'],Tags=['shelves'],Items=['Hammer'])])}


class SyntheticHouse:
    def __init__(self, position=(100,0,100), orientation=(15,0,0)):
        self.position=list(position); self.orientation=list(orientation)
    def GetType(self): return 'Land_House_1W01'
    def GetPosition(self): return self.position
    def GetOrientation(self): return self.orientation
    def ModelToWorld(self, local): return [a+b for a,b in zip(self.position,local)]


def fixture(values=None):
    assert METADATA['Synthetic']
    values = pack() if values is None else values
    raw = {name:json.dumps(value) for name,value in values.items()}
    env = authored(); reads=[]; logs=[]; objects=EArray([SyntheticHouse()]); created=EArray()
    def read(path, kind):
        reads.append(path)
        value = raw.get(path.rsplit('/',1)[-1], '')
        return value if 0 < len(value.encode()) <= 32767 else ''
    def native_load(typ, content, target, error):
        try:
            value=json.loads(content)
            def convert(obj, key=''):
                if isinstance(obj,dict):
                    if key=='Sources': return EMap(obj)
                    return NS(**{k:convert(v,k) for k,v in obj.items()})
                if isinstance(obj,list): return EArray(convert(v) for v in obj)
                return obj
            target.__dict__.update(vars(convert(value))); return True
        except ValueError: return False
    game=NS(GetWorldName=lambda:'chernarusplus',ConfigIsExisting=lambda path:True,
            GetObjectsAtPosition3D=lambda point,radius,found,cargos:found.extend(objects))
    env.update(Read=read, NativeLoad=native_load, EngineClasses=lambda:EArray(['Land_House_1W01']),
        GetGame=lambda:game, HCBuildIdentity=build_identity(),FileExist=lambda path:False,
        HCInteriorMeasuredCatalog=NS(MeasuredClaimedClass=lambda:''),
        HCSearchRules=NS(TextValid=lambda v,n:isinstance(v,str) and 0<len(v)<=n and bool(re.fullmatch('[a-zA-Z0-9_.:+/=-]+',v)),
                         PinValid=lambda v:isinstance(v,str) and bool(re.fullmatch('[0-9a-f]{64}',v))),
        HCInteriorRules=NS(TransformKey=lambda p,o:"_".join(str(round(v*100)) for v in p+o),SaneVector=lambda v,n:all(-n<=x<=n for x in v),PlacementAdmitted=lambda:True),
        Vector=lambda x,y,z:[x,y,z], vector=NS(DistanceSq=lambda a,b:sum((x-y)**2 for x,y in zip(a,b))),
        Math=NS(Min=min,Max=max), Print=logs.append,
        ROOT_PATH='$profile:HollowCountry/templates/',
        s_Attempted=False,s_Loaded=False,s_Index=None,s_Bytes=0,s_Files=0,s_Reason='',
        s_Classes=EArray(),s_Templates=EArray(),s_Groups=EArray(),s_Furnish=EArray(),
        s_Placed=0,s_Capped=0,s_Refused=EMap(),s_Houses=EArray(),s_Started=False,s_ResolveReason='',s_MaxProps=5,
        Available=lambda module,point,orientation,typ:True,
        Spawn=lambda typ,point,orientation:NS(Type=typ,Position=point,Orientation=orientation),
        Schedule=lambda props:None,
        HCInteriorCatalog=NS(SearchType=lambda typ:typ=='StaticObj_Furniture_case_a'))
    return env, raw, reads, logs, objects, created


class InteriorTemplatesRuntimeTests(unittest.TestCase):
    def load(self, values=None, legacy=None):
        result=fixture(values); result[0]['EnsureLoaded'](legacy); return result

    def test_valid_pack_publishes_exact_reader_api_once(self):
        e,raw,reads,logs,objects,created=self.load()
        self.assertTrue(e['Loaded']())
        self.assertEqual('covered',e['ClassRow']('Land_House_1W01').Furniture)
        self.assertEqual('synthetic-v1',e['Template']('Land_House_1W01').TemplateId)
        self.assertEqual(['Hammer'],e['Group']('g-0000').Items)
        self.assertEqual('a'*64,e['SourcePin']())
        first=list(reads); e['EnsureLoaded'](None); self.assertEqual(first,reads)
        self.assertIsNone(e['ClassRow']('absent')); self.assertIsNone(e['Template']('absent'))
        self.assertIsNone(e['Group']('absent'))

    def assert_refused(self, result):
        e=result[0]
        self.assertFalse(e['Loaded']())
        self.assertIsNone(e['ClassRow']('Land_House_1W01'))
        self.assertIsNone(e['Template']('Land_House_1W01'))
        self.assertIsNone(e['Group']('g-0000')); self.assertEqual('',e['SourcePin']())
        self.assertTrue(result[3])

    def test_unknown_duplicate_missing_keys_refuse_before_native_parse(self):
        for name in pack():
            for mutation in ('unknown','missing','duplicate'):
                with self.subTest(name=name,mutation=mutation):
                    result=fixture(); e,raw=result[:2]
                    if mutation=='unknown': raw[name]=raw[name][:-1]+',"Unknown":1}'
                    if mutation=='missing':
                        value=json.loads(raw[name]); del value['SchemaVersion']; raw[name]=json.dumps(value)
                    if mutation=='duplicate': raw[name]=raw[name][:-1]+',"SchemaVersion":2}'
                    e['EnsureLoaded'](None); self.assert_refused(result)

    def test_oversize_and_non_ascii_file_refuse(self):
        for name in pack():
            for value in (' '*32768,'{"SchemaVersion":2,"é":1}'):
                result=fixture(); result[1][name]=value; result[0]['EnsureLoaded'](None)
                self.assert_refused(result)

    def test_chunk_gap_and_pin_mismatch_refuse(self):
        values=pack(); values['index.json']['ClassFiles'][0]['File']='classes-001.json'
        self.assert_refused(self.load(values))
        values=pack(); values['t-0000.json']['Evidence'][0]['Sha256']='d'*64
        self.assert_refused(self.load(values))
        values=pack(); values['index.json']['SourcePin']='broken'
        self.assert_refused(self.load(values))

    def test_provisional_build_and_denominator_refuse(self):
        for key,value in [('Provisional',False),('SchemaVersion',1),('Build','other')]:
            values=pack(); values['index.json'][key]=value; self.assert_refused(self.load(values))
        result=fixture(); result[0]['EngineClasses']=lambda:EArray(['Land_House_1W01','Land_Other'])
        result[0]['EnsureLoaded'](None); self.assert_refused(result)

    def test_legacy_only_load_does_not_touch_legacy_files(self):
        e,raw,reads,logs,objects,created=self.load({})
        self.assertFalse(e['Loaded']()); self.assertEqual(['$profile:HollowCountry/templates/index.json'],reads)
        module=(SRC/'HCInteriorModule.c').read_text()
        self.assertIn('HCInteriorJson<HCInteriorConfig>.Load("$profile:HollowCountry/interiors.json", m_Config)',module)
        self.assertIn('HCInteriorMeasuredCatalog.MeasuredEnsureLoaded()',module)

    def test_legacy_claim_conflict_refuses_with_reason(self):
        legacy=NS(Candidates=EArray([NS(Type='Land_House_1W01')]))
        result=self.load(legacy=legacy); self.assert_refused(result)
        self.assertIn('rooms_conflict',result[0]['s_Reason'])

    def place(self, result, overall=1500, per_house=5):
        e,raw,reads,logs,objects,created=result
        settings=NS(MaxFurnishedProps=overall,MaxPropsPerInterior=per_house)
        module=NS()
        module.PlaceCandidate=lambda row,cfg:e['PlaceRow'](module,row,cfg,created)
        e['Place'](module,settings,created)
        return e,created

    def test_props_cap_holds_and_never_reads_during_placement(self):
        result=self.load(); reads=list(result[2]); e,created=self.place(result,overall=0)
        self.assertEqual(0,len(created)); self.assertEqual(1,e['s_Capped'])
        self.assertEqual(reads,result[2])
        result=self.load(); e,created=self.place(result,overall=1)
        self.assertEqual(1,len(created)); self.assertEqual(1,e['s_Placed'])
        self.assertEqual([98,0,98],created[0].Position)

    def test_tilted_and_ambiguous_live_houses_refuse(self):
        for objects,reason in [([SyntheticHouse(orientation=(15,.01,0))],'tilted'),
                               ([SyntheticHouse(),SyntheticHouse(position=(100.5,0,100))],'ambiguous')]:
            result=self.load(); result[4][:]=objects; e,created=self.place(result)
            self.assertEqual(0,len(created)); self.assertEqual(1,e['s_Refused'][reason])

    def test_door_keepout_and_clearance_block_slot(self):
        for minimum,maximum in [([-2.1,0,-2.1],[-1.9,2,-1.9]),
                                ([-1.2,0,-2.5],[-.5,2,-1.5])]:
            values=pack(); values['t-0000.json']['KeepOuts'][0].update(Min=minimum,Max=maximum)
            self.assert_refused(self.load(values))

    def test_nested_unknown_and_duplicate_keys_refuse(self):
        for needle in ('"FloorY": 0','"Radius": 0.8','"Sha256": "'+'a'*64+'"'):
            result=fixture(); name='t-0000.json'; result[1][name]=result[1][name].replace(needle,needle+', '+needle,1)
            result[0]['EnsureLoaded'](None); self.assert_refused(result)

    def test_model_bounds_history_and_group_bindings_are_strict(self):
        for mutate in (lambda t:t['PropSlots'][0]['Bounds']['Min'].__setitem__(0,-8),
                       lambda t:t['PropSlots'][0].__setitem__('History',['invented']),
                       lambda t:t['SearchSites'][0].__setitem__('Groups',['missing'])):
            values=pack(); mutate(values['t-0000.json']); self.assert_refused(self.load(values))


    def test_actual_bounded_reader_rejects_count_mismatch_and_reads_cap_plus_one(self):
        for count,content,accepted in [(2,'{}',True),(3,'{}',False),(0,'',False),
                                       (32768,' '*32768,False)]:
            e=authored(include_read=True); lengths=[]; closed=[]
            e.update(OpenFile=lambda p,m:7,CloseFile=closed.append,
                FileMode=NS(READ=0),Print=lambda text:None,
                NativeRead=lambda handle,length:(lengths.append(length) or count,content))
            self.assertEqual(content if accepted else '',e['Read']('synthetic','index'))
            self.assertEqual([32768],lengths); self.assertEqual([7],closed)

    def test_read_totals_are_refused_before_publication(self):
        for key,value in [('s_Files',610),('s_Bytes',20971520)]:
            result=fixture(); e=result[0]; e[key]=value
            self.assertEqual('',e['ReadStrict']('index.json','index','index'))
            self.assert_refused(result)

    def test_template_slot_count_obeys_setting(self):
        result=fixture(); result[0]['EnsureLoaded'](None,0)
        self.assert_refused(result)

    def test_measured_claim_and_production_rooms_conflict(self):
        result=fixture(); e=result[0]
        e['HCInteriorMeasuredCatalog'].MeasuredClaimedClass=lambda:'Land_House_1W01'
        e['EnsureLoaded'](None); self.assert_refused(result)
        self.assertEqual('rooms_conflict',e['s_Reason'])
        result=fixture(); e=result[0]
        e['FileExist']=lambda path:path.endswith('/Infected/production-rooms.json')
        e['EnsureLoaded'](None); self.assert_refused(result)
        self.assertEqual('rooms_conflict',e['s_Reason'])

    def test_per_house_cap_and_startup_once(self):
        values=pack(); second=copy.deepcopy(values['t-0000.json']['PropSlots'][0]); second['Id']=2
        second['Position']=[0,0,-2]; second['Bounds']=dict(Min=[-.5,0,-2.5],Max=[.5,2,-1.5])
        values['t-0000.json']['PropSlots'].append(second)
        values['furnish-000.json']['Rows'][0]['Props']=[1,2]
        result=self.load(values); e,created=self.place(result,per_house=1)
        self.assertEqual((1,1),(len(created),e['s_Capped']))
        self.place(result,per_house=1); self.assertEqual(1,len(created))

    def test_failed_pack_cannot_retry_or_publish_partial_rows(self):
        result=fixture(); e,raw=result[:2]
        original=raw['furnish-000.json']; raw['furnish-000.json']='{}'
        e['EnsureLoaded'](None); self.assert_refused(result)
        first=list(result[2]); raw['furnish-000.json']=original
        e['EnsureLoaded'](None); self.assertEqual(first,result[2]); self.assert_refused(result)

    def test_overall_cap_includes_already_owned_pilot_props(self):
        result=self.load(); result[5].append(NS(Type='synthetic-existing-pilot'))
        e,created=self.place(result,overall=1)
        self.assertEqual(1,len(created)); self.assertEqual(1,e['s_Capped'])

    def invoke_extension(self, name, module, settings=None, index=0, events=None):
        from tests.unit.test_group_server import execute_member
        source=(SRC/'HCInteriorTemplatesModule.c').read_text()
        source=source.replace('super.OnStart(settings)', 'self.LegacyStart(settings)')
        source=source.replace('super.PlaceCandidate(index)', 'self.LegacyPlace(index)')
        source=source.replace('s_Instance', 'self.s_Instance').replace('this', 'self')
        source=source.replace('!IsEnabled(settings)', '!self.IsEnabled(settings)')
        e=dict(GetGame=lambda:NS(IsServer=lambda:True),Math=NS(Min=min),
            Print=lambda text:None,HCInteriorMeasuredCatalog=NS(MeasuredEnsureLoaded=lambda:None),
            HCInteriorTemplates=NS(EnsureLoaded=lambda legacy,cap:events.append(('load',legacy,cap)),Loaded=lambda:True),
            HCInteriorTemplatePlacement=NS(Place=lambda *args:events.append(('place',))))
        if name=='OnStart': return execute_member(source,name,e,module,settings)
        return execute_member(source,name,e,module,index)

    def test_template_startup_runs_without_legacy_config_and_preserves_pilot_entry(self):
        events=[]; settings=NS(MaxFurnishedProps=1500,MaxPropsPerInterior=5)
        module=NS(s_Instance=None,m_Config=None,m_Objects=EArray(),IsEnabled=lambda cfg:True,
                  LegacyStart=lambda cfg:events.append(('legacy',)))
        self.invoke_extension('OnStart',module,settings,events=events)
        self.assertEqual([('legacy',),('load',None,5),('place',)],events)
        self.assertIs(module,module.s_Instance)

    def test_legacy_placement_also_obeys_overall_cap(self):
        calls=[]
        module=NS(m_FurnishedLimit=3,m_PropLimit=2,m_Objects=EArray([object(),object()]),
                  LegacyPlace=calls.append)
        self.invoke_extension('PlaceCandidate',module,index=0)
        self.assertEqual([],calls)
        module.m_FurnishedLimit=4
        self.invoke_extension('PlaceCandidate',module,index=0)
        self.assertEqual([0],calls)

    def test_duplicate_furnish_instance_with_different_yaw_refuses_pack(self):
        values=pack(); duplicate=copy.deepcopy(values['furnish-000.json']['Rows'][0])
        duplicate.update(Slot=1,Yaw=30)
        values['furnish-000.json']['Rows'].append(duplicate)
        self.assert_refused(self.load(values))

    def test_same_live_house_cannot_bypass_per_house_cap_with_nearby_rows(self):
        values=pack(); duplicate=copy.deepcopy(values['furnish-000.json']['Rows'][0])
        duplicate.update(Slot=1,Position=[100.5,0,100])
        values['furnish-000.json']['Rows'].append(duplicate)
        result=self.load(values); e,created=self.place(result,per_house=1)
        self.assertEqual(1,len(created)); self.assertEqual(1,e['s_Refused']['duplicate_house'])

    def with_items(self, items):
        values=pack(); values['search-groups-000.json']['Groups'][0]['Items']=items; return values

    def test_group_items_need_not_be_presorted(self):
        e=self.load(self.with_items(['Hammer','Axe']))[0]
        self.assertTrue(e['Loaded']())
        self.assertEqual(['Hammer','Axe'],list(e['Group']('g-0000').Items))

    def test_duplicate_group_items_refuse(self):
        self.assert_refused(self.load(self.with_items(['Hammer','Axe','Hammer'])))

    def test_group_items_cap_is_1024(self):
        items=['Item%04d' % index for index in range(1024)]
        self.assertTrue(self.load(self.with_items(items))[0]['Loaded']())
        self.assert_refused(self.load(self.with_items(items+['Item9999'])))

    def test_door_gap_of_at_least_point_six_metres_is_admitted(self):
        for minimum,maximum in [([-.9,0,-2.5],[0,2,-1.5]),
                                ([-1.05,0,-1.05],[0,2,0])]:
            values=pack(); values['t-0000.json']['KeepOuts'][0].update(Min=minimum,Max=maximum)
            result=self.load(values)
            self.assertTrue(result[0]['Loaded'](),result[3])
