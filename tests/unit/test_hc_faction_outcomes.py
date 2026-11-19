"""HC-37/#146 spec -> plan -> task: observed outcomes, finite retry ledger.

Synthetic stdlib ports execute authored Enforce handlers; never DayZ evidence.
Missing legacy docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md:
the assigned HC-37 contract supplies this slice; HC-11 owns documentation trace.
Plan: remove abstract attrition; bind one surveyed opposed pair through HC-10;
persist actual death/survival receipts without creating bodies, stock or cargo.
Provider targeting/disengage and runtime acceptance remain PENDING.

Actual RED/GREEN, 2026-11-18:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_faction_outcomes -v
RED: FAILED (failures=1), [] != [('raiders', -1)]:
  "unobserved abstract victory must never debit real population".
Generation RED, same command: '' != 'conflict:1':
  "another world generation cannot reuse an old receipt".
GREEN, same command: Ran 1 test; OK. Required focused suite (including file
reader test_expansion_ai_live_map and formula guard): Ran 66 tests; OK.

Wave-8 #177 extends this same behavioral test with explicit synthetic persisted
survivor keys. RED: AssertionError: Missing authored method HCFieldsPresent.
GREEN: test_hc_zero_fill + this module, Ran 4 tests; OK (command/evidence in
test_hc_zero_fill). Lead must wire HCFieldsPresent before the encounter-store
load in HCFactionConflict.OnStart; this owned-file guard alone cannot distinguish
absent keys after native scalar zero-fill. Runtime acceptance remains PENDING.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'
HCX = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'


def syntax(source):
    # Language scaffolding only, shared restricted translator supplies decisions.
    source = source.replace('array<bool> slots', 'HCSlots slots')
    return re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', source)


class Slots(EArray):
    def Set(self, index, value): self[index] = value


class FactionOutcomes(unittest.TestCase):
    def test_abstract_pressure_cannot_kill_and_observed_receipts_are_finite(self):
        source = (WORLD/'HCFactionConflict.c').read_text()
        a = N(Id='locals', Strength=3, Territory=EArray(['0:0']), LastRegrowth=1)
        b = N(Id='raiders', Strength=3, Territory=EArray(['0:0']), LastRegrowth=1)
        data = N(Meta=N(Epoch=1, LastTick=1), Factions=EArray([a, b]),
                 Places=EArray([N(Id='synthetic-site', Name='Synthetic', Position=(0,0,0))]),
                 SiteMemory=EArray(), AppendMemory=lambda row: True)
        changes, facts = [], []
        def strength(faction, delta):
            target = a if faction == a.Id else b
            target.Strength += delta
            changes.append((faction, delta))
        world = N(Relation=lambda *args: -1, AdjustStrength=strength,
                  AddFact=lambda *args: facts.append(args))
        limits = N(DAY=86400, FACT_LIFETIME=604800, TERRITORY=64)
        env = dict(Math=N(Floor=lambda v: int(v)), HCWorldLimits=limits,
                   HCWorldClock=N(Day=lambda d, now: now//86400),
                   HCWorldSiteMemory=N, Print=lambda line: None, str=str)
        # The legacy static job is executed as an instance solely to bind its
        # retained cursor fields in the existing translator.
        old = syntax(source).replace('protected static ', 'protected ')
        old = old.replace('static bool Tick(', 'bool Tick(')
        translate(old, 'HCFactionConflict', env, only=('Cell', 'HCRecentlyContested', 'Tick'))
        env['HCFactionConflict'] = N(Cell=env['Cell'])
        budget = N(HCReset=lambda n: None, HCContinue=lambda: True,
                   HCDeferred=lambda *args: None, HCTake=lambda n: True)
        job = N(s_Active=True, s_WorkNow=86401, s_GrowthNext=2,
                s_PlaceNext=0, s_WorkBudget=budget, s_UnitBudget=budget)
        for _ in range(4):
            env['Tick'](job, world, data, 86401)
        self.assertEqual([], changes, 'unobserved abstract victory must never debit real population')
        self.assertEqual([], facts, 'pressure alone must never publish a physical clash')
        self.assertEqual(['0:0'], list(a.Territory))
        self.assertEqual(['0:0'], list(b.Territory))

        policy = (WORLD/'HCTerritoryOutcomes.c').read_text()
        # #177: explicit synthetic serialized rows. Native zero-fill makes a
        # missing survivor key indistinguishable from an observed zero later.
        from tests.unit.json_loader_port import json_fields_port
        from tests.unit.test_event_runtime import translate as execute
        present = execute(policy, 'HCFieldsPresent', {'HCJsonFields': json_fields_port()},
                          'HCTerritoryOutcomes')
        self.assertTrue(present('{"Rows":[]}'))
        self.assertTrue(present('{"Rows":[{"LeftSurvivors":-1,"RightSurvivors":-1}]}'))
        self.assertTrue(present('{"Rows":[{"LeftSurvivors":0,"RightSurvivors":0}]}'))
        for image in ('{"Rows":[{}]}', '{"Rows":[{"LeftSurvivors":0}]}',
                      '{"Rows":[{"RightSurvivors":0}]}',
                      '{"Rows":[{"LeftSurvivors":0,"RightSurvivors":0},{}]}',
                      '{"Rows":[{"Nested":{"LeftSurvivors":0,"RightSurvivors":0}}]}'):
            self.assertFalse(present(image), 'missing survivor receipts must refuse before zero-fill')
        api = N(MAX_ROWS=int(re.search(r'MAX_ROWS = (\d+)', policy)[1]))
        factions = N()
        fenv = dict(HCWorldFactionCatalog=factions)
        translate((ROOT/'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c').read_text(),
                  'HCWorldFactionCatalog', fenv, only=('Known', 'Relation'))
        factions.Known, factions.Relation = fenv['Known'], fenv['Relation']
        penv = dict(HCTerritoryOutcomes=api, MAX_ROWS=api.MAX_ROWS, str=str,
                    HCJsonFields=json_fields_port(),
                    HCWorldLimits=N(Token=lambda s: isinstance(s, str) and 0 < len(s) <= 96),
                    HCWorldFactionCatalog=factions, HCAILimits=N(SIZE_CEILING=12))
        translate(syntax(policy), 'HCTerritoryOutcomes', penv)
        for name, value in tuple(penv.items()):
            if callable(value): setattr(api, name, value)
        row = N(Id='conflict:1', LeftLease='lease:1', RightLease='lease:2',
                PlaceId='synthetic-site', Survey=EStr('a'*64), State='OBSERVING',
                LeftFaction='locals', RightFaction='raiders',
                LeftParty='party:a', RightParty='party:b', LeftCargo='cargo:a', RightCargo='cargo:b',
                Generation=1,
                LeftDead=Slots([False, False]), RightDead=Slots([False]),
                LeftSurvivors=-1, RightSurvivors=-1)
        self.assertEqual('OBSERVING', api.HCOutcome(row))
        self.assertFalse(api.HCDeath(row, 2, 0))
        self.assertFalse(api.HCDeath(row, 0, 2))
        self.assertTrue(api.HCDeath(row, 1, 0))
        self.assertFalse(api.HCDeath(row, 1, 0), 'retry must not debit twice')
        self.assertEqual('OBSERVING', api.HCOutcome(row), 'one death is not proof of victory')
        self.assertFalse(api.HCResolve(row, 3, 0))
        self.assertFalse(api.HCResolve(row, 2, 1), 'dead actor cannot survive')
        self.assertTrue(api.HCResolve(row, 2, 0))
        self.assertEqual('LEFT_REMAINS', row.State)
        restored = deepcopy(row)  # Explicit synthetic persisted DTO restart.
        self.assertFalse(api.HCDeath(restored, 0, 0))
        self.assertFalse(api.HCResolve(restored, 0, 0))
        self.assertEqual(row, restored)
        self.assertTrue(api.HCSamePair(row, 'lease:2', 'lease:1'))
        self.assertFalse(api.HCSamePair(row, 'lease:1', 'lease:3'))
        unresolved = deepcopy(row)
        unresolved.State = 'OBSERVING'
        unresolved.LeftSurvivors = unresolved.RightSurvivors = -1
        state = N(Rows=EArray([restored, unresolved]))
        self.assertEqual(1, api.HCRecover(state))
        self.assertEqual('UNKNOWN_RESTART', unresolved.State)
        self.assertEqual(-1, unresolved.LeftSurvivors, 'restart cannot infer survivors or cargo')
        self.assertFalse(api.HCResolve(unresolved, 0, 0))

        # Actual handler through explicit synthetic native/provider/store ports.
        # No targeting, corpse factory or inventory API exists in this fixture.
        writes, lines, alive, clock = [], [], [True, True], [100]
        actors = [N(IsAlive=lambda i=i: alive[i]) for i in range(2)]
        generation = [1]
        identities = lambda lease: N(HCPartyId=lambda: 'party:'+lease,
                                     HCCargoId=lambda: 'cargo:'+lease,
                                     HCGeneration=lambda: generation[0])
        owned = lambda lease, faction, body, place, survey: (place == 'synthetic-site' and
                    survey == 'a'*64 and (body is actors[0] or body is actors[1]))
        provider = N(HCSurveyed=lambda *a: True, HCOwns=owned, HCDisengaged=lambda e: False)
        def fresh_row():
            return N(State='OBSERVING', LeftSurvivors=-1, RightSurvivors=-1,
                     LeftDead=Slots(), RightDead=Slots())
        benv = dict(HCTerritoryOutcomes=api, HCWorldLimits=penv['HCWorldLimits'],
                    HCWorldFactionCatalog=factions, HCAILimits=penv['HCAILimits'],
                    HCWorldMaterializer=N(HCIdentity=identities), HCTerritoryOutcomeRow=fresh_row,
                    GetGame=lambda: N(GetTime=lambda: clock[0]),
                    Print=lines.append, str=str)
        adapted = syntax(source).replace('protected static ', 'protected ').replace('protected ', '')
        adapted = adapted.replace('array<Object>', 'HCObjects')
        adapted = adapted.replace('override ', '')
        translate(adapted, 'HCFactionConflict', benv,
                  only=('HCBind', 'HCSave', 'HCRefuse', 'HCLog', 'HCCallbackAllowed',
                        'OnTick', 'HCFinishObserved', 'OnStop'))
        state = N(Version=1, NextEncounter=1, Rows=EArray())
        module = N(m_Healthy=True, s_Active=True, s_CombatPort=None,
                   m_Outcomes=state, m_Current=None, m_LeftActors=EArray(),
                   m_RightActors=EArray(), m_ActorCursor=0, m_CallbackFrame=-1,
                   m_CallbackUnits=budget, m_Units=budget, m_Work=budget,
                   m_Operational=N(HCPublish=lambda *a: None),
                   m_Store=N(Save=lambda d: writes.append(deepcopy(d)) or True))
        for name in ('HCBind', 'HCSave', 'HCRefuse', 'HCLog', 'HCCallbackAllowed',
                     'HCFinishObserved'):
            setattr(module, name, lambda *args, n=name: benv[n](module, *args))
        args = ('synthetic-site', EStr('a'*64), 'lease:10', 'locals', EArray([actors[0]]),
                'lease:11', 'raiders', EArray([actors[1]]))
        self.assertEqual('', module.HCBind(*args))
        self.assertIn('COMBAT_PROVIDER_UNVERIFIED', lines[-1])
        self.assertEqual([], writes)
        module.s_CombatPort = provider
        provider.HCSurveyed = lambda *a: False
        self.assertEqual('', module.HCBind(*args))
        self.assertIn('CONTESTED_SURVEY_UNVERIFIED', lines[-1])
        provider.HCSurveyed = lambda *a: True
        bad = list(args); bad[7] = EArray([actors[0]])
        self.assertEqual('', module.HCBind(*bad), 'same actor cannot belong to both sides')
        self.assertEqual('conflict:1', module.HCBind(*args))
        self.assertEqual(1, len(writes))
        self.assertTrue(api.HCValid(state))
        self.assertEqual('conflict:1', module.HCBind(*args))
        self.assertEqual(1, len(writes), 'begin retry must not save or bind again')
        benv['OnTick'](module, 1)  # Real bound left actor is still alive.
        self.assertEqual(1, len(writes))
        alive[1] = False
        benv['OnTick'](module, 1)  # Actual right-body observation, one slot/tick.
        self.assertEqual(2, len(writes))
        for _ in range(4): benv['OnTick'](module, 1)
        self.assertEqual(2, len(writes), 'death observation retry is idempotent')
        self.assertFalse(module.HCFinishObserved('conflict:1'))
        provider.HCDisengaged = lambda e: True
        module.m_LeftActors[0] = None
        self.assertFalse(module.HCFinishObserved('conflict:1'))
        self.assertIn('ACTOR_ABSENCE_UNKNOWN', lines[-1])
        module.m_LeftActors[0] = actors[0]
        module.m_RightActors[0] = None  # Death was observed before deletion.
        self.assertTrue(module.HCFinishObserved('conflict:1'))
        self.assertEqual('LEFT_REMAINS', state.Rows[0].State)
        self.assertTrue(api.HCValid(state))
        self.assertEqual(3, len(writes))
        self.assertTrue(module.HCFinishObserved('conflict:1'))
        self.assertEqual('conflict:1', module.HCBind(*args))
        self.assertEqual(3, len(writes))
        generation[0] = 2
        self.assertEqual('', module.HCBind(*args), 'another world generation cannot reuse an old receipt')
        generation[0] = 1
        # A failed begin barrier closes the feature without a binding or replay.
        module.m_Store.Save = lambda d: False
        alive[1] = True
        other = list(args); other[2] = 'lease:12'; other[5] = 'lease:13'
        self.assertEqual('', module.HCBind(*other))
        self.assertFalse(module.m_Healthy)
        self.assertIsNone(module.m_Current)
        benv['OnStop'](module)
        benv['OnTick'](module, 1)
        self.assertEqual([], list(module.m_LeftActors))
        self.assertIn('state=off', lines[-1])
        self.assertEqual(3, len(writes))

        # All 25 finite pairs preserve third-party neutrality; mapping changes
        # no HC-5 gesture, surrender or betrayal decision.
        xenv = {}
        xsource = re.sub(r'\bfrom\b', 'fromFaction', (HCX/'HCXFactions.c').read_text())
        translate(xsource, 'HCXFactions', xenv,
                  only=('Known', 'Relation', 'HCWorldId', 'HCEncounterPair'))
        xenv['HCXFactions'] = N(Known=xenv['Known'])
        names = ('Locals', 'Volunteers', 'Scavengers', 'Raiders', 'Travellers')
        for left in names:
            self.assertEqual(left.lower(), xenv['HCWorldId'](left))
            for right in names:
                opposed = left != right and 'Raiders' in (left, right)
                self.assertEqual(opposed, xenv['HCEncounterPair'](left, right))
        self.assertFalse(xenv['HCEncounterPair']('unowned', 'Raiders'))


if __name__ == '__main__': unittest.main()


class FactionOutcomeStorePresenceWiring(unittest.TestCase):
    """Source contract (#188): OnStart checks the loaded image for the survivor keys.

    OnStart and the generic HCEncounterStore aren't translatable here, so this pins
    the order only; HCFieldsPresent itself is exercised behaviourally above.
    """

    def test_on_start_refuses_a_loaded_image_missing_survivor_keys(self):
        root = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/World'
        module = (root / 'HCFactionConflict.c').read_text()
        store = (root / 'HCHoldouts.c').read_text()
        start = module[module.index('override void OnStart'):module.index('override void OnStop')]
        self.assertIn('string HCTakeLoadedText()', store)
        self.assertIn('m_LoadedText = encoded;', store)
        load = start.index('m_Store.Load(')
        take = start.index('m_Store.HCTakeLoadedText()')
        guard = start.index('HCTerritoryOutcomes.HCFieldsPresent(loadedText)')
        refuse = start.index('HCRefuse("OUTCOME_STORE_FIELDS_MISSING")')
        recover = start.index('HCTerritoryOutcomes.HCRecover(')
        self.assertTrue(load < take < guard < refuse < recover)
