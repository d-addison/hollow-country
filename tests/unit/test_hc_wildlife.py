"""HC-15: authored Enforce bodies, SYNTHETIC native handles/clock/players.

No engine, herd, perception, pair-matrix or inventory acceptance evidence.
RED (2026-11-18), existing raw HCEcologyRuntime.Add called from two alias
origins for one handle: AssertionError: 1 != 2 : duplicate herd/territory
aliases created double ownership. Ran 1 test; FAILED (failures=1).
Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_wildlife -v
The GREEN harness uses the new deduplicating port; existing EEInit guards and
the raw registry are unchanged. All policy below executes authored bodies.
Follow-up RED: the same test rejected a skinned carcass still in HCFacts;
GREEN: same focused command, Ran 1 test, OK after native IsSkinned recheck.
Required checks GREEN: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3
-m unittest test_hc_wildlife test_script_syntax test_enforce_locals
test_script_identifiers test_hygiene -v -> Ran 54 tests, OK.
"""
import functools
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_ecology_runtime import environment
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray, body
from tests.unit.test_hc_unit_budget import unit_budget

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Ecology/HCWildlifeObservation.c'
CONFIG = ROOT / 'mission/hollow-country/ecology/species.json'


def rename(text):
    return re.sub(r'\b(HCWildlife\w*|HCEcology\w*|HCV2Admission|DayZAnimalInputController|AnimalBase|AIAgent|Man)\b',
                  lambda m: 'HCEvent' + m[0], text)


def authored(text, method, env, owner, member=False):
    text = re.sub(r'new array<([^>]+)>(?!\s*\()', r'new array<\1>()', rename(text))
    return translate(text, method, {rename(k): v for k, v in env.items()}, rename(owner), member)


class SyntheticAnimal:
    """Identity equality matches native handles; no gameplay decisions here."""
    def __init__(self, group):
        self.position = [10., 0., 10.]
        self.alive = True
        self.deleted = self.skinned = False
        self.group = group
    def IsPendingDeletion(self): return self.deleted
    def IsAlive(self): return self.alive
    def IsSkinned(self): return self.skinned
    def CanBeSkinned(self): return True
    def GetPosition(self): return self.position
    def GetType(self): return 'Animal_CervusElaphus_Synthetic'
    def IsKindOf(self, species): return species == 'Animal_CervusElaphus'
    def GetInputController(self): return N(GetBehaviourSlot=lambda: 12, GetBehaviourAction=lambda: 7)
    def GetAIAgent(self): return N(GetGroup=lambda: self.group)


class WildlifeBehavior(unittest.TestCase):
    def harness(self):
        self.assertTrue(SOURCE.is_file(), 'missing HC-15 authored port')
        text = SOURCE.read_text()
        owner_text = body(text, re.search(r'class HCWildlifeObservation\s*\{', text).end())
        env = environment()
        limits = (SOURCE.parents[2] / '3_Game/Ecology/HCEcologyData.c').read_text()
        env['HCEcologyLimits'].TEXT = int(re.search(r'TEXT = (\d+)', limits)[1])
        rules = (SOURCE.parent / 'HCEcologyRules.c').read_text()
        env['HCEcologyRules'] = N(TextValid=authored(rules, 'TextValid', env, 'HCEcologyRules'))
        env['EArray'] = EArray
        env['AnimalBase'] = N(Cast=lambda obj: obj if isinstance(obj, SyntheticAnimal) else None)
        self.authority = True
        self.logs, self.contributors = [], []
        self.players = EArray([N(IsAlive=lambda: True, GetPosition=lambda: [0., 0., 0.])])
        env['HCEcologyNative'] = N(Authority=lambda: self.authority)
        env['HCPerfPlayers'] = N(HCGet=lambda: self.players)
        env['HCDebugSnapshot'] = N(HCRegister=self.contributors.append, HCUnregister=self.contributors.remove)
        env['Print'] = self.logs.append
        admission = (SOURCE.parents[0].parent / 'Core/HCV2Admission.c').read_text()
        env['HCV2Admission'] = N()
        for method in ('Admitted', 'Line', 'OnOff'):
            setattr(env['HCV2Admission'], method, authored(admission, method, env, 'HCV2Admission'))
        # DTO scaffolding reads authored fields/defaults; no policy surrogate.
        for kind in ('HCWildlifeFact', 'HCWildlifeBinding'):
            fields = body(text, re.search(r'class ' + kind + r'\s*\{', text).end())
            declarations = re.findall(r'^\s*(?:ref )?(\w+) (\w+)(?: = ([^;]+))?;', fields, re.M)
            def factory(declarations=declarations):
                return N(**{key: json.loads(value) if value else {'string':'', 'bool':False,
                    'int':0, 'vector':[0.,0.,0.]}.get(typ) for typ,key,value in declarations})
            env[kind] = factory
        env['HCWildlifeDebugContributor'] = lambda: N(Owner=None)
        state = N(state='unknown', reason='unknown')
        state.HCPublish = lambda s, r: (setattr(state, 'state', s), setattr(state, 'reason', r))
        owner = N(m_Bindings=EArray(), m_Config=None, m_Units=unit_budget(),
                  m_Work=N(HCReset=lambda *args: None, HCContinue=lambda: True),
                  m_Status=state, m_Debug=None, m_Collecting=True, m_Running=False,
                  m_OverflowReported=False, m_NextSerial=1, m_Cursor=0,
                  m_LastTick=-1, m_LastNow=-1)
        policy = N()
        env['HCWildlifeObservation'] = policy
        for method in ('HCConfigValid', 'HCDestinationSupported', 'HCFeedingSupported', 'HCTargetObservationSupported'):
            setattr(policy, method, authored(owner_text, method, env, 'HCWildlifeObservation'))
            setattr(owner, method, getattr(policy, method))
        for method in ('HCBegin', 'HCAdd', 'HCRemove', 'HCNear', 'HCRead', 'HCSample', 'HCFacts', 'HCEnd', 'HCRefuse'):
            setattr(owner, method, functools.partial(authored(owner_text, method, env, 'HCWildlifeObservation', True), owner))
        config = json.loads(CONFIG.read_text())
        config['Species'] = EArray(config['Species'])
        config['TargetPairs'] = EArray(N(**p) for p in config['TargetPairs'])
        return owner, N(**config)

    def test_aliases_share_one_native_owner_and_unsupported_commands_refuse(self):
        owner, config = self.harness()
        animal = SyntheticAnimal(object())
        for alias in ('synthetic-herd', 'synthetic-territory'):
            self.assertTrue(owner.HCAdd(animal), alias)
        self.assertEqual(1, owner.m_Bindings.Count(),
                         'duplicate herd/territory aliases created double ownership')
        self.assertTrue(owner.HCBegin(True, config))
        owner.HCSample(100)
        facts = owner.HCFacts(100)
        self.assertEqual(1, facts.Count())
        self.assertIs(animal.group, facts[0].NativeGroup)
        self.assertEqual((12, 7), (facts[0].BehaviourSlot, facts[0].BehaviourAction))
        self.assertFalse(facts[0].TargetKnown)  # HUNTING still does not identify prey.
        self.assertIsNone(facts[0].Target)
        facts[0].Species = 'mutated-consumer-copy'
        self.assertEqual(animal.GetType(), owner.HCFacts(100)[0].Species)
        for method in ('HCDestinationSupported', 'HCFeedingSupported', 'HCTargetObservationSupported'):
            self.assertFalse(getattr(owner, method)())
        for capability in ('destination', 'feeding', 'animal_target'):
            self.assertTrue(any('capability=' + capability in line and 'state=refused' in line for line in self.logs))
        self.assertTrue(any('targets=5 state=ready' in line and 'observed_targets=0 runtime=PENDING' in line for line in self.logs))

        # Finite carcass evidence is revoked on native skinning/deletion/death,
        # and clock/freshness checks never replay an observation into a new life.
        animal.alive = False
        self.assertEqual([], owner.HCFacts(100))
        owner.HCSample(1100)
        self.assertTrue(owner.HCFacts(1100)[0].Carcass)
        animal.skinned = True
        self.assertEqual([], owner.HCFacts(1100))
        animal.skinned = False
        animal.deleted = True
        self.assertEqual([], owner.HCFacts(1100))
        animal.deleted = False
        self.assertEqual([], owner.HCFacts(1100 + config.FactLifetimeMs + 1))

        # Work-unit/time yields retain the next animal; configured range is
        # observation-only. Off/stop releases the debug contributor and handles.
        other = SyntheticAnimal(object())
        self.assertTrue(owner.HCAdd(other))
        config.WorkUnits = 1
        owner.m_Cursor = 0
        owner.HCSample(2100)
        self.assertEqual(1, owner.m_Cursor)
        owner.m_Work.HCContinue = lambda: False
        owner.HCSample(3100)
        self.assertEqual(1, owner.m_Cursor)
        owner.m_Work.HCContinue = lambda: True
        owner.HCSample(4100)
        self.assertEqual(2, owner.m_Cursor)
        config.MaxFacts = 1
        self.assertEqual(1, len(owner.HCFacts(4100)))
        self.players[0].GetPosition = lambda: [config.PlayerObservationRadiusM * 2, 0., 0.]
        owner.HCSample(5100)
        owner.HCSample(6100)
        self.assertEqual([], owner.HCFacts(6100))
        owner.HCRemove(animal)
        self.assertEqual([other], [row.Live for row in owner.m_Bindings])
        owner.HCEnd()
        self.assertEqual([], self.contributors)
        self.assertEqual([], owner.m_Bindings)
        self.assertFalse(owner.HCAdd(other))
        self.assertFalse(owner.HCBegin(False, None))
        owner.HCSample(7100)
        self.assertEqual([], owner.HCFacts(7100))
        self.assertEqual('off', owner.m_Status.state)
        self.assertTrue(owner.HCBegin(True, config))
        self.assertTrue(owner.HCAdd(other))
        owner.HCSample(8100)
        owner.HCSample(8000)  # rollback refuses and clears the entire port
        self.assertEqual('refused', owner.m_Status.state)
        self.assertEqual([], owner.HCFacts(8100))
        self.assertEqual([], self.contributors)

        for field, invalid in (('PlayerObservationRadiusM', float('nan')), ('MaxAnimals', 257)):
            old = getattr(config, field)
            setattr(config, field, invalid)
            self.assertFalse(owner.HCBegin(True, config), field)
            setattr(config, field, old)
        config.TargetPairs[0].Verdict = 'accepted_from_config'
        self.assertFalse(owner.HCBegin(True, config))
        config.TargetPairs[0].Verdict = 'pending_native_pair_matrix'
        self.authority = False
        self.assertFalse(owner.HCAdd(other))
        self.assertFalse(owner.HCBegin(True, config))


if __name__ == '__main__':
    unittest.main()
