"""Synthetic translated Enforce checks; never DayZ geometry/runtime evidence.

#138 TDD (2026-11-18): test_building_templates_keep_placements_and_refusals_with_one_resolve_query
RED: AssertionError: 1 != 3 : same building must share one native resolve query.
RED/GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_interior_templates_runtime.InteriorTemplatesRuntimeTests.test_building_templates_keep_placements_and_refusals_with_one_resolve_query -v
GREEN also covers bounded eviction/reset, duplicate-house and unchanged refusal snapshots.
"""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray, body
from tests.unit.test_interior_measured_catalog import EMap as BaseMap, statements
from tests.unit.build_identity_support import translate as build_identity
from tests.unit.test_tilt_rule import tilt_rules
from tools.package.interior_catalog import SEARCH_TYPES

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors'
METADATA = {"Synthetic": True}


class EMap(BaseMap):
    def __missing__(self, key): return 0
    def Get(self, key): return self.get(key, 0)
    def GetKey(self, index): return list(self)[index]
    def GetElement(self, index): return list(self.values())[index]
    def Set(self, key, value): self[key] = value
    def Clear(self): self.clear()


class RefMap(EMap):
    def __missing__(self, key): return None
    def Get(self, key): return self.get(key)


class Array(EArray):
    def Sort(self): self.sort()
    def Set(self, index, value): self[index] = value


def authored():
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
        if name in {'EngineHouse', 'Spawn', 'Available', 'Schedule'}:
            continue  # Native byte/config/spawn boundaries are explicit in fixture().
        args = [arg.split('=')[0].strip().split()[-1] + ('='+arg.split('=')[1].strip() if '=' in arg else '') for arg in re.sub(r'<[^>]*>', '', match[3]).split(',') if arg.strip()]
        args = [arg.replace("=false", "=False").replace("=true", "=True") for arg in args]
        lines = [f'def {name}({", ".join(args)}):',
                 '    global s_Attempted, s_Loaded, s_Index, s_Bytes, s_Files, s_Reason, s_Placed, s_Capped, s_Started, s_ResolveReason, s_MaxProps, s_Root, s_Source, s_Steps, s_LastType, s_LastQuery, s_ResolveNext, s_Job, s_LoadPhase, s_LoadChunk, s_LoadStart, s_LoadCheck, s_FurnishProps']
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
            token = re.sub(r'vector (\w+)\[2\]', r'\1 = [None, None]', token)
            token = re.sub(r'(?:array<[^>]+>|HC\w+|int|float|bool|string|vector|Object|FileHandle)\s+(?=\w+\s*=)', '', token)
            bare = re.fullmatch(r'(int|float|bool|string|vector|Object|HC\w+) (\w+)', token)
            if bare:
                token = bare[2] + ' = ' + {'int': '0', 'float': '0.', 'bool': 'False', 'string': "''", 'vector': '[0.,0.,0.]'}.get(bare[1], 'None')
            token = re.sub(r'([\w.]+)\.Get\(([^)]+)\)', r'\1[\2]', token)
            token = re.sub(r'(\w+)\.ToAscii\(\)', r'ord(\1)', token)
            # Enforce Substring returns at most 8191 characters (observed under Wine, diag-json-1:
            # a 25 KB class chunk reached LoadData as exactly 8191), so the translation caps it too.
            token = re.sub(r'([\w.]+)\.Substring\(([^,]+), ([^)]+)\)', r'\1[\2:(\2)+min((\3), 8191)]', token)
            token = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', token)
            token = re.sub(r'(s_Refused.GetElement\([^)]+\))\.ToString\(\)', r'str(\1)', token)
            token = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', token)
            token = re.sub(r'([\w.]+)\.ToString\(false\)', r'" ".join(str(component) for component in \1)', token)
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
    # Issue #138 sub-timer step indices are plain static int constants of the placement class.
    env.update({m[1]: int(m[2]) for m in re.finditer(r'static const int (\w+) = (\d+);', sources)})
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


def fixture(values=None, staged=False, connect_pack=True):
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
            GetObjectsAtPosition3D=lambda point,radius,found,cargos:found.extend(objects),
            GetPlayers=lambda players:None, GetTime=lambda:123)  # no players online: placement is never deferred
    def synthetic_spawn(typ, point, orientation):
        # Explicit native boundary: invented dimensions, never installed-model evidence.
        def clipping(box): box[:]=[[-.5,0,-.3],[.5,2,.3]]
        return NS(Type=typ,Position=point,Orientation=orientation,GetType=lambda:typ,ClippingInfo=clipping)
    env.update(Read=read, NativeLoad=native_load, EngineHouse=lambda cls:cls=='Land_House_1W01',
        GetGame=lambda:game, HCBuildIdentity=build_identity(),FileExist=lambda path:False,
        HCInteriorMeasuredCatalog=NS(MeasuredClaimedClass=lambda:''),
        HCSearchRules=NS(TextValid=lambda v,n:isinstance(v,str) and 0<len(v)<=n and bool(re.fullmatch('[a-zA-Z0-9_.:+/=-]+',v)),
                         PinValid=lambda v:isinstance(v,str) and bool(re.fullmatch('[0-9a-f]{64}',v))),
        HCInteriorRules=NS(**vars(tilt_rules()), TransformKey=lambda p,o:"_".join(str(round(v*100)) for v in p+o),SaneVector=lambda v,n:all(-n<=x<=n for x in v),PlacementAdmitted=lambda:True),
        Vector=lambda x,y,z:[x,y,z], vector=NS(DistanceSq=lambda a,b:sum((x-y)**2 for x,y in zip(a,b))),
        Math=NS(Min=min,Max=max), Print=logs.append, TickCount=lambda previous:12345,  # SYNTHETIC raw tick delta
        ROOT_PATH='$profile:HollowCountry/templates/',
        HCProfileDefaults=NS(PBO_ROOT='HollowCountry/data/defaults/',
            Resolve=lambda relative, root:'$profile:HollowCountry/'+relative),
        s_Root='',s_Source='',
        HCV1Admission=NS(Refused=lambda feature,gate,reason:'[HollowCountry] V1 admission feature='+feature+' preference=on gate='+gate+' qualified=0 result=refused: '+reason),
        s_Attempted=False,s_Loaded=False,s_Index=None,s_Bytes=0,s_Files=0,s_Reason='',
        s_Classes=EArray(),s_Templates=EArray(),s_Groups=EArray(),s_Furnish=EArray(),
        s_ClassIndex=RefMap(),s_TemplateIndex=RefMap(),s_GroupIndex=RefMap(),s_TemplatePins=EMap(),
        s_FurnishSlots=EMap(),s_FurnishInstances=EMap(),s_FurnishProps=0,s_LoadCheck=0,
        s_Placed=0,s_Capped=0,s_Refused=EMap(),s_Houses=EArray(),s_Started=False,s_ResolveReason='',s_MaxProps=5,
        s_BoxLogged=Array(), s_Deferred=Array(), s_DeferredNext=0,
        s_ResolveCache=Array(), s_ResolveNext=0,
        # SYNTHETIC sub-timer sink (the authored HCStepTimer is exercised in test_hc_unit_budget).
        # This translator renders 'new HCStepTimer("Interiors")' as 'HCStepTimer()("Interiors")'.
        s_Steps=None, s_LastType='', s_LastQuery=0, HCStepTimer=lambda *args:lambda *owner:NS(HCDefine=lambda name:0,
            HCAdd=lambda step,ticks:None, HCItem=lambda kind,ticks:None, HCDeferred=lambda ticks:None,
            HCEndTick=lambda ticks:None),
        Available=lambda module,point,orientation,typ:True,
        Spawn=synthetic_spawn,
        Schedule=lambda props:None,
        HCInteriorCatalog=NS(SearchType=lambda typ:typ in SEARCH_TYPES))
    if connect_pack:
        from tests.unit.test_hc_template_pack import pack_reader, SyntheticBudget
        env.update(reads=reads, logs=logs)
        pack_reader(raw, existing=env)
        env.update(s_Job=env['HCInteriorPackJob'](), s_LoadPhase=0, s_LoadChunk=0, s_LoadStart=0)
        if not staged:
            # Existing tests inspect completed admission; explicitly simulate ticks.
            begin = env['EnsureLoaded']
            def load(legacy, cap=5):
                begin(legacy, cap)
                for _ in range(6000):
                    if env['s_Loaded'] or env['s_Reason']: break
                    env['HCLoadStep'](legacy, SyntheticBudget(True))
                else: raise AssertionError('synthetic pack admission did not finish')
            env['EnsureLoaded'] = load
    return env, raw, reads, logs, objects, created


class InteriorTemplatesRuntimeTests(unittest.TestCase):
    def test_large_pack_phase_boundaries_obey_budget_and_lookups_do_not_scan(self):
        from tests.unit.test_hc_template_pack import SyntheticBudget
        env = fixture(staged=True)[0]
        env['EnsureLoaded'](None)
        visits = []
        class CountedArray(Array):
            def __iter__(self):
                for row in super().__iter__():
                    visits.append(row)
                    yield row
        # Explicit synthetic maximum denominator; no claim about native geometry.
        env['s_Classes'] = CountedArray(NS(BuildingClass='Land_Synthetic_%04d' % n,
            Rooms='unmeasured', Furniture='unmeasured', Search='unmeasured') for n in range(2048))
        env['EngineHouse'] = lambda cls: True
        env['s_LoadChunk'] = 1  # class chunk consumed, phase boundary next
        status = env['HCLoadStep'](None, SyntheticBudget(False))
        self.assertEqual(0, len(visits), 'exhausted phase boundary scanned 2048 classes')
        self.assertEqual(1, status)
        self.assertEqual(0, env['s_LoadPhase'])
        # Coverage is a retained one-row step even with 512 templates present.
        env['s_LoadPhase'] = 2
        env['s_LoadChunk'] = 1
        env['s_Templates'] = CountedArray(NS(BuildingClass='Land_Other_%04d' % n) for n in range(512))
        visits.clear()
        env['HCLoadStep'](None, SyntheticBudget(True))
        self.assertLessEqual(len(visits), 1, 'coverage step exceeded one row')
        visits.clear()
        before_check = env['s_LoadCheck']
        env['HCLoadStep'](None, SyntheticBudget(True))
        self.assertEqual(before_check + 1, env['s_LoadCheck'])
        self.assertLessEqual(len(visits), 1, 'coverage scanned classes or templates')
        for settings, expected in ((None, 8), (NS(TemplateLoadStepsPerTick=0), 8),
                                   (NS(TemplateLoadStepsPerTick=1), 1), (NS(TemplateLoadStepsPerTick=65), 8)):
            self.assertEqual(expected, env['HCLoadStepLimit'](settings))
        # A missing group in the maximum synthetic group collection uses the index.
        env['s_Groups'] = CountedArray(NS(Id='g-%05d' % n) for n in range(32768))
        visits.clear()
        self.assertFalse(env['FindGroup']('missing'))
        self.assertEqual([], visits, 'group lookup scanned 32768 groups')

    def test_module_tick_finishes_admission_and_stop_cancels_pending_load(self):
        from tests.unit.test_group_server import execute_member
        from tests.unit.test_hc_template_pack import SyntheticBudget
        source = (SRC / 'HCInteriorTemplates.c').read_text()
        # Before integration, execute the existing tick: it never advances a pack.
        if 'modded class HCInteriorsModule' not in source:
            source = (SRC / 'HCInteriorTemplatesModule.c').read_text()
        # The member translator supports primitive return declarations only;
        # preserve the getter body and adapt its type spelling at this boundary.
        source = source.replace('override HCOperationalStatus HCGetOperationalStatus()',
                                'override int HCGetOperationalStatus()')
        source = source.replace('super.OnTick(deltaTime)', 'self.LegacyTick(deltaTime)')
        source = source.replace('super.OnStop()', 'self.LegacyStop()')
        source = source.replace('super.OnStart(settings)', 'self.LegacyStart(settings)')
        source = source.replace('s_Instance', 'self.s_Instance').replace('this', 'self')
        source = source.replace('IsEnabled(settings)', 'self.IsEnabled(settings)')
        source = re.sub(r'\b(?:HC\w+|array<[^;]+>)\s+(?=\w+\s*=)', '', source)
        settings = NS(EnableInteriors=True)
        result = fixture(staged=True)
        env, raw, reads, logs = result[:4]
        env['EnsureLoaded'](None)
        events = []
        budget = SyntheticBudget(True)
        budget.HCReset = lambda limit: None
        module = NS(m_PackLoading=True, m_PackBudget=budget, m_Config=None, m_Objects=EArray(),
                    s_Instance=None, LegacyTick=lambda delta:None, IsEnabled=lambda cfg:cfg.EnableInteriors,
                    LegacyStart=lambda cfg:None, LegacyStop=lambda:events.append('stop'))
        ports = dict(GetGame=lambda:NS(IsServer=lambda:True),
                     HCServer=NS(Get=lambda:NS(GetSettings=lambda:settings)),
                     HCInteriorTemplates=NS(**env), Print=logs.append, FileExist=lambda path:False,
                     HCInteriorTemplatePlacement=NS(Place=lambda *args:events.append('place')),
                     HCSearchBinding=NS(TemplatesComplete=lambda owner:events.append('search')))
        execute_member(source, 'OnTick', ports, module, 1.0)
        self.assertGreater(len(reads), 1, 'module tick must advance pending pack even without a legacy owner')
        for _ in range(20):
            execute_member(source, 'OnTick', ports, module, 1.0)
            if env['Loaded'](): break
        self.assertTrue(env['Loaded'](), logs)
        self.assertIs(module, module.s_Instance)
        self.assertEqual(['place', 'search'], events)
        status_rows = []
        module.m_PackStatus = NS(HCPublish=lambda state,reason:status_rows.append((state,reason)))
        execute_member(source, 'HCGetOperationalStatus', ports, module)
        self.assertEqual('ready', status_rows[-1][0])
        execute_member(source, 'OnTick', ports, module, 1.0)
        self.assertEqual(['place', 'search'], events)
        execute_member(source, 'OnStop', ports, module)
        self.assertFalse(env['Loaded']())
        self.assertFalse(env['s_Job'].Started)
        execute_member(source, 'HCGetOperationalStatus', ports, module)
        self.assertEqual('off', status_rows[-1][0])
        execute_member(source, 'OnStart', ports, module, settings)
        env['EnsureLoaded'](None)
        self.assertTrue(module.m_PackLoading)
        execute_member(source, 'OnStop', ports, module)
        before = list(reads)
        execute_member(source, 'OnTick', ports, module, 1.0)
        self.assertEqual(before, reads)
        self.assertFalse(env['s_Job'].Started)
        self.assertTrue(any('state=off' in line for line in logs))

        # Explicit two-page synthetic metadata: page-merged can continue within this tick.
        from tools.package import interiors_profile as ip
        values = pack()
        index = values['index.json']
        values['index-000.json'] = dict(SchemaVersion=3, Chunk=0,
            SourcePins=[dict(Name=k,Sha256=v) for k,v in index['Sources'].items()],
            **{key:[] for key in ip.TEMPLATE_LISTS})
        values['index-001.json'] = dict(SchemaVersion=3, Chunk=1, SourcePins=[],
            **{key:index[key] for key in ip.TEMPLATE_LISTS})
        root = {k:v for k,v in index.items() if k not in ('Sources', *ip.TEMPLATE_LISTS)}
        root.update(SchemaVersion=3, IndexFiles=[dict(File='index-%03d.json'%i,Sha256='a'*64) for i in range(2)])
        values['index.json'] = root
        env, _, reads, logs = fixture(values, staged=True)[:4]
        ports['HCInteriorTemplates'] = NS(**env)
        module.m_PackLoading = True
        module.s_Instance = None
        env['EnsureLoaded'](None)
        execute_member(source, 'OnTick', ports, module, 1.0)
        self.assertGreaterEqual(len(reads), 3, 'page-merged must differ from exhausted budget')
        self.assertTrue(any(path.endswith('index-001.json') for path in reads))
        self.assertFalse(env['Loaded']())

    def test_reader_stages_both_schemas_without_reloading_and_resets_on_stop(self):
        from tests.unit.test_hc_template_pack import SyntheticBudget
        from tools.package import interiors_profile as ip
        legacy = pack()
        paged = copy.deepcopy(legacy)
        index = paged['index.json']
        page = dict(SchemaVersion=3, Chunk=0,
                    SourcePins=[dict(Name=k,Sha256=v) for k,v in index['Sources'].items()],
                    **{key:index[key] for key in ip.TEMPLATE_LISTS})
        paged['index-000.json'] = page
        root = {k:v for k,v in index.items() if k not in ('Sources', *ip.TEMPLATE_LISTS)}
        root.update(SchemaVersion=3, IndexFiles=[dict(File='index-000.json', Sha256='a'*64)])
        paged['index.json'] = root
        snapshots = []
        for values in (legacy, paged):
            result = fixture(values, staged=True)
            env, raw, reads, logs = result[:4]
            env['EnsureLoaded'](None)
            self.assertFalse(env['Loaded'](), 'startup must retain a job and yield before leaves')
            self.assertEqual(1, len(reads))
            job = env['s_Job']
            env['HCLoadStep'](None, SyntheticBudget(False))
            self.assertEqual(1, len(reads))
            budget = SyntheticBudget(True)
            for _ in range(20):
                before = len(reads)
                env['HCLoadStep'](None, SyntheticBudget(False))
                self.assertEqual(before, len(reads))
                env['HCLoadStep'](None, budget)
                if env['Loaded'](): break
            self.assertTrue(env['Loaded'](), logs)
            self.assertIs(job.Index, env['s_Index'])
            self.assertEqual(len(raw), len(reads))
            self.assertEqual(len(reads), len(set(reads)))
            self.assertEqual(sum(len(text) for text in raw.values()), job.Bytes)
            self.assertIn('pack_chunks=%d classes=1 refused=none state=ready' % (len(raw)-1), '\n'.join(logs))
            snapshots.append((vars(env['ClassRow']('Land_House_1W01')),
                              vars(env['Template']('Land_House_1W01')),
                              vars(env['Group']('g-0000')), [vars(row) for row in env['FurnishRows']()]))
            env['HCLoadReset']()
            self.assertFalse(env['Loaded']())
            self.assertFalse(job.Started)
            self.assertEqual((0, 0), (job.Files, job.Bytes))
            env['EnsureLoaded'](None)
            self.assertTrue(job.Started)
        # Compare exact native-deserialization results, including all template fields.
        def plain(value):
            if isinstance(value, NS): return {k:plain(v) for k,v in vars(value).items()}
            if isinstance(value, dict): return {k:plain(v) for k,v in value.items()}
            if isinstance(value, (list,tuple)): return [plain(v) for v in value]
            return value
        self.assertEqual(plain(snapshots[0]), plain(snapshots[1]))

    def test_reader_propagates_job_refusal_and_clears_partial_admission(self):
        from tests.unit.test_hc_template_pack import SyntheticBudget
        for broken in ('index.json', 'classes-000.json', 'furnish-000.json'):
            result = fixture(staged=True)
            env, raw, reads, logs = result[:4]
            raw[broken] = '{}'
            env['EnsureLoaded'](None)
            for _ in range(20):
                if env['s_Reason']: break
                env['HCLoadStep'](None, SyntheticBudget(True))
            self.assertFalse(env['Loaded']())
            expected = 'legacy_index_or_pin' if broken == 'index.json' else 'chunk_strict:' + broken
            self.assertEqual(expected, env['s_Reason'], logs)
            self.assertTrue(any('HC-24 pack_chunks=' in line and 'state=refused' in line for line in logs))
            self.assertFalse(env['s_Job'].Started)
            self.assertEqual([], env['s_Classes'])
            before = list(reads)
            env['EnsureLoaded'](None)
            self.assertEqual(before, reads)

    def test_resolve_cache_is_bounded_separates_positions_and_resets_on_stop(self):
        result = self.load()
        env = result[0]
        queries = []
        def query(position, radius, found, cargos):
            queries.append(tuple(position))
            found.append(SyntheticHouse(position=position))
        env['GetGame'] = lambda: NS(GetObjectsAtPosition3D=query)
        row = env['FurnishRows']()[0]
        for index in range(env['RESOLVE_CACHE_LIMIT'] + 1):
            row.Position = [100 + index * 10, 0, 100]
            self.assertIsNotNone(env['Resolve'](row))
        self.assertEqual(env['RESOLVE_CACHE_LIMIT'], len(env['s_ResolveCache']))
        row.Position = [100, 0, 100]
        env['Resolve'](row)  # Oldest position was evicted, without an unbounded cache.
        self.assertEqual(env['RESOLVE_CACHE_LIMIT'] + 2, len(queries))
        env['Resolve'](row)
        self.assertEqual(env['RESOLVE_CACHE_LIMIT'] + 2, len(queries))
        env['ResetPlacement']()
        self.assertEqual([], env['s_ResolveCache'])
        self.assertEqual(0, env['s_ResolveNext'])
        env['Resolve'](row)
        self.assertEqual(env['RESOLVE_CACHE_LIMIT'] + 3, len(queries))
        extension = (SRC / 'HCInteriorTemplatesModule.c').read_text()
        self.assertIn('HCInteriorTemplatePlacement.ResetPlacement();',
                      body(extension, extension.index('{', extension.index('override void OnStop()')) + 1))

    def test_cached_resolve_rechecks_live_pose_and_class(self):
        result = self.load()
        env, _, _, _, world, _ = result
        row = env['FurnishRows']()[0]
        house = world[0]
        self.assertIs(house, env['Resolve'](row))
        house.orientation[1] = .6
        self.assertIsNone(env['Resolve'](row))
        self.assertEqual('tilted', env['s_ResolveReason'])
        house.orientation[1] = 0
        house.position[0] += 1
        self.assertIsNone(env['Resolve'](row))
        self.assertEqual('unresolved', env['s_ResolveReason'])
        house.position[0] -= 1
        row.BuildingClass = 'Land_SyntheticOther'
        self.assertIsNone(env['Resolve'](row))
        self.assertEqual('unresolved', env['s_ResolveReason'])

    def test_multiple_template_rows_for_one_live_building_preserve_duplicate_refusals(self):
        # Explicit synthetic placement inputs; normal pack validation rejects identical rows.
        # Exercise the placement backstop as well as the per-slot continuation path below.
        snapshots = []
        for uncached in (True, False):
            result = self.load()
            env, _, _, _, world, placed = result
            queries = []
            def query(position, radius, found, cargos):
                queries.append(tuple(position)); found.extend(world)
            env['GetGame'] = lambda:NS(GetObjectsAtPosition3D=query)
            row = env['FurnishRows']()[0]
            settings = NS(MaxFurnishedProps=1500, MaxPropsPerInterior=5)
            for _ in range(3):
                if uncached:
                    env['s_ResolveCache'].Clear()
                env['PlaceRow'](NS(), copy.deepcopy(row), settings, placed)
            snapshots.append(([(obj.Type, obj.Position, obj.Orientation) for obj in placed],
                              dict(env['s_Refused']), len(queries)))
        self.assertEqual(snapshots[0][:2], snapshots[1][:2])
        self.assertEqual(1, len(snapshots[1][0]))
        self.assertEqual(2, snapshots[1][1]['duplicate_house'])
        self.assertEqual((3, 1), (snapshots[0][2], snapshots[1][2]))

    def test_building_templates_keep_placements_and_refusals_with_one_resolve_query(self):
        # Explicit synthetic building with three prop templates, attempted one per slice.
        # Clearing only the candidate cache before each slice models the old native queries.
        values = pack()
        template = values['t-0000.json']
        original = copy.deepcopy(template['PropSlots'][0])
        for slot_id, x in ((2, 0), (3, 2)):
            slot = copy.deepcopy(original)
            slot.update(Id=slot_id, Position=[x, 0, -2],
                        Bounds=dict(Min=[x-.5, 0, -2.5], Max=[x+.5, 2, -1.5]))
            template['PropSlots'].append(slot)
        values['furnish-000.json']['Rows'][0]['Props'] = [1, 2, 3]

        def run(uncached, objects=None):
            result = self.load(values)
            env, _, _, _, world, placed = result
            if objects is not None:
                world[:] = objects
            queries = []
            def query(position, radius, found, cargos):
                queries.append((list(position), radius))
                found.extend(world)
            env['GetGame'] = lambda: NS(GetObjectsAtPosition3D=query)
            row = env['FurnishRows']()[0]
            settings = NS(MaxFurnishedProps=1500, MaxPropsPerInterior=5)
            for index in range(3):
                if uncached:
                    env['s_ResolveCache'].Clear()
                env['HCPlaceRowSlice'](NS(), row, settings, placed, index, 1, index, len(placed))
            snapshot = [(obj.Type, obj.Position, obj.Orientation) for obj in placed]
            return snapshot, dict(env['s_Refused']), queries

        baseline, refusals, baseline_queries = run(True)
        cached, cached_refusals, queries = run(False)
        self.assertEqual(3, len(baseline))
        self.assertEqual(baseline, cached)
        self.assertEqual(refusals, cached_refusals)
        self.assertEqual(3, len(baseline_queries))
        self.assertEqual(1, len(queries), 'same building must share one native resolve query')
        for world, reason in (([], 'unresolved'),
                              ([SyntheticHouse(), SyntheticHouse()], 'ambiguous'),
                              ([SyntheticHouse(orientation=(15, .6, 0))], 'tilted'),
                              ([SyntheticHouse()] * 257, 'query_cap')):
            with self.subTest(reason=reason):
                before = run(True, world)
                after = run(False, world)
                self.assertEqual(before[:2], after[:2])
                self.assertEqual(9, after[1][reason])
                self.assertEqual(1, len(after[2]))

    def test_abandoned_history_and_every_catalog_prop_load_and_place(self):
        from tools.package import interior_catalog
        for typ in interior_catalog.PROPS:
            with self.subTest(typ=typ):
                values=pack()
                values['t-0000.json']['PropSlots'][0].update(Type=typ,History=['abandoned'])
                values['furnish-000.json']['Rows'][0]['History']='abandoned'
                result=self.load(values)
                self.assertTrue(result[0]['Loaded'](),result[3])
                self.assertEqual(1,len(self.place(result)[1]))
                self.assertTrue(any('[HC Interiors] prop box type='+typ+' min=<' in line for line in result[3]))

    def test_native_box_logger_runs_once_per_created_type_without_spawning(self):
        result=fixture(); env=result[0]; calls=[]
        def clipping(box):
            calls.append('clip'); box[:]=[[-.5,0,-.3],[.5,2,.3]]
        prop=NS(GetType=lambda:'StaticObj_Furniture_case_a',ClippingInfo=clipping)
        env['s_BoxLogged']=Array()
        logger=env['LogPropBox']
        logger(prop); logger(prop); logger(None)
        self.assertEqual(['clip'],calls)
        self.assertEqual(1,len(result[3]))
        self.assertTrue(result[3][0].startswith('[HC Interiors] prop box type=StaticObj_Furniture_case_a min=<'))
        self.assertIn('> max=<',result[3][0])
        from tools.package import interior_templates
        parsed=interior_templates.ingest_boxes(('SYNTHETIC\n'+'\n'.join(result[3])).encode())
        self.assertEqual(2,parsed['Props']['StaticObj_Furniture_case_a']['Height'])
        second=NS(GetType=lambda:'StaticObj_Furniture_case_a_open',ClippingInfo=clipping)
        logger(second); logger(second)
        self.assertEqual(['clip','clip'],calls)
        self.assertEqual(2,len(result[3]))
        self.assertEqual([],result[5])
        source=(SRC/'HCInteriorTemplatePlacement.c').read_text()
        self.assertIn('LogPropBox(object);',source)
        self.assertEqual(1,source.count('CreateObjectEx('))

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
        result=fixture(); result[0]['EngineHouse']=lambda cls:False
        result[0]['EnsureLoaded'](None); self.assert_refused(result)

    def test_pack_covers_a_subset_of_engine_house_classes(self):
        # The engine has thousands of House classes (walls, wrecks, ruins); the pack lists only the
        # classes it covers. Each must be an engine House class; the pack need not list every one.
        result=fixture(); result[0]['EngineHouse']=lambda cls:cls in {'Land_House_1W01','Land_Other','Land_Wall'}
        result[0]['EnsureLoaded'](None); self.assertTrue(result[0]['Loaded']())

    @staticmethod
    def search_only_pack(rooms_disposition='path_pending'):
        # A class measured by the census whose rooms lack path/door proof: search runs at its vanilla
        # CE container points only; no rooms, keep-outs or props, so infected and furniture never use it.
        values=pack(); pin='a'*64
        values['index.json']['TemplateFiles'].append(dict(File='t-0001.json',BuildingClass='Land_House_2W01',Sha256=pin))
        values['classes-000.json']['Rows'].append(dict(BuildingClass='Land_House_2W01',Rooms=rooms_disposition,
                                                       Furniture='path_pending',Search='covered'))
        template=json.loads(json.dumps(values['t-0000.json']))
        template.update(BuildingClass='Land_House_2W01',TemplateId='synthetic-search-v1',Rooms=[],KeepOuts=[],PropSlots=[])
        template['SearchSites'][0]['Room']=0
        values['t-0001.json']=template
        return values

    def load_search_only(self, values):
        result=fixture(values); result[0]['EngineHouse']=lambda cls:cls in {'Land_House_1W01','Land_House_2W01'}
        result[0]['EnsureLoaded'](None); return result

    def test_search_only_template_without_rooms_is_admitted_for_search(self):
        e=self.load_search_only(self.search_only_pack())[0]
        self.assertTrue(e['Loaded']())
        self.assertEqual('covered',e['ClassRow']('Land_House_2W01').Search)
        self.assertEqual('path_pending',e['ClassRow']('Land_House_2W01').Rooms)
        layout=e['Template']('Land_House_2W01')
        self.assertEqual(0,len(layout.Rooms)); self.assertEqual(0,layout.SearchSites[0].Room)
        self.assertEqual(1,len(e['Template']('Land_House_1W01').Rooms))

    def test_rooms_covered_class_still_requires_rooms(self):
        self.assert_refused(self.load_search_only(self.search_only_pack(rooms_disposition='covered')))

    def test_room_zero_site_refuses_when_the_template_has_rooms(self):
        values=pack(); values['t-0000.json']['SearchSites'][0]['Room']=0
        self.assert_refused(self.load(values))

    def test_search_only_template_cannot_cover_furniture(self):
        values=self.search_only_pack(); values['classes-000.json']['Rows'][1]['Furniture']='covered'
        self.assert_refused(self.load_search_only(values))

    def test_engine_house_reads_config_per_class_not_all_cfgvehicles(self):
        source=(SRC/'HCInteriorTemplates.c').read_text()
        self.assertNotIn('ConfigGetChildrenCount("CfgVehicles")', source)
        self.assertIn('GetGame().IsKindOf(cls, "House")', source)

    def with_sources(self, profile, shipped):
        """Explicit synthetic file presence; the stub mirrors HCProfileDefaults.Resolve order."""
        result=fixture(); e=result[0]; copies=[]
        present=set()
        if profile: present.add('$profile:HollowCountry/templates/index.json')
        if shipped: present.add('HollowCountry/data/defaults/templates/index.json')
        def resolve(relative, root):
            for candidate in ('$profile:HollowCountry/'+relative, root+relative):
                if candidate in present: return candidate
            return ''
        e['HCProfileDefaults']=NS(PBO_ROOT='HollowCountry/data/defaults/',Resolve=resolve,
                                  Ensure=lambda *a:copies.append(a),EnsureBase=lambda *a:copies.append(a))
        e['EnsureLoaded'](None)
        return result, copies

    def test_workshop_route_reads_shipped_pack_from_pbo_when_profile_pack_absent(self):
        (e,raw,reads,logs,objects,created),copies=self.with_sources(profile=False, shipped=True)
        self.assertTrue(e['Loaded'](),logs)
        self.assertTrue(reads)
        self.assertTrue(all(path.startswith('HollowCountry/data/defaults/templates/') for path in reads),reads)
        self.assertIn('[HC Interiors] templates source=pbo root=HollowCountry/data/defaults/templates/',' '.join(logs))
        self.assertEqual([],copies)  # read in place: nothing is written to the operator profile

    def test_operator_profile_pack_wins_over_shipped_pack(self):
        (e,raw,reads,logs,objects,created),copies=self.with_sources(profile=True, shipped=True)
        self.assertTrue(e['Loaded'](),logs)
        self.assertTrue(all(path.startswith('$profile:HollowCountry/templates/') for path in reads),reads)
        self.assertIn('[HC Interiors] templates source=profile root=$profile:HollowCountry/templates/',' '.join(logs))
        self.assertEqual([],copies)

    def test_missing_pack_in_both_sources_refuses_without_reading(self):
        (e,raw,reads,logs,objects,created),copies=self.with_sources(profile=False, shipped=False)
        self.assertFalse(e['Loaded']()); self.assertEqual([],reads)
        self.assertIn('templates refused: pack_missing',' '.join(logs))
        self.assertIn('templates source=missing', ' '.join(logs))
        self.assertIn('[HollowCountry] V1 admission feature=InteriorPlacement preference=on gate=interior_placement qualified=0 result=refused: template pack missing',' '.join(logs))

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

    def test_heaviest_item_name_carries_the_resolve_query_size(self):
        # Boot 032: one 0.75 m house resolve cost 30-1600 ms; the step line must say how many
        # objects the query returned so the next boot separates query cost from result size.
        result=self.load(); e=result[0]
        result[4].append(SyntheticHouse(position=(500,0,500)))
        self.place(result)
        self.assertTrue(e['HCLastType']().endswith('#q2'),e['HCLastType']())

    def test_props_cap_holds_and_never_reads_during_placement(self):
        result=self.load(); reads=list(result[2]); e,created=self.place(result,overall=0)
        self.assertEqual(0,len(created)); self.assertEqual(1,e['s_Capped'])
        self.assertEqual(reads,result[2])
        result=self.load(); e,created=self.place(result,overall=1)
        self.assertEqual(1,len(created)); self.assertEqual(1,e['s_Placed'])
        self.assertEqual([98,0,98],created[0].Position)

    def test_tilted_and_ambiguous_live_houses_refuse(self):
        for objects,reason in [([SyntheticHouse(orientation=(15,.6,0))],'tilted'),
                               ([SyntheticHouse(),SyntheticHouse(position=(100.5,0,100))],'ambiguous')]:
            result=self.load(); result[4][:]=objects; e,created=self.place(result)
            self.assertEqual(0,len(created)); self.assertEqual(1,e['s_Refused'][reason])

    def test_nearly_level_house_places_at_full_model_transform(self):
        for pitch, roll in ((.3, -.3), (-0., -0.), (.5, -.5)):
            with self.subTest(pitch=pitch, roll=roll):
                result = self.load()
                house = SyntheticHouse(orientation=(15, pitch, roll))
                # Explicit synthetic native boundary: a tilted transform changes height.
                house.ModelToWorld = lambda local: [98., 7.25, 98.]
                result[4][:] = [house]
                env, created = self.place(result)
                self.assertEqual(1, len(created))
                self.assertEqual([98., 7.25, 98.], created[0].Position)
                self.assertEqual(0, env['s_Refused']['tilted'])

    def test_nonfinite_or_over_limit_house_counts_tilt_refusal(self):
        for axis in (1, 2):
            for value in (.6, -.6, float('nan')):
                with self.subTest(axis=axis, value=value):
                    result = self.load()
                    pose = [15., 0., 0.]; pose[axis] = value
                    result[4][:] = [SyntheticHouse(orientation=pose)]
                    env, created = self.place(result)
                    self.assertEqual([], created)
                    self.assertEqual(1, env['s_Refused']['tilted'])

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


    def test_file_keys_reach_the_engine_as_FileName(self):
        # A loaded dependency declares a type named File (compile with the Expansion stack: "Variable name
        # 'File' already used as type name"), so DTO members cannot be called File or Slot.
        e=fixture()[0]
        text=e['NativeText'](json.dumps(pack()['index.json']),'index')
        self.assertNotIn('"File"',text); self.assertEqual(4,text.count('"FileName"'))
        data=(SRC/'HCInteriorTemplatesData.c').read_text()
        self.assertEqual([],re.findall(r'^\s*(?:ref )?[\w<>, ]+ (File|Slot);',data,re.M))
        self.assertTrue(self.load()[0]['Loaded']())

    def test_class_chunk_longer_than_one_native_substring_reaches_the_engine_whole(self):
        # The release classes-000.json is ~25 KB; a single Substring copy cut it to 8191 characters
        # and LoadData refused it ("Missing a closing quotation mark"), refusing the whole pack.
        e=fixture()[0]; values=pack(); row=values['classes-000.json']['Rows'][0]
        values['classes-000.json']['Rows']=[dict(row,BuildingClass='Land_House_%04d'%i) for i in range(160)]
        text=json.dumps(values['classes-000.json']); self.assertGreater(len(text),2*8191)
        self.assertEqual(text,e['NativeText'](text,'classes'))
        index=values['index.json']; index['ClassFiles'][0]['File']='classes-000.json'
        self.assertEqual(json.loads(json.dumps(index).replace('"File"','"FileName"')),
                         json.loads(e['NativeText'](json.dumps(index),'index')))

    def test_read_totals_are_refused_before_publication(self):
        for key,value in [('LeafFiles',610),('Bytes',20971520)]:
            result=fixture(staged=True); e=result[0]
            e['EnsureLoaded'](None)
            setattr(e['s_Job'], key, value)
            self.assertEqual('',e['ReadStrict']('classes-000.json','classes','a'*64))
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
        result=fixture(); e=result[0]
        e['HCProfileDefaults'].Resolve=lambda relative,root:root+relative
        e['HCInteriorMeasuredCatalog'].MeasuredClaimedClass=lambda:'Land_House_1W01'
        e['EnsureLoaded'](None); self.assert_refused(result)
        self.assertIn('[HC Interiors] shipped pack yields to legacy room owner', result[3])
        for key in ('s_ClassIndex', 's_TemplateIndex', 's_GroupIndex', 's_TemplatePins'):
            self.assertEqual(0, len(e[key]), key)

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
            Print=lambda text:None,FileExist=lambda path:False,
            HCSearchBinding=NS(TemplatesComplete=lambda owner:None),
            HCInteriorMeasuredCatalog=NS(MeasuredEnsureLoaded=lambda:None),
            HCInteriorTemplates=NS(EnsureLoaded=lambda legacy,cap:events.append(('load',legacy,cap)),Loaded=lambda:True),
            HCInteriorTemplatePlacement=NS(Place=lambda *args:events.append(('place',))))
        if name=='OnStart': return execute_member(source,name,e,module,settings)
        return execute_member(source,name,e,module,index)

    def test_template_startup_runs_without_legacy_config_and_preserves_pilot_entry(self):
        events=[]; settings=NS(MaxFurnishedProps=1500,MaxPropsPerInterior=5)
        module=NS(s_Instance=None,m_Config=None,m_Objects=EArray(),IsEnabled=lambda cfg:True,
                  LegacyStart=lambda cfg:events.append(('legacy',)))
        self.invoke_extension('OnStart',module,settings,events=events)
        # HC-24: placement and the owner install move to the staged pack tick (HCInteriorTemplates.c).
        self.assertEqual([('legacy',),('load',None,5)],events)
        self.assertIsNone(module.s_Instance)

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

    def test_text_lists_preserve_validation_and_input_order(self):
        env = fixture()[0]
        for values, minimum, maximum, expected in (
                (None, 0, 2, False), ([], 0, 2, True), ([], 1, 2, False),
                (['B', 'A'], 1, 2, True), (['A', 'B', 'C'], 0, 2, False),
                (['B', 'A', 'B'], 1, 3, False), (['A', 'a'], 1, 2, True),
                (['_.-:+/=09aZ'], 1, 2, True), (['A' * 128], 1, 2, True),
                (['A' * 129], 1, 2, False), ([''], 1, 2, False),
                (['A B'], 1, 2, False), (['é'], 1, 2, False)):
            with self.subTest(values=values, minimum=minimum, maximum=maximum):
                source = None if values is None else Array(values)
                self.assertEqual(expected, env['Texts'](source, minimum, maximum))
                self.assertEqual(values, source)

    def test_text_list_duplicate_detection_uses_one_sort_without_linear_searches(self):
        calls = []
        class CountedArray(Array):
            def Find(self, value):
                calls.append('find')
                return super().Find(value)
            def Sort(self):
                calls.append('sort')
                super().Sort()
        env = fixture()[0]; env['EArray'] = CountedArray
        values = Array('Item%04d' % n for n in reversed(range(1024)))
        self.assertTrue(env['Texts'](values, 1, 1024))
        self.assertEqual(['sort'], calls)

    def test_group_loader_sorts_items_only_once_and_refuses_duplicates_in_every_list(self):
        for field in ('Usages', 'Categories', 'Tags', 'Items'):
            values = pack(); values['search-groups-000.json']['Groups'][0][field] = ['B', 'A', 'B']
            self.assert_refused(self.load(values))
        calls = []
        class CountedArray(Array):
            def Sort(self):
                calls.append(list(self)); super().Sort()
        result = fixture(self.with_items(['Hammer', 'Axe']))
        result[0]['EArray'] = CountedArray
        result[0]['EnsureLoaded'](None)
        self.assertTrue(result[0]['Loaded'](), result[3])
        self.assertEqual(1, calls.count(['Hammer', 'Axe']))

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
