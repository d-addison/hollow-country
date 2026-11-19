"""HC-44 spec -> plan -> task: one durable causal trace per shared fact.

Assigned HC-44 brief is the slice specification; HC-11 owns shared trace docs.
The two AGENTS.md spec paths are absent. Plan: reserve observed fact identity
before Paper creation, retain tombstones after cleanup/restart, bind only real
corpses without touching native inventory/lifetime; never synthesize a death.
Explicit synthetic stdlib ports execute authored Enforce handlers through the
existing restricted translator. Offline success is never DayZ acceptance.

Actual RED/GREEN (2026-11-18), exact focused command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_causal_traces -v
RED before Enforce edits: AssertionError: namespace(...) is not None :
  duplicate fact spawned another physical causal trace. Ran 1; FAILED (failures=1).
Additional same-test REDs: expired active row must release its bounded reference;
  global10 bound includes body traces as well as notes;
  lost body receipt must quarantine rather than permit replay.
GREEN with the implementation: Ran 1 test; OK. runtime=PENDING.
Shared spec/plan/task trace: .banso-writer/inputs/task.md HC-44;
HC-11 owns integration into shared spec/plan/tasks (legacy paths absent).
"""
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
LEADS = ROOT / 'mods/HollowCountry/scripts/4_World/Leads'


def syntax(source):
    # Language/type spellings only; no feature policy in this adapter.
    source = re.sub(r'\b(HCLeadData|HCLeadStore|HCLeadPolicy|HCLeadNote|HCLeadModule|HCTraceReceipt|HCBodyStoryRow|HCBodyStories|HCWorldPlace|HCWorldFact|HCWorldLead|HCWorldLimits|HCWorldModule|HCWorldClock|HCWorldStore|HCNoteEntities|HCNoteLedger|Man|Paper|WrittenNoteData)\b', r'HCEvent\1', source)
    source = source.replace('if (text == "" || !JsonFileLoader<HCEventHCLeadData>.LoadData(text, value, error))',
        'value = NativeDecode(text); if (text == "" || !value)')
    source = source.replace('if (!JsonFileLoader<HCEventHCLeadData>.MakeData(Data, m_PendText, error))',
        'm_PendText = NativeEncode(m_Data); if (m_PendText == "")')
    source = source.replace('.RemoveItem(', '.remove(')
    source = source.replace('s_Instance', 'm_StaticInstance')
    source = re.sub(r'(?<![\w.])Data\b', 'm_Data', source)
    source = source.replace('new array<ref HCEventHCWorldFact>;', 'new array<ref HCEventHCWorldFact>();')
    source = re.sub(r'([\w.]+)\+\+;', r'\1 = \1 + 1;', source)
    return source


class Fixture:
    """Synthetic native handles, world facts, files and save failures."""
    def __init__(self, image=None):
        self.now, self.fail, self.server = 10000, False, True
        self.created, self.images, self.logs, self.deleted = [], [], [], []
        self.facts = EArray([N(Kind='shots_heard', PlaceId='kamenka', Severity=1, At=8000, Expires=20000)])
        self.store = N(Data=copy.deepcopy(image) if image else N(SchemaVersion=1, Serial=0, LastWrite=0,
            TraceVersion=1, TraceAfter=0, Traces=EArray(), Notes=EArray(), Bodies=EArray(), Leads=EArray(), Channels=EArray()),
            m_Healthy=True, m_DuplicateRefusals=0, m_LastTraceRefusal='', m_Facts=EArray(),
            Healthy=lambda: self.store.m_Healthy)
        self.store.m_Data = self.store.Data
        self.store.Save = self.save
        self.store.NextId = self.next_id
        self.entities = {}
        self.game = N(IsServer=lambda: self.server, CreateObjectEx=self.create,
                      ObjectDelete=self.deleted.append, GetTime=lambda: 10)
        self.world = N(GetRecentFacts=lambda age, output: (output.clear(), output.extend(self.facts)))
        self.env = dict(EArray=EArray, Print=self.logs.append, GetGame=lambda: self.game,
            HCEventHCWorldClock=N(UTC=lambda: self.now),
            HCEventHCWorldLimits=N(NOTES=10, FACT_LIFETIME=604800, Token=lambda s: bool(s) and len(s) <= 96,
                Position=lambda pos: True),
            HCEventHCWorldModule=N(Get=lambda: self.world),
            HCEventHCNoteEntities=N(Find=self.entities.get),
            HCEventPaper=N(Cast=lambda p: p), ECE_PLACE_ON_SURFACE=1,
            HCEventHCBodyStories=N(Get=lambda: None),
            HCEventHCLeadNote=lambda: N(Row=N(Id='', SceneId='', EntityRef='', CreatedAt=0, TextId=''),
                Lead=None, Expires=0, Phase=0, NativeText=''),
            HCEventHCTraceReceipt=lambda: N(FactId='', SceneId='', NoteId='', BodyId=''),
            HCEventHCWorldLead=lambda: N(Id='', Kind='', TargetPlaceId='', Source='', GroupId='', Expires=0, TextId=''),
            HCEventHCBodyStoryRow=lambda: N(Id='', SceneId='', PlaceId='', Position=[0,0,0], CreatedAt=0, Expires=0, Phase=0, FactId=''),
            HCPerfPlayers=N(HCGet=lambda: EArray()),
            HCObserverTransitionGate=N(CanTransition=lambda pos, distance: True),
            HCEventHCLeadStore=N(Get=lambda: self.store),
            HCV2Admission=N(Line=lambda *args: 'synthetic admission'), HCV2Gates=N(Qualified=lambda gate: False))
        self.policy = N(Place=lambda place: N(Name='Kamenka') if place == 'kamenka' else None)
        self.env['HCEventHCLeadPolicy'] = self.policy
        for name in ('KnownPlace', 'Valid', 'Kind', 'Build', 'Copy', 'Text', 'LegacyText', 'FactionName'):
            setattr(self.policy, name, translate(syntax((LEADS/'HCLeadModule.c').read_text()), name,
                self.env, 'HCEventHCLeadPolicy'))
        self.bind(self.store, 'HCLeadStore.c', 'HCLeadStore',
            ('HCTrace', 'HCFactId', 'HCResolveFact', 'HCReserveTrace', 'HCTraceRefuse', 'HCTraceText', 'HCTraceValid', 'HCSceneTraces', 'HCPlan'))
        self.notes = N(m_Store=self.store, m_Ready=True, m_LastCount=-1, m_LogElapsed=0,
            m_Status=N(HCPublish=lambda *args: None), m_LastRefusal='', m_Elapsed=0,
            m_Units=N(HCReset=lambda *args: None, HCTake=lambda cost: True),
            m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True), m_Cursor=0,
            RadioFallback=lambda lead: None, LogCount=lambda: None)
        self.bind(self.notes, 'HCNoteLedger.c', 'HCNoteLedger', ('CanCreate', 'Scene', 'Create', 'HCText', 'HCRefuse'))

    def bind(self, obj, filename, owner, names):
        from types import MethodType
        source = syntax((LEADS/filename).read_text())
        for name in names:
            if re.search(r'\b'+name+r'\(', source):
                fn = translate(source, name, self.env, 'HCEvent'+owner, member=True)
                setattr(obj, name, MethodType(fn, obj))

    def next_id(self, prefix):
        self.store.Data.Serial += 1
        return prefix+'-'+str(self.store.Data.Serial)

    def save(self):
        if self.fail:
            self.store.m_Healthy = False
            return False
        self.images.append(copy.deepcopy(self.store.Data))
        return True

    def create(self, kind, position, flags):
        paper = N(text='', position=position, owner=None)
        paper.GetWrittenNoteData = lambda: N(SetNoteText=lambda text: setattr(paper, 'text', text),
                                              GetNoteText=lambda: paper.text)
        paper.HCAssignNote = lambda ident: self.entities.update({ident: paper})
        paper.GetHierarchyParent = lambda: paper.owner
        paper.SetLifetime = lambda seconds: None
        self.created.append(paper)
        return paper

    def offer(self, at=8000):
        return N(Id='shots_heard-kamenka-'+str(at), Source='world', Kind='DANGER',
                 TargetPlaceId='kamenka', TextId='shots_heard', GroupId='', Expires=20000)

    def storage_port(self, disk=None, fail_copy=False):
        """Synthetic native file/JSON output ports, no persistence policy."""
        self.disk = {} if disk is None else disk
        self.store.m_Path = 'synthetic/leads.json'
        self.store.m_SaveStage = self.store.m_Revision = self.store.m_SnapshotRevision = 0
        self.store.m_PendText = self.store.m_PendPrior = ''
        self.store.m_SaveJob = N(HCDirty=False, HCInFlight=False)
        self.store.m_StaticInstance = None
        defaults = copy.deepcopy(Fixture().store.Data)
        def dto(value):
            if isinstance(value, dict): return N(**{k: dto(v) for k,v in value.items()})
            if isinstance(value, list): return EArray(dto(v) for v in value)
            return value
        def decode(text):
            try:
                values = json.loads(text)
                return dto(dict(vars(defaults), **values))
            except (ValueError, TypeError):
                return None
        def encode(data):
            return json.dumps(data, default=lambda row: vars(row), sort_keys=True)
        self.env.update(NativeDecode=decode, NativeEncode=encode,
            HCEventHCLeadData=lambda: copy.deepcopy(defaults),
            HCLeadSaveJob=lambda: N(Owner=None, HCDirty=False, HCInFlight=False),
            HCSaveJob=N(STEP_MORE=1, STEP_DONE=0, STEP_FAILED=2),
            HCSaveScheduler=N(HCRegister=lambda job: None, HCUnregister=lambda job: None,
                              HCFlush=lambda job: self.store.Save()),
            FileExist=lambda path: path in self.disk,
            MakeDirectory=lambda path: True,
            DeleteFile=lambda path: self.disk.pop(path, None) is not None,
            CopyFile=lambda src, dest: False if fail_copy else self.disk.update({dest: self.disk[src]}) or True,
            HCEventHCWorldStore=N(MAX_BYTES=1048576, Read=lambda path: self.disk.get(path, ''),
                Write=lambda path, text: self.disk.update({path: text}) or True))
        self.bind(self.store, 'HCLeadStore.c', 'HCLeadStore',
            ('Valid', 'Decode', 'Fault', 'HCRequestCheckpoint', 'HCCloseCheckpoint',
             'HCSaveFailed', 'HCCheckpointStep', 'Save', 'Open'))
        return encode


class CausalTraces(unittest.TestCase):
    def test_duplicate_fact_cannot_materialize_second_trace_after_restart_or_cleanup(self):
        f = Fixture()
        first = f.notes.Create('scene-a', [100,0,100], f.offer())
        self.assertIsNotNone(first)
        self.assertIsNone(f.notes.Create('scene-b', [200,0,200], f.offer()),
                          'duplicate fact spawned another physical causal trace')
        self.assertEqual(1, len(f.created))
        self.assertIn('[HC trace '+f.offer().Id+']', first.text)
        self.assertEqual(1, len(f.images[0].Traces), 'receipt and note intent share the barrier')
        self.assertEqual(0, f.images[0].Notes[0].Phase)
        self.assertEqual(f.images[0].Notes[0].Row.Id, f.images[0].Traces[0].NoteId)
        self.assertEqual(1, f.store.m_DuplicateRefusals)
        restarted = Fixture(f.images[-1])
        self.assertIsNone(restarted.notes.Create('scene-c', [300,0,300], restarted.offer()))
        self.assertEqual([], restarted.created)
        # Physical cleanup releases a slot; the fact tombstone never releases.
        restarted.store.Data.Notes.clear()
        restarted.save()
        cleaned = Fixture(restarted.images[-1])
        self.assertIsNone(cleaned.notes.Create('scene-d', [400,0,400], cleaned.offer()))
        self.assertEqual(1, len(cleaned.store.Data.Traces))
        self.assertTrue(any('HC-44 facts=1 traces=0 duplicate_refusals=1' in line
                            and 'runtime=PENDING' in line for line in cleaned.logs))
        # Independent causes at the same place remain independent; their native
        # text differs so reloaded Papers cannot alias another fact's receipt.
        newer = copy.deepcopy(f.facts[0]); newer.At = 8100
        f.facts.append(newer)
        second = f.notes.Create('scene-new', [110,0,110], f.offer(8100))
        self.assertIsNotNone(second)
        self.assertNotEqual(first.text, second.text)
        self.assertEqual(2, len(f.store.Data.Traces))
        # Refuse scene-only, counterfeit, future/recent and expired causes.
        for mode in ('scene', 'forged', 'future', 'recent', 'expired', 'client', 'legacy'):
            x = Fixture(); offer = x.offer()
            if mode == 'scene': offer.Source = 'scene'
            if mode == 'forged': offer.TextId = 'BODY_FOUND'
            if mode == 'future': x.facts[0].At = 11000
            if mode == 'recent': x.facts[0].At = 9500
            if mode == 'expired': x.facts[0].Expires = 9999
            if mode == 'client': x.server = False
            if mode == 'legacy': x.store.Data.TraceAfter = 9000
            self.assertIsNone(x.notes.Create('scene-'+mode, [0,0,0], offer), mode)
            self.assertEqual([], x.created, mode)
        # One note per scene, global10; history fills without forgetting old
        # outcomes. No cap check is permission to mint a new cache or corpse.
        x = Fixture()
        self.assertIsNotNone(x.notes.Create('scene-one', [0,0,0], x.offer()))
        x.facts.append(newer)
        self.assertIsNone(x.notes.Create('scene-one', [0,0,0], x.offer(8100)))
        x = Fixture(); x.store.Data.Notes[:] = [N(Row=N(SceneId='other'))]*10
        self.assertIsNone(x.notes.Create('scene-cap', [0,0,0], x.offer()))
        x = Fixture(); x.store.Data.Notes[:] = [N(Row=N(SceneId='other'))]*7
        x.store.Data.Bodies[:] = [N(SceneId='other')]*3
        self.assertIsNone(x.notes.Create('scene-total-cap', [0,0,0], x.offer()),
                          'global10 bound includes body traces as well as notes')
        x = Fixture(); x.store.Data.Bodies[:] = [N(SceneId='scene-three')]*3
        self.assertIsNone(x.notes.Create('scene-three', [0,0,0], x.offer()),
                          'per-scene3 includes existing body traces')
        x = Fixture(); x.store.Data.Traces[:] = [N(FactId='other')]*256
        self.assertIsNone(x.notes.Create('scene-history-cap', [0,0,0], x.offer()))
        self.assertIn('TRACE_HISTORY_CAP_NO_EVICTION', x.logs[-1])
        # An interrupted creation reserves a fact without materializing/retrying.
        x = Fixture(); x.fail = True
        self.assertIsNone(x.notes.Create('scene-fault', [0,0,0], x.offer()))
        self.assertEqual([], x.created)
        self.assertEqual(1, len(x.store.Data.Traces))
        self.assertFalse(x.store.Healthy())
        x = Fixture(); x.game.CreateObjectEx = lambda *args: None
        self.assertIsNone(x.notes.Create('scene-spawn-fault', [0,0,0], x.offer()))
        self.assertEqual(0, len(x.store.Data.Notes))
        restored_failure = Fixture(x.images[-1])
        self.assertIsNone(restored_failure.notes.Create('scene-no-refill', [0,0,0], restored_failure.offer()))
        self.assertEqual([], restored_failure.created)
        # Body port observes actual native death. It never spawns a substitute,
        # copies inventory, extends lifetime or emits an invented BODY_FOUND.
        body = N(IsPendingDeletion=lambda: False, IsMan=lambda: True, IsAlive=lambda: False,
                 GetIdentity=lambda: None, GetPosition=lambda: [100,0,100])
        f.env['HCEventMan'] = N(Cast=lambda corpse: corpse)
        owner = N(m_Ready=True, m_Store=f.store, m_StaticRefused=False, m_Observed=EArray(),
                  m_ObservedIds=EArray(), m_Cursor=0, m_Elapsed=0,
                  m_Units=f.notes.m_Units, m_Work=f.notes.m_Work,
                  m_Status=N(HCPublish=lambda *args: None))
        f.bind(owner, 'HCBodyStories.c', 'HCBodyStories', ('Consider', 'HCObserveBody', 'OnTick', 'OnStop'))
        owner.Consider('scene-random', [0,0,0], f.offer())
        self.assertIn('STATIC_DEATH_UNOBSERVED', f.logs[-1])
        self.assertEqual(2, len(f.created))
        self.assertTrue(owner.HCObserveBody('scene-a', f.offer(), body))
        self.assertFalse(owner.HCObserveBody('scene-a', f.offer(), body))
        self.assertEqual(1, len(f.store.Data.Bodies))
        self.assertEqual(2, len(f.store.Data.Traces), 'bound corpse shares the original note receipt')
        self.assertEqual(2, f.store.Data.Bodies[0].Phase)
        f.store.Data.Bodies[0].Expires = f.now
        f.store.HCRequestCheckpoint = lambda: None
        owner.OnTick(20)
        self.assertEqual([], f.store.Data.Bodies)
        self.assertEqual([], owner.m_Observed, 'expired active row must release its bounded reference')
        self.assertEqual([], f.deleted, 'native corpse cleanup stays with CE/provider')
        self.assertFalse(owner.HCObserveBody('scene-a', f.offer(), body), 'expired receipt cannot rebind body')
        for mode in ('alive', 'player', 'not-human', 'deleted', 'unknown'):
            candidate = copy.copy(body)
            if mode == 'alive': candidate.IsAlive = lambda: True
            if mode == 'player': candidate.GetIdentity = lambda: N()
            if mode == 'not-human': candidate.IsMan = lambda: False
            if mode == 'deleted': candidate.IsPendingDeletion = lambda: True
            if mode == 'unknown': candidate = None
            self.assertFalse(owner.HCObserveBody('scene-new', f.offer(8100), candidate), mode)
        owner.OnStop()
        self.assertFalse(owner.HCObserveBody('scene-new', f.offer(8100), body))
        owner.OnTick(100)
        self.assertEqual([], f.deleted)

        # Execute the shipping validity/decoder and staged writer through
        # synthetic JSON/file ports; no OS durability or DayZ persistence proof.
        x = Fixture(f.images[0]); encode = x.storage_port()
        self.assertTrue(x.store.Valid(x.store.Data))
        body_only = Fixture(f.images[-1]); body_only.storage_port()
        body_only.store.Data.Notes.clear()
        body_only.store.Data.Traces.clear()
        self.assertFalse(body_only.store.Valid(body_only.store.Data),
                         'lost body receipt must quarantine rather than permit replay')
        encoded = encode(x.store.Data)
        decoded = x.store.Decode(encoded)
        self.assertEqual(x.offer().Id, decoded.Traces[0].FactId)
        corrupt = json.loads(encoded)
        corrupt['Traces'].append(corrupt['Traces'][0])
        self.assertIsNone(x.store.Decode(json.dumps(corrupt)), 'duplicate persisted fact quarantines')
        corrupt = json.loads(encoded); del corrupt['Traces']
        self.assertIsNone(x.store.Decode(json.dumps(corrupt)), 'truncation cannot default to empty receipts')
        corrupt = json.loads(encoded); del corrupt['TraceAfter']
        self.assertIsNone(x.store.Decode(json.dumps(corrupt)))
        # Legacy images retain active slots but refuse all pre-migration facts.
        legacy = Fixture(); legacy.storage_port()
        old = encode(legacy.store.Data)
        old_dict = json.loads(old)
        for key in ('TraceVersion', 'TraceAfter', 'Traces'): del old_dict[key]
        legacy_data = legacy.store.Decode(json.dumps(old_dict))
        self.assertEqual(legacy.now, legacy_data.TraceAfter)
        legacy.store.Data = legacy.store.m_Data = legacy_data
        self.assertIsNone(legacy.notes.Create('scene-legacy', [0,0,0], legacy.offer()))
        self.assertEqual([], legacy.created)
        # Staged routine writes serialize/read/commit; only commit creates intent.
        x.store.HCRequestCheckpoint()
        self.assertEqual(1, x.store.HCCheckpointStep())
        self.assertEqual({}, x.disk)
        self.assertEqual(1, x.store.HCCheckpointStep())
        self.assertEqual({}, x.disk)
        self.assertEqual(0, x.store.HCCheckpointStep())
        self.assertIn('synthetic/leads.json', x.disk)
        self.assertNotIn('synthetic/leads.json.tmp', x.disk)
        # A cleanup between stages invalidates the snapshot, then checkpoints
        # the current state while preserving its permanent tombstone.
        x.store.HCRequestCheckpoint()
        self.assertEqual(1, x.store.HCCheckpointStep())
        self.assertEqual(1, x.store.HCCheckpointStep())
        x.store.Data.Notes.clear(); x.store.HCRequestCheckpoint()
        self.assertEqual(1, x.store.HCCheckpointStep())
        self.assertTrue(x.store.Save(), 'barrier cancels an older routine snapshot')
        primary = json.loads(x.disk['synthetic/leads.json'])
        self.assertEqual([], primary['Notes'])
        self.assertEqual(1, len(primary['Traces']))
        # Open executes native-like decode of the exact persisted receipt. It
        # never recreates an entity, including a restart after reservation only.
        reopened = Fixture(); reopened.storage_port(dict(x.disk))
        self.assertTrue(reopened.store.Open())
        self.assertIsNone(reopened.notes.Create('scene-after-open', [0,0,0], reopened.offer()))
        self.assertEqual([], reopened.created)
        # Interrupted/corrupt saves quarantine and retain the intent/receipts.
        for files in ({'synthetic/leads.json.tmp': encoded},
                      {'synthetic/leads.json.bak': encoded},
                      {'synthetic/leads.json': '{}'}):
            damaged = Fixture(); damaged.storage_port(files)
            self.assertFalse(damaged.store.Open())
            self.assertFalse(damaged.store.Healthy())
            self.assertEqual([], damaged.created)
        failed = Fixture(f.images[0]); failed.storage_port(fail_copy=True)
        self.assertFalse(failed.store.Save())
        self.assertIn('synthetic/leads.json.tmp', failed.disk)
        self.assertEqual(1, len(failed.store.Data.Traces))
        self.assertFalse(failed.store.Healthy())


if __name__ == '__main__':
    unittest.main()
