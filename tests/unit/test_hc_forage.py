"""HC-12 synthetic ports execute authored handlers; no DayZ/visibility proof.

Actual RED (2026-11-18):
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_forage -v
  AssertionError: unexpectedly None : >40 travelled records blocks forever
Follow-up RED, same command:
  AssertionError: [] is not true : pickup cooldown must be durable before callback returns
Follow-up RED, same command:
  AssertionError: 19 != 0 : retirement must retain the next maintenance row
GREEN: same command, Ran 1 test, OK. Native acceptance remains PENDING.

HC-33 actual RED (2026-11-18), same focused command:
  AssertionError: Lists differ: ['SambucusBerry'] != []
  + [] : HC-33 all-season supply must ignore visual/calendar month
HC-33 GREEN: same command, Ran 1 test, OK. Native acceptance remains PENDING.
"""
import functools
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_admin_test_kit import rewrite_tostring
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Forage/HCForage.c'


def bind(path, cls, obj, env, names, source=None):
    from tests.unit.test_c3_survivalcfg import config_ports
    env.update(config_ports())  # Explicit synthetic default profile.
    if source is None:
        source = path.read_text()
    match = re.search(r'(?:modded )?class ' + cls + r'\b[^\{]*\{', source)
    source = body(source, match.end())
    # Syntax only: extend the existing restricted port's accepted type names
    # and integer for-loop spelling. Every decision remains in authored bodies.
    source = re.sub(r'\b(HC(?:Forage|Progression)\w*|HCSurvival\w*)\b', r'HCEvent\1', source)
    source = re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',
                    r'foreach (int \1 : range(\2, \3))', source)
    source = re.sub(r'\bint (\w+) = ([^;\n]+/[^;\n]+);', r'int \1 = native_int(\2);', source)
    source = re.sub(r'HCV2ThreatStore<\w+>', 'HCV2ThreatStore', source)
    source = source.replace('s_HCInstance', 'native_static.Instance')
    # Syntax-only nested else-if for the existing restricted translator.
    source = re.sub(r"else if (\([^\n]+\))\s*\{([^{}]*)\}", r"else { if \1 {\2} }", source)
    source = rewrite_tostring(source)
    renamed_env = {re.sub(r'^(HC(?:Forage|Progression)\w*|HCSurvival\w*)$', r'HCEvent\1', k): v
                   for k, v in env.items()}
    renamed_env.setdefault('native_int', int)
    renamed_env.setdefault('native_static', N(Instance=None))
    for name in names:
        fn = translate(source, name, renamed_env, cls, member=True)
        setattr(obj, name, functools.partial(fn, obj))
    return obj


class ForageTravel(unittest.TestCase):
    def test_travel_reclaims_only_expired_unowned_records_and_exact_pickup(self):
        now = 5000
        nodes = EArray()
        spots = EArray()
        logs = []
        saved = []
        rewards = []
        policy = N()
        env = dict(range=range, str=str, EArray=EArray, Print=logs.append,
                   HCEcologyMigrationNative=N(PointHidden=lambda *args:True),
                   RECORD_CAP=40, LIVE_CAP=40, Math=N(Floor=math.floor, RandomInt=lambda lo, hi: 0),
                   HCSurvivalPolicy=policy,
                   HCSaveJob=N(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2),
                   HCV2ThreatStore=N(Save=lambda *args: saved.append(args[1]) or True),
                   PATH='synthetic/forage',
                   HCForageState=lambda: N(Version=1, WorldName='chernarusplus', Spots=EArray()),
                   HCSurvivalRuntime=N(HCIsServer=lambda: True),
                   HCProgressionModule=N(HCRecordForage=lambda player: rewards.append(player) or 0),
                   HCGroupClock=N(Utc=lambda: now),
                   HCWorldLimits=N(Position=lambda pos: True),
                   HCForageSpot=lambda: N(CellX=0, CellZ=0, NodeSlot=0, ReadyUtc=0),
                   HCForageNode=lambda: N(Spot=None, Item=None, WasLive=False))
        from tests.unit.test_c3_survivalcfg import config_ports
        env.update(config_ports())
        for name in ('CanRefill', 'DecayedFamiliarity', 'ForageDelay'):
            setattr(policy, name, translate((ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCSurvivalPolicy.c').read_text(), name, env, 'HCSurvivalPolicy'))
        module = N(m_Nodes=nodes, m_State=N(Version=1, WorldName='chernarusplus', Spots=spots), m_Healthy=True,
                   m_Dirty=False, m_LastUtc=now, m_NodeCursor=20, m_Deferred=0,
                   RECORD_CAP=40, LIVE_CAP=40, m_Revision=0, m_SaveStage=0, m_Snapshot=None, m_SnapshotRevision=0,
                   m_SaveJob=N(HCDirty=False))
        def flush(job):
            for _ in range(16):
                result = module.HCStepCheckpoint()
                if result != 1:
                    job.HCDirty = False
                    return result == 0
            return False
        env['HCSaveScheduler'] = N(HCFlush=flush)
        module.HCPosition = lambda *args: (0, 0, 0)
        module.HCClearCandidate = lambda pos: True  # SYNTHETIC geometry port, never visibility evidence.
        module.HCFail = lambda: self.fail('unexpected authored refusal')
        bind(SOURCE, 'HCForageModule', module, env,
             ('HCSelectCandidate', 'HCObserveCollection', 'HCReleaseNode', 'HCChanged', 'HCStepCheckpoint', 'HCFlush'))
        for index in range(40):
            spot = N(CellX=index, CellZ=0, NodeSlot=0, ReadyUtc=now-1)
            node = N(Spot=spot, Item=None, WasLive=False)
            nodes.Insert(node)
            spots.Insert(spot)
        protected = nodes[:3]
        protected[0].Item = N()  # Live ownership remains.
        protected[1].Spot.ReadyUtc = now+100  # Spent/cooldown evidence remains.
        protected[2].WasLive = True  # Missing handle awaits release; cannot be retired.
        player = N(IsAlive=lambda: True, GetPosition=lambda: (50*200, 0, 0))
        selected = module.HCSelectCandidate(player, 0, now)
        self.assertIsNotNone(selected, '>40 travelled records blocks forever')
        self.assertEqual(19, module.m_NodeCursor, 'retirement must retain the next maintenance row')
        self.assertEqual(40, len(nodes))
        self.assertEqual(40, len(spots))
        for node in protected:
            self.assertIn(node, nodes)
        # Repeated travel well past the record cap continues, with no cooldown reset.
        for cell in range(51, 71):
            player.GetPosition = lambda cell=cell: (cell*200, 0, 0)
            selected = module.HCSelectCandidate(player, 0, now)
            self.assertIsNotNone(selected)
            self.assertEqual(now+1800, selected.Spot.ReadyUtc)
            self.assertEqual(40, len(nodes))
        exact = N(GetHierarchyRootPlayer=lambda: player)
        selected.Item, selected.WasLive = exact, True
        unrelated = N(GetHierarchyRootPlayer=lambda: player)
        module.HCObserveCollection(unrelated, player)
        self.assertIs(exact, selected.Item)
        module.HCObserveCollection(exact, player)
        self.assertIsNone(selected.Item)
        self.assertFalse(saved, 'pickup batches its cooldown update')
        self.assertTrue(module.HCFlush())
        self.assertTrue(saved, 'checkpoint must preserve the updated cooldown')
        self.assertEqual(selected.Spot.ReadyUtc, saved[-1].Spots[-1].ReadyUtc)
        ready = selected.Spot.ReadyUtc
        module.HCObserveCollection(exact, player)  # Re-drop never rewards or shortens cooldown.
        self.assertEqual(ready, selected.Spot.ReadyUtc)
        self.assertEqual([player], rewards)
        # All records owned/pending/cooling: no eviction, bounded deferral.
        for node in nodes:
            node.Spot.ReadyUtc = now+100
        before = list(nodes)
        player.GetPosition = lambda: (72*200, 0, 0)
        self.assertIsNone(module.HCSelectCandidate(player, 0, now))
        self.assertEqual(before, nodes)
        now += 100  # Exact expiry boundary permits retirement, never before it.
        self.assertIsNotNone(module.HCSelectCandidate(player, 0, now))
        self.assertEqual(40, len(nodes))
        self.assertIn(protected[0], nodes)
        self.assertIn(protected[2], nodes)
        # Legacy table remains callable; HC-33 runtime supply ignores calendar dates.
        bind(SOURCE, 'HCForageModule', module, env, ('HCSeasonalType',))
        self.assertEqual('', module.HCSeasonalType(1, 0))
        self.assertEqual('SambucusBerry', module.HCSeasonalType(6, 0))

        # HC-33: same authored tick, synthetic native/store/budget ports. Each
        # fixture starts empty, so cooldown/record exhaustion cannot mask supply.
        from tests.unit.test_hc_forage_round2 import SyntheticRuntime
        for month in range(1, 13):
            runtime = SyntheticRuntime()
            runtime.month = month
            runtime.players.Insert(runtime.player())
            runtime.start()
            runtime.forage.OnTick(10)
            self.assertEqual(['SambucusBerry'], [item.kind for item in runtime.created],
                             'HC-33 all-season supply must ignore visual/calendar month')
            self.assertTrue(any('[HC Plan] HC-33 native_routes=' in line and
                                'runtime=PENDING' in line for line in runtime.logs))
        runtime = SyntheticRuntime()
        runtime.settings.EnableForage = False
        runtime.forage.OnStart(runtime.settings)
        runtime.forage.OnTick(10)
        self.assertIsNone(runtime.forage.m_Nodes)
        self.assertFalse(runtime.writes or runtime.created)
        self.assertTrue(any('[HC Plan] HC-33' in line and 'state=off' in line for line in runtime.logs))
        # Every slot/roll keeps orchard fruit and the five stock generator children native-only.
        for slot in range(3):
            for roll in range(10):
                runtime = SyntheticRuntime()
                runtime.month, runtime.roll = 10, roll
                runtime.players.Insert(runtime.player())
                runtime.start()
                runtime.forage.m_SlotCursor = slot
                runtime.forage.OnTick(10)
                self.assertEqual(1, len(runtime.created))
                self.assertIn(runtime.created[0].kind, ('CaninaBerry', 'SambucusBerry', 'Cannabis', 'AmanitaMushroom', 'AuriculariaMushroom', 'CraterellusMushroom', 'PsilocybeMushroom'))

        # Dispositions feed the existing small route report. These are authored
        # routes, never additional CE usages or an observed acquisition receipt.
        from tools.audit.loot_routes import native_route_rows
        habitats = ROOT / 'mission/hollow-country/forage/habitats.json'
        policy = ROOT / 'tools/package/essential_routes.json'
        flora = json.loads(habitats.read_text())['flora']
        self.assertEqual(15, len({entry['class'] for entry in flora}))
        mushrooms = [entry for entry in flora if entry['class'].endswith('Mushroom')]
        self.assertEqual(9, len(mushrooms))
        self.assertTrue(all(entry['safety'] == 'unknown-config-and-food-stage-dependent' for entry in mushrooms))
        rows = native_route_rows(habitats, policy)
        self.assertEqual(20, len(rows))  # 15 flora + five native essential-use families.
        self.assertTrue(all(row[1] == 0 and row[4] == 'authored_only_runtime_pending' for row in rows))
        self.assertEqual(13, sum(row[3] == 'native_route_runtime_pending' for row in rows))
        self.assertEqual(7, sum(row[3] == 'hc_bounded_supplement_runtime_pending' for row in rows))
        self.assertEqual(0, sum(row[3] == 'refused_no_acquisition_evidence' for row in rows))


if __name__ == '__main__':
    unittest.main()
