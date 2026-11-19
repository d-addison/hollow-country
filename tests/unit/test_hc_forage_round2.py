"""HC-12/13 synthetic native ports; authored control flow, never DayZ proof.

Actual test-first evidence (2026-11-18), command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_forage_round2 -v
P1 RED: AssertionError: 1 != 0 : eligible default candidate must materialize
P1 RED: AssertionError: '' != 'BoletusMushroom'
P1 GREEN (with test_hc_forage and unchanged test_v2_world): Ran 6 tests; OK.
P2/P3 RED: archive absent; pickup 3 != 4 writes; cap 2 != 128;
           Unknown field MaxFamiliarityRows; Stop deferred 0 != 40.
P2/P3 GREEN: Ran 7 tests; OK.
Identity restart RED (single method): AssertionError: 2 != 1 : a later Start
gets one fresh bounded diagnostic. GREEN (whole module): Ran 8 tests; OK.
Native outputs, clock, files and handles below are explicit synthetic fixtures.
"""
import copy
import math
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_hc_forage import bind
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2]
FORAGE = ROOT / 'mods/HollowCountry/scripts/4_World/Forage/HCForage.c'
PROGRESSION = ROOT / 'mods/HollowCountry/scripts/4_World/Progression/HCProgression.c'
POLICY = ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCSurvivalPolicy.c'
SETTINGS = ROOT / 'mods/HollowCountry/scripts/3_Game/HCSettings.c'


class Vec(list):
    def __add__(self, other):
        if isinstance(other, str):
            other = [float(v) for v in other.split()]
        return Vec(a+b for a, b in zip(self, other))


class SyntheticRuntime:
    """Explicit in-memory files, native outputs, budgets, scheduler and handles."""
    def __init__(self):
        self.now = 5000
        self.logs, self.writes, self.created = [], [], []
        self.files = {}
        self.players = EArray()
        self.month, self.roll = 6, 1
        self.surface, self.water, self.collision, self.slope = 'cp_conifer_moss', False, False, 0
        self.settings = N(EnableForage=True, EnableProgression=True, MaxFamiliarityRows=0)
        self.env = dict(range=range, str=str, len=len, native_int=int, EArray=EArray, Print=self.logs.append,
            RECORD_CAP=40, LIVE_CAP=40, PATH='synthetic/forage', LEGACY_PATH='synthetic/progression.v1.json',
            Math=N(Floor=math.floor, AbsFloat=abs, RandomInt=lambda lo, hi: self.roll),
            Vector=lambda x, y, z: Vec([x, y, z]),
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a,b))),
            ObjIntersect=N(View=1, Geom=2), ECE_SETUP=1, ECE_TRACE=2,
            ECE_CREATEPHYSICS=4, ECE_DYNAMIC_PERSISTENCY=8,
            PlayerBase=N(Cast=lambda p:p), ItemBase=N(Cast=lambda p:p),
            HCGroupClock=N(Utc=lambda:self.now),
            HCV2Admission=N(Line=lambda *args:'synthetic admission'),
            HCWorldLimits=N(Position=lambda p:True, Admit=lambda count, cap, name:count < cap),
            HCSurvivalRuntime=N(HCIsServer=lambda:True, HCIdentityKey=lambda p:p.uid,
                                HCCharacterKey=lambda p:p.life),
            HCPerfPlayers=N(HCGet=lambda:self.players),
            HCSaveJob=N(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2),
            FileExist=lambda path:path in self.files,
            HCV2ThreatStore=N(CanOpen=lambda path:True, Save=self.save,
                              Load=lambda path,limit:copy.deepcopy(self.files.get(path))),
            HCForageState=lambda:N(Version=1, WorldName='', Spots=EArray()),
            HCForageSpot=lambda:N(CellX=0, CellZ=0, NodeSlot=0, ReadyUtc=0),
            HCForageNode=lambda:N(Spot=None, Item=None, WasLive=False),
            HCProgressionState=lambda:N(Version=2, Players=EArray()),
            HCProgressionRow=lambda:N(Key='', CharacterKey='', Dead=False, Forage=0, DecayUtc=0, GainUtc=0),
            HCForageSaveJob=lambda:N(Owner=None,HCDirty=False),
            HCProgressionSaveJob=lambda:N(Owner=None,HCDirty=False))
        self.game = N(GetWorldName=lambda:'chernarusplus', GetWorld=lambda:self,
            SurfaceY=lambda x,z:self.slope, SurfaceIsSea=lambda x,z:self.water,
            SurfaceIsPond=lambda x,z:False, SurfaceGetType=lambda x,z:self.surface,
            ConfigIsExisting=lambda path:True, IsBoxCollidingGeometry=lambda *args:self.collision,
            CreateObjectEx=self.create, ObjectDelete=lambda item:None)
        self.env['GetGame'] = lambda:self.game
        self.env['native_date'] = lambda:(2026,self.month,1,12,0)
        self.env['HCSaveScheduler'] = N(HCRegister=lambda job:None, HCUnregister=lambda job:None,
                                       HCFlush=self.flush)
        policy = N()
        self.env['HCSurvivalPolicy'] = policy
        for name in ('CanRefill','DecayedFamiliarity','ForageDelay'):
            source = POLICY.read_text().replace('return 1800 - (180 * score) / 100;',
                'return 1800 - native_int((180 * score) / 100);')
            setattr(policy,name,translate(source,name,self.env,'HCSurvivalPolicy'))
        self.progression = self.module(PROGRESSION, 'HCProgressionModule')
        self.env['HCProgressionModule'] = N(HCRecordForage=self.progression.HCAwardForage)
        self.forage = self.module(FORAGE, 'HCForageModule')

    def save(self, path, state, limit):
        self.files[path] = copy.deepcopy(state)
        self.writes.append((path,copy.deepcopy(state)))
        return True

    def create(self, kind, pos, flags):
        item = N(kind=kind, owner=None, lifetime=0)
        item.GetHierarchyParent = lambda:item.owner
        item.GetHierarchyRootPlayer = lambda:item.owner
        item.SetLifetime = lambda value:setattr(item,'lifetime',value)
        self.created.append(item)
        return item

    def flush(self, job):
        for _ in range(16):
            result = job.Owner.HCStepCheckpoint()
            if result != 1:
                job.HCDirty = False
                return result == 0
        return False

    def module(self, path, cls):
        module = N(m_Healthy=False,m_Dirty=False,m_State=None,m_Nodes=None,m_Players=None,
            m_Exclude=None,m_SaveJob=None,m_Snapshot=None,m_Cursor=0,m_SaveUtc=self.now,
            m_NodeCursor=0,m_PlayerCursor=0,m_SlotCursor=0,m_Elapsed=0,m_Deferred=0,
            m_Revision=0,m_SnapshotRevision=0,m_SaveStage=0,m_IdentityRefused=False,m_RowCap=128,
            m_LastUtc=self.now,m_VisibilityPending=False,
            m_Units=N(HCReset=lambda *args:None,HCTake=lambda *args:True),
            m_Work=N(HCReset=lambda *args:None,HCContinue=lambda:True),
            m_Status=N(HCPublish=lambda *args:None))
        env = dict(self.env,PATH='synthetic/'+('forage' if path == FORAGE else 'progression'))
        # Native out parameters only: all placement/date/selection decisions stay authored.
        source = path.read_text().replace(
            'GetGame().SurfaceGetType(position[0], position[2], surface);',
            'surface = GetGame().SurfaceGetType(position[0], position[2]);').replace(
            'GetGame().GetWorld().GetDate(year, month, day, hour, minute);',
            'year, month, day, hour, minute = native_date();')
        import re
        source = re.sub(r'new array<[^;]+>;', 'new EArray;', source)
        source = re.sub(r'([\w.]+)\.Get\(([^()]+)\)',r'\1[\2]',source)
        source = source.replace('(payload / 2)', '(native_int(payload / 2))')
        source = re.sub(r'if \(!HCV2ThreatStore<\w+>\.Load\(([^,]+), ([^,]+), (\w+)\)\)',
            r'\3 = HCV2ThreatStore.Load(\1, \2); if (!\3)',source)
        class_body = body(source, re.search(r'class '+cls+r'\b[^\{]*\{',source).end())
        names = re.findall(r'^    (?:protected |override )?(?:bool|void|int|string|vector|HCForageNode) (\w+)\(',class_body,re.M)
        bind(path,cls,module,env,names,source=source)
        return module

    def start(self):
        self.progression.OnStart(self.settings)
        self.forage.OnStart(self.settings)

    def player(self, index=1, life='c:1:2:3:4', cell=50):
        return N(uid='p'+format(index,'032x'),life=life,IsAlive=lambda:True,
                 GetPosition=lambda:Vec([cell*200,0,10000]))


class ForageRound2(unittest.TestCase):
    def test_default_candidate_materializes_reclaims_and_rewards_character_life(self):
        r = SyntheticRuntime()
        r.players.Insert(r.player())
        r.start()
        for index in range(40):
            spot = N(CellX=index,CellZ=0,NodeSlot=0,ReadyUtc=r.now-1)
            r.forage.m_State.Spots.Insert(spot)
            r.forage.m_Nodes.Insert(N(Spot=spot,Item=None,WasLive=False))
        r.forage.OnTick(10)
        self.assertEqual(1,len(r.created),'eligible default candidate must materialize')
        self.assertEqual('SambucusBerry',r.created[0].kind)
        self.assertEqual(600,r.created[0].lifetime)
        self.assertEqual(40,len(r.forage.m_Nodes),'expired record must be reclaimed on the spawn path')
        item = r.created[0]
        item.owner = r.players[0]
        r.forage.HCObserveCollection(item,item.owner)
        row = r.progression.m_State.Players[0]
        self.assertEqual(1,row.Forage)
        node = r.forage.m_Nodes[-1]
        self.assertEqual(r.now+1799,node.Spot.ReadyUtc)
        r.forage.HCObserveCollection(item,item.owner)
        self.assertEqual(1,row.Forage,'re-drop cannot award twice')
        r.progression.HCObserveDeath(item.owner)
        self.assertEqual(0,row.Forage)
        self.assertTrue(row.Dead)
        self.assertEqual(0,r.progression.HCAwardForage(item.owner))
        replacement = r.player(life='c:5:6:7:8')
        self.assertEqual(1,r.progression.HCAwardForage(replacement))
        self.assertEqual(replacement.life,row.CharacterKey)

    def test_seasonal_content_and_existing_surface_distance_geometry_vetoes(self):
        r = SyntheticRuntime()
        r.players.Insert(r.player())
        r.start()
        for month in (1,5,12):
            self.assertEqual('',r.forage.HCSeasonalType(month,0))
        self.assertEqual('SambucusBerry',r.forage.HCSeasonalType(6,0))
        self.assertEqual('CaninaBerry',r.forage.HCSeasonalType(8,1))
        self.assertEqual('BoletusMushroom',r.forage.HCSeasonalType(9,0))
        self.assertEqual('MacrolepiotaMushroom',r.forage.HCSeasonalType(11,1))
        r.roll = 0
        self.assertEqual('Cannabis',r.forage.HCSeasonalType(6,2))
        self.assertEqual('',r.forage.HCSeasonalType(1,2))
        r.forage.m_Players = r.players
        pos = Vec([10045,0,10155])
        self.assertTrue(r.forage.HCClearCandidate(pos))
        r.water = True
        self.assertFalse(r.forage.HCClearCandidate(pos))
        r.water, r.surface = False, 'cp_asphalt'
        self.assertFalse(r.forage.HCClearCandidate(pos))
        r.surface, r.slope = 'cp_broadleaf_leaves', 1
        self.assertFalse(r.forage.HCClearCandidate(pos))
        r.slope, r.collision = 0, True
        self.assertFalse(r.forage.HCClearCandidate(pos))
        r.collision = False
        r.players[0].GetPosition = lambda:Vec([10045,0,10184.9])
        self.assertFalse(r.forage.HCClearCandidate(pos))
        r.players[0].GetPosition = lambda:Vec([10045,0,10185])
        self.assertTrue(r.forage.HCClearCandidate(pos))

    def test_legacy_archive_preserves_rows_and_maps_only_living_known_characters(self):
        r = SyntheticRuntime()
        living = r.player()
        r.players.Insert(living)
        mapped = N(Key=living.uid,CharacterKey='',Dead=False,Forage=37,DecayUtc=r.now-100,GainUtc=r.now-60)
        unknown = N(Key=r.player(2).uid,CharacterKey='',Dead=False,Forage=81,DecayUtc=r.now-100,GainUtc=r.now-60)
        r.progression.m_State = N(Version=1,Players=EArray([mapped,unknown]))
        original = copy.deepcopy(r.progression.m_State)
        self.assertTrue(r.progression.HCMigrate(r.now))
        self.assertIn('synthetic/progression.v1.json',r.files,'legacy rows must be archived before conversion')
        self.assertEqual(original,r.files['synthetic/progression.v1.json'])
        self.assertEqual(2,r.progression.m_State.Version)
        self.assertEqual(1,len(r.progression.m_State.Players))
        self.assertEqual((37,living.life),(mapped.Forage,mapped.CharacterKey))
        lines = [line for line in r.logs if '[HC Plan]' in line and 'rows_dropped=' in line]
        self.assertEqual(1,len(lines))
        self.assertIn('rows_dropped=1',lines[0])
        self.assertIn('rows_mapped=1',lines[0])
        self.assertTrue(r.progression.HCMigrate(r.now))
        self.assertEqual(1,len([line for line in r.logs if 'rows_dropped=' in line]))
        self.assertEqual(1,len(r.writes),'v2 migration must be idempotent')
        # An existing archive must never be overwritten by unrelated v1 rows.
        r.progression.m_State = copy.deepcopy(original)
        r.progression.m_State.Players[0].Forage = 99
        self.assertFalse(r.progression.HCMigrate(r.now))
        self.assertEqual(original,r.files['synthetic/progression.v1.json'])
        # An archive write fault must leave the legacy DTO unmodified.
        broken = SyntheticRuntime()
        broken.progression.m_State = copy.deepcopy(original)
        broken.save = lambda *args:False
        broken.env['HCV2ThreatStore'].Save = broken.save
        self.assertFalse(broken.progression.HCMigrate(broken.now))
        self.assertEqual(original,broken.progression.m_State)

    def test_zero_or_unavailable_character_id_skips_without_shared_row_and_logs_once(self):
        r = SyntheticRuntime()
        r.start()
        # Execute the authored encoder with explicitly synthetic native out integers.
        native = POLICY.read_text().replace('player.GetPersistentID(part1, part2, part3, part4);',
            'part1 = player.parts[0]; part2 = player.parts[1]; part3 = player.parts[2]; part4 = player.parts[3];')
        from tests.unit.test_admin_test_kit import rewrite_tostring
        encoder = translate(rewrite_tostring(native),'HCCharacterKey',
            dict(HCSurvivalRuntime=N(HCIsServer=lambda:True),str=str),'HCSurvivalRuntime')
        self.assertEqual('',encoder(None),'unavailable character has no generation')
        self.assertEqual('',encoder(N(parts=(0,0,0,0))))
        r.env['HCSurvivalRuntime'].HCCharacterKey = lambda p:encoder(p)
        for index in range(1,6):
            player = r.player(index)
            player.parts = (0,0,0,0)
            self.assertEqual(0,r.progression.HCAwardForage(player))
            r.progression.HCObserveDeath(player)
        self.assertEqual([],r.progression.m_State.Players)
        lines = [line for line in r.logs if '[HC Plan]' in line and 'character_id_unavailable' in line]
        self.assertEqual(1,len(lines),'unknown IDs produce one bounded diagnostic per start')
        r.progression.OnStop()
        r.progression.OnStart(r.settings)
        self.assertEqual(0,r.progression.HCAwardForage(player))
        lines = [line for line in r.logs if '[HC Plan]' in line and 'character_id_unavailable' in line]
        self.assertEqual(2,len(lines),'a later Start gets one fresh bounded diagnostic')
        player.parts = (1,2,3,4)
        self.assertEqual(1,r.progression.HCAwardForage(player))
        self.assertEqual('c:1:2:3:4',r.progression.m_State.Players[0].CharacterKey)

    def test_pickup_marks_dirty_then_interval_and_stop_flush(self):
        for stop in (False,True):
            with self.subTest(stop=stop):
                r = SyntheticRuntime()
                r.players.Insert(r.player())
                r.start()
                r.forage.OnTick(10)
                writes = len(r.writes)
                item = r.created[0]
                item.owner = r.players[0]
                r.forage.HCObserveCollection(item,item.owner)
                self.assertEqual(writes,len(r.writes),'pickup must not synchronously save')
                self.assertTrue(r.forage.m_Dirty)
                self.assertTrue(r.progression.m_Dirty)
                self.assertFalse(r.forage.m_SaveJob.HCDirty,'pickup must wait for interval')
                if stop:
                    r.forage.OnStop()
                    r.progression.OnStop()
                else:
                    r.players = EArray()  # HC-33 supply is all-season; no player means no new candidate in this interval.
                    r.now += 59
                    r.forage.OnTick(10)
                    r.progression.OnTick(1)
                    self.assertFalse(r.forage.m_SaveJob.HCDirty)
                    self.assertFalse(r.progression.m_SaveJob.HCDirty)
                    self.assertEqual(writes,len(r.writes))
                    r.now += 1
                    r.forage.OnTick(10)
                    r.progression.OnTick(1)
                    self.assertTrue(r.forage.m_SaveJob.HCDirty)
                    self.assertTrue(r.progression.m_SaveJob.HCDirty)
                    self.assertTrue(r.flush(r.forage.m_SaveJob))
                    self.assertTrue(r.flush(r.progression.m_SaveJob))
                    r.now += 59
                    r.progression.HCAwardForage(item.owner)
                    r.progression.OnTick(1)
                    self.assertFalse(r.progression.m_SaveJob.HCDirty)
                self.assertEqual(writes+2,len(r.writes))
                self.assertEqual(1,r.files['synthetic/progression'].Players[0].Forage)
                self.assertEqual(r.forage.m_Dirty,False)

    def test_configurable_oldest_first_cap_and_absent_zero_default(self):
        for cap in (0,2):
            with self.subTest(cap=cap):
                r = SyntheticRuntime()
                r.settings.MaxFamiliarityRows = cap
                r.progression.m_RowCap = 7  # A reused module must still apply zero/default.
                r.start()
                self.assertEqual(cap or 128,r.progression.m_RowCap)
                for index in range(1,5):
                    r.progression.HCAwardForage(r.player(index,life='c:1:2:3:'+str(index)))
                    r.now += 60
                rows = r.progression.m_State.Players
                self.assertEqual(min(cap or 128,4),len(rows))
                if cap:
                    self.assertEqual([r.player(3).uid,r.player(4).uid],[row.Key for row in rows])
                    # A recently reset dead row is newer than the oldest gain.
                    r.progression.HCObserveDeath(r.player(3,life='c:1:2:3:3'))
                    r.now += 60
                    r.progression.HCAwardForage(r.player(5,life='c:1:2:3:5'))
                    self.assertEqual([r.player(3).uid,r.player(5).uid],[row.Key for row in rows])
        # Missing JSON integers are zero; reject negatives and oversized explicit bounds.
        import json
        from tools.validate.runtime import validate_settings
        settings = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())
        for cap in (0,1,128):
            self.assertEqual([],validate_settings(dict(settings,MaxFamiliarityRows=cap)))
        for cap in (-1,129,True,1.5):
            self.assertTrue(validate_settings(dict(settings,MaxFamiliarityRows=cap)))

    def test_stop_and_start_reset_deferred_even_when_disabled(self):
        r = SyntheticRuntime()
        r.start()
        r.forage.m_Deferred = 40
        r.forage.OnStop()
        self.assertEqual(0,r.forage.m_Deferred,'Stop must reset deferred receipts')
        r.forage.m_Deferred = 23
        r.settings.EnableForage = False
        r.forage.OnStart(r.settings)
        self.assertEqual(0,r.forage.m_Deferred,'disabled Start must reset deferred receipts')
        r.settings.EnableForage = True
        r.forage.m_Deferred = 19
        r.forage.OnStart(r.settings)
        self.assertTrue(r.forage.m_Healthy)
        self.assertEqual(0,r.forage.m_Deferred)


    def test_lowered_cap_prunes_loaded_rows_and_persists_before_start(self):
        r = SyntheticRuntime()
        r.start()
        for index in range(1,5):
            r.progression.HCAwardForage(r.player(index,life='c:1:2:3:'+str(index)))
            r.now += 60
        r.progression.OnStop()
        r.settings.MaxFamiliarityRows = 2
        r.progression.OnStart(r.settings)
        self.assertTrue(r.progression.m_Healthy)
        keys = [r.player(3).uid,r.player(4).uid]
        self.assertEqual(keys,[row.Key for row in r.progression.m_State.Players])
        self.assertEqual(keys,[row.Key for row in r.files['synthetic/progression'].Players])
        self.assertEqual(0,r.progression.m_Cursor)
