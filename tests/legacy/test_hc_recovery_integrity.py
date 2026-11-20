"""HC-4: authored handlers with explicit SYNTHETIC native boundaries.

Restricted execution reuses the crafting test port. No DayZ transaction,
inventory replication, persistence, or engine acceptance is established here.

TDD receipt (same focused command throughout):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_recovery_integrity -v
RED: FAILED (failures=4); actual property tuples (55, 0, 0, 1, 7) versus
     expected (20, 0.8, 6, 1, 7); drysack quantities (0, 0) versus (0, 1).
     A deleting allocation also reached ['results', 'debit', 'native-do'].
RED extension: FAILED (failures=2); filled waterskin: True is not false;
     invalidated result reached ['results', 'debit', 'native-do'].
RED diagnostic: FAILED (failures=1); expected startup receipt versus [].
GREEN: Ran 9 tests; OK. Native runtime acceptance remains pending.

HC-30 receipt (same focused command for every RED/GREEN below):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery_integrity -v
RED: FAILED (failures=5, errors=1): exact common sources were rejected with
     'False is not true : HC-30 must admit the exact owned common recovery
     source'; the unauthored manifest was also absent.
RED preflight: FAILED (failures=1): 'True is not false : missing retained tool
     must refuse registration'.
RED native reuse: FAILED (failures=1): 'False is not true : native disposition
     must preserve other HC recipes'.
GREEN: Ran 10 tests; OK. All native boundaries below remain SYNTHETIC.

HC-30 round-2 integration receipt (2026-11-18):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery_integrity test_crafting_contract -v
RED: Ran 24 tests; FAILED (failures=47, errors=1). Actual failures included
     'AssertionError: 1 != 4', missing appended registrations,
     'AssertionError: 1 != 0 : exactly one report per boot path', and
     'ValueError: mission handoff file outside allowlist: crafting/recovery-dispositions.json'.
GREEN: same command, Ran 24 tests; OK. Nine synthetic source-disposition pairs
       exercise ten startup paths each, including core skipping disabled OnStart.
Required-suite GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery_integrity test_crafting_contract test_salvage_tools test_package test_friend_bundle test_script_syntax test_enforce_locals test_script_identifiers test_enforce_formula_complexity test_hygiene -v
Ran 155 tests; OK (skipped=1: Windows PowerShell helper belongs to Windows CI).
python3 -B -m tools.validate.enforce_lint --no-native
enforce_lint: pass findings=124 new=0 stale=0 native=no; baseline unchanged.
Related lifecycle/construction/fuel test ports now include explicit synthetic
HC-30 collaborators; their initial missing-port RED was NameError:
name 'HCCommonRecoveryPolicy' is not defined (87 tests, errors=66).
Related-suite GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_crafting_families test_crafting_completion test_v1_combined_flags test_hc_claim_round2 test_hc_fuel_conservation -v
Ran 87 tests; OK (expected failures=1, existing combined workload budget case).
No native compile, boot or craft observed; runtime/production acceptance pending.
"""
from types import SimpleNamespace as NS
import json
import io
from pathlib import Path
import re
import unittest
import zipfile

from tests.legacy.test_crafting_completion import execute_flat
from tests.legacy.test_crafting_families import Result, state_for
from tests.legacy.test_salvage_tools import authored, NativeArray

NATIVE = 'HCNativeCraftingSafety.c'
COMMON = 'HCCommonRecoveryRecipes.c'
ROOT = Path(__file__).resolve().parents[2]
COMMON_SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Crafting' / COMMON
COMMON_MANIFEST = ROOT / 'mission/hollow-country/crafting/recovery-dispositions.json'


def synthetic_format(pattern, *args):
    for index, value in enumerate(args, 1):
        pattern = pattern.replace('%' + str(index), str(value))
    return pattern


def common_policy(game=None, logs=None, manager=None):
    from tests.legacy.test_salvage_tools import tool_policy
    from tests.legacy.test_event_runtime import translate
    policy = NS()
    env = dict(HCCommonRecoveryPolicy=policy, GetGame=lambda: game,
               HCSalvageTools=tool_policy(game), Print=(logs if logs is not None else []).append,
               PluginRecipesManager=NS(Cast=lambda value: value), GetPlugin=lambda kind: manager,
               string=NS(Format=synthetic_format))
    for name, params in (('HCSourceCount', 'recipeName'),
                         ('HCSourceAt', 'recipeName,index'),
                         ('HCAllowsSource', 'recipeName,actualType'),
                         ('HCPreflight', 'recipeName'),
                         ('HCCheckDefinition', 'recipe,recipeName')):
        call = authored(name, params, env, COMMON, 'HCCommonRecoveryPolicy')
        setattr(policy, name, lambda *args, fn=call: fn(None, *args))
    try:
        call = authored('HCMatchesPreflight', 'recipe,recipeName', env, COMMON, 'HCCommonRecoveryPolicy')
        policy.HCMatchesPreflight = lambda *args: call(None, *args)
    except AssertionError:
        pass  # RED exercises current validation when the extension is absent.
    policy.HCValidateRegistered = execute_flat(COMMON, 'HCValidateRegistered', '', env)
    # Type alias only: the existing event port understands HCEvent native DTO
    # declarations. It executes the authored receipt control flow unchanged.
    text = COMMON_SOURCE.read_text().replace('PluginRecipesManager manager', 'HCEventNativeManager manager')
    policy.HCReport = translate(text, 'HCReport', env)
    return policy


def common_state(name):
    """Execute HC initializers/handlers; all native boundaries are SYNTHETIC.

    Before HC-30 exists, exercise the existing recovery admission with the
    proposed exact source: RED must show rejected behavior, not a missing file.
    """
    from tests.legacy.test_crafting_families import source_policy
    from tests.legacy.test_salvage_tools import tool_policy
    state = state_for('HCRecoverBatWood')
    state.m_HCInputType = name
    if not COMMON_SOURCE.exists():
        return state
    policy = common_policy()
    state.m_Ingredients = [NativeArray(), NativeArray()]
    state.m_NumberOfResults = 0
    state.m_ItemsToCreate = []
    state.InsertIngredient = lambda slot, kind: state.m_Ingredients[slot].Insert(kind)
    def add_result(kind):
        state.m_ItemsToCreate.append(kind)
        state.m_NumberOfResults += 1
    state.AddResult = add_result
    env = dict(HCCommonRecoveryPolicy=policy, HCSalvageTools=tool_policy(),
               HCSalvageSources=source_policy(), MAX_NUMBER_OF_INGREDIENTS=2,
               HCCraftingGate=NS(CanPreviewOrCraft=lambda: True))
    configure = authored('Configure', 'label,inputType,toolType,outputType,quantity,wear,animationUnits', env)
    state.Configure = lambda *args: configure(state, *args)
    authored('Init', '', env, COMMON, name)(state)
    state.ClassName = lambda: name
    state.IsInstaRecipe = lambda: state.m_IsInstaRecipe
    state.IsRepeatable = lambda: False
    state.IsRecipeAnywhere = lambda: state.m_AnywhereInInventory
    state.GetLengthInSecs = lambda: state.m_AnimationLength * 4
    state.GetSpecialty = lambda: state.m_Specialty
    call = authored('CanDo', 'ingredients,player', env, COMMON, 'HCCommonRecoveryRecipe')
    state.CanDo = lambda *args: call(state, *args)
    return state


class Item(Result):
    def __init__(self, kind, health=40, quantity=1, wet=0.6, agents=2):
        super().__init__(kind, quantity)
        self.health, self.wet, self.agents = health, wet, agents
        self.energy = 0
        self.delete_calls = 0
        self.IsEmpty = lambda: True
        self.ConfigGetString = lambda key: 'Green'

    def GetWet(self): return self.wet
    def GetAgents(self): return self.agents
    def TransferAgents(self, agents): self.agents |= agents
    def Delete(self):
        self.delete_calls += 1
        self.deleted = True  # SYNTHETIC deferred-delete admission boundary.


def guard():
    state = NS(m_Busy=False)
    for name in ('TryEnter', 'Release'):
        call = authored(name, '', {}, owner='HCCraftingCommitGuard')
        setattr(state, name, lambda fn=call: fn(state))
    return state


def safety_policy():
    policy = NS()
    env = dict(HCNativeCraftingSafety=policy)
    for name, params in (
        ('IsScoped', 'recipeName'), ('NeedsConditionCap', 'recipeName'),
        ('NeedsEmptySource', 'recipeName'),
        ('CapNativeRecovery', 'results,sourceHealth'),
        ('DiscardNativeOutputs', 'results'),
        ('NeedsRecoveryState', 'recipeName'),
        ('InheritRecoveryState', 'source,results'),
    ):
        # Before an override exists, execute the original handler with the
        # explicit native boundary below, rather than failing on a new symbol.
        try:
            call = authored(name, params, env, NATIVE)
        except AssertionError:
            continue
        setattr(policy, name, lambda *args, fn=call: fn(None, *args))
    return policy


def native_completion(name, source, material, outputs, destroyed=(True, False), deltas=(0, 0), invalidate=False):
    """Native methods are stubs; HC PerformRecipe/result policy actually execute.

    The explicit average is the inspected native bag upgrade inheritance seam;
    the test does not implement recipes or native inventory in Python.
    """
    events = []
    policy = safety_policy()
    env = dict(HCNativeCraftingSafety=policy, NativeArray=NativeArray,
               MAX_NUMBER_OF_INGREDIENTS=2,
               GetGame=lambda: NS(IsServer=lambda: True))
    state = NS(ClassName=lambda: name, HCIsScoped=lambda: policy.IsScoped(name),
               m_HCNativeCommitGuard=guard(), m_IngredientsSorted=[source, material],
               m_NumberOfResults=len(outputs), m_Specialty=0,
               m_IngredientDestroy=destroyed, m_IngredientAddQuantity=deltas)
    state.CheckRecipe = lambda *args: not source.deleted and not material.deleted
    state.SpawnItems = lambda pair, actor, dest: dest.extend(outputs)
    def native_results(*args):
        events.append('results')
        if invalidate: outputs[0].Delete()
    state.native = NS(ApplyModificationsResults=native_results)
    try:
        apply = authored('ApplyModificationsResults', 'sorted,results,result,player', env, NATIVE)
        state.ApplyModificationsResults = lambda *args: apply(state, *args)
    except AssertionError:
        state.ApplyModificationsResults = state.native.ApplyModificationsResults

    def debit(pair, actor):
        events.append('debit')
        # Allocator callback reentry must fail before creating another output.
        perform(state, source, material, actor)

    state.ApplyModificationsIngredients = debit
    state.Do = lambda *args: events.append('native-do')
    state.DeleleIngredientsPass = lambda: source.Delete()
    perform = authored('PerformRecipe', 'item1,item2,player', env, NATIVE)
    perform(state, source, material, object())
    perform(state, source, material, object())
    return events


class RecoveryIntegrityTests(unittest.TestCase):
    def test_hc30_exact_finite_recoveries_reuse_guarded_debit_and_property_policy(self):
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        choices = {
            'HCRecoverTeddyRag': ['Bear_Beige', 'Bear_Dark', 'Bear_Pink', 'Bear_White'],
            'HCRecoverFabricRag': ['Fabric'],
        }
        for name, sources in choices.items():
            for kind in sources:
                with self.subTest(recipe=name, source=kind):
                    state = common_state(name)
                    source, tool = Item(kind, health=40), Item('KitchenKnife', health=6)
                    source.owner = tool.owner = actor
                    source.ConfigGetFloat = lambda field: 0
                    source.HasQuantity = lambda: kind == 'Fabric'
                    source.quantity = 4 if kind == 'Fabric' else 1
                    self.assertTrue(state.CanDo([source, tool], actor),
                                    'HC-30 must admit the exact owned common recovery source')
                    self.assertEqual(sources, state.m_Ingredients[0])
                    self.assertEqual(['Rag'], state.m_ItemsToCreate)
                    self.assertEqual(1, state.m_ResultSetQuantity[0])
                    self.assertEqual([kind != 'Fabric', False], state.m_IngredientDestroy)
                    self.assertEqual([-1 if kind == 'Fabric' else 0, 0], state.m_IngredientAddQuantity)
                    for field, bad in [('owner', None), ('deleted', True), ('ruined', True)]:
                        old = getattr(source, field)
                        setattr(source, field, bad)
                        self.assertFalse(state.CanDo([source, tool], actor))
                        setattr(source, field, old)
                    source.ConfigGetFloat = lambda field: 2
                    self.assertFalse(state.CanDo([source, tool], actor), 'native rag route wins')
                    source.ConfigGetFloat = lambda field: 0
                    source.kind = kind + '_Mod'
                    self.assertFalse(state.CanDo([source, tool], actor))
                    source.kind = kind
                    tool.health = 5
                    self.assertFalse(state.CanDo([source, tool], actor))
                    tool.health = 6
                    source.inventory.GetCargo = lambda: NS(GetItemCount=lambda: 1)
                    self.assertFalse(state.CanDo([source, tool], actor))
                    source.inventory.GetCargo = lambda: None
                    if kind == 'Fabric':
                        for quantity in (0, 0.5):
                            source.quantity = quantity
                            self.assertFalse(state.CanDo([source, tool], actor))
                        source.quantity = 4

                    # Native recipe execution/allocation/debit is an explicit
                    # adapter, never evidence of DayZ's inventory transaction.
                    for fail_output in (True, False):
                        output = Item('Rag', health=100, wet=0, agents=0)
                        state.m_HCCommitGuard = guard()
                        state.native.SpawnItems = lambda pair, actor, dest: dest.extend([None if fail_output else output])
                        state.native.ApplyModificationsResults = lambda *args: None
                        perform = authored('PerformRecipe', 'item1,item2,player',
                                           dict(GetGame=lambda: NS(IsServer=lambda: True)))
                        def native_perform(first, second, player):
                            perform(state, first, second, player)  # reentry refused
                            if not state.CanDo([first, second], player):
                                return
                            dest = NativeArray()
                            state.SpawnItems([first, second], player, dest)
                            state.ApplyModificationsResults([first, second], dest, None, player)
                            if state.m_HCOutputReady:
                                if state.m_IngredientDestroy[0]: first.Delete()
                                else: first.quantity += state.m_IngredientAddQuantity[0]
                                second.health += state.m_IngredientAddHealth[1]
                            state.Do([first, second], player, dest, 0)
                        state.native.PerformRecipe = native_perform
                        perform(state, source, tool, actor)
                        if fail_output:
                            self.assertEqual(0, source.delete_calls)
                            self.assertEqual(4 if kind == 'Fabric' else 1, source.quantity)
                            self.assertEqual(6, tool.health)
                        else:
                            self.assertEqual(0 if kind == 'Fabric' else 1, source.delete_calls)
                            self.assertEqual(3 if kind == 'Fabric' else 1, source.quantity)
                            self.assertEqual(1, tool.health)
                            self.assertAlmostEqual(30, output.health)
                            self.assertEqual((0.6, 2, 1),
                                             (output.wet, output.agents, output.quantity))
                            perform(state, source, tool, actor)
                            self.assertEqual(1, tool.health)  # duplicate completion cannot debit

        manifest = json.loads(COMMON_MANIFEST.read_text())
        self.assertEqual('pending', manifest['runtime_acceptance'])
        approved = [row for row in manifest['entries'] if row['route'] == 'hc-recovery']
        self.assertEqual(set(choices), {row['recipe'] for row in approved})
        edges = {}
        for row in approved:
            self.assertEqual(choices[row['recipe']], row['sources'])
            self.assertEqual([{'class': 'Rag', 'quantity': 1}], row['outputs'])
            for source in row['sources']:
                edges.setdefault(source, set()).update(output['class'] for output in row['outputs'])
        def visit(node, active):
            self.assertNotIn(node, active, 'selected recovery cycle')
            for target in edges.get(node, ()):
                visit(target, active | {node})
        for source in edges:
            visit(source, set())

        # Explicit synthetic config/cache boundary: no installed-config fixture
        # and no native manager execution is smuggled into the offline test.
        missing, overrides, logs = set(), {}, []
        game = NS(ConfigIsExisting=lambda path: path not in missing,
                  ConfigGetInt=lambda path: 2,
                  ConfigGetFloat=lambda path: overrides.get(path,
                      6 if path == 'CfgVehicles Rag varQuantityMax' else
                      4 if path == 'CfgVehicles Fabric varQuantityMax' else 0))
        cached = {name: common_state(name) for name in choices}
        cached.update({name: object() for name in ('CraftRag', 'SplitBroom', 'SplitLongWoodenStick')})
        manager = NS(HCGetRegisteredSalvage=cached.get)
        policy = common_policy(game, logs, manager)
        for name in choices:
            self.assertTrue(policy.HCPreflight(name))
        missing.add('CfgVehicles KitchenKnife')
        self.assertFalse(policy.HCPreflight('HCRecoverFabricRag'), 'missing retained tool must refuse registration')
        missing.clear()
        for source in ['Fabric', *choices['HCRecoverTeddyRag']]:
            overrides['CfgVehicles ' + source + ' ragQuantity'] = 1
            name = 'HCRecoverFabricRag' if source == 'Fabric' else 'HCRecoverTeddyRag'
            self.assertFalse(policy.HCPreflight(name))
            overrides.clear()
        self.assertTrue(policy.HCValidateRegistered())
        overrides['CfgVehicles Fabric ragQuantity'] = 1
        self.assertFalse(policy.HCValidateRegistered(), 'duplicate HC/native route must refuse')
        fabric = cached.pop('HCRecoverFabricRag')
        self.assertTrue(policy.HCValidateRegistered(), 'native disposition must preserve other HC recipes')
        cached['HCRecoverFabricRag'] = fabric
        overrides.clear()
        for name in choices:
            cached[name].m_ResultSetFullQuantity[0] = True
            self.assertFalse(policy.HCValidateRegistered())
            cached[name].m_ResultSetFullQuantity[0] = False
        self.assertTrue(policy.HCValidateRegistered())
        self.assertEqual({'recoveries': 2, 'native_reused': 3, 'refused': 3}, manifest['authored_counts'])
        logs.clear()
        policy.HCReport(True, True)
        self.assertEqual('[HC Plan] HC-30 recoveries=2 native_reused=3 refused=3 '
                         'state=ready authored=2 observed=0 runtime=PENDING', logs[-1])
        self.assertEqual(1, len(logs))
        policy.HCReport(True, False)
        self.assertIn('recoveries=0 native_reused=3 refused=5 state=refused', logs[-1])
        logs.clear()
        policy.HCReport(False, False)
        self.assertEqual(['[HC Plan] HC-30 recoveries=0 native_reused=0 refused=0 '
                          'state=off authored=2 observed=0 runtime=PENDING'], logs)

    def test_hc30_registration_and_boot_admission_report_once_on_every_path(self):
        from itertools import product
        from tests.legacy.test_event_runtime import translate
        from tests.legacy.test_refusal_report import MethodsTranslator
        from tools.package import pbo

        crafting = COMMON_SOURCE.parent
        registration = (crafting / 'HCRecipeRegistration.c').read_text()
        module_source = (crafting / 'HCCraftingModule.c').read_text()
        pilots = json.loads((ROOT / 'tests/fixtures/runtime/crafting-contract.json').read_text())['pilots']
        existing = [row['class'] for row in pilots]
        additions = ['HCRecoverTeddyRag', 'HCRecoverFabricRag']

        # Execute actual registration, validation and report bodies. Config,
        # recipe cache, core lifecycle dispatch and HC-4 Run are SYNTHETIC ports.
        for teddy, fabric in product(('approved', 'native', 'missing'), repeat=2):
            with self.subTest(teddy=teddy, fabric=fabric):
                logs, events, cached = [], [], {}
                choices = {'Bear_Beige': teddy, 'Fabric': fabric}
                game = NS(IsServer=lambda: True,
                          ConfigIsExisting=lambda path: choices.get(path.removeprefix('CfgVehicles ')) != 'missing',
                          ConfigGetInt=lambda path: 2,
                          ConfigGetFloat=lambda path: (
                              1 if path.endswith(' ragQuantity') and choices.get(path.split()[1]) == 'native' else
                              6 if path == 'CfgVehicles Rag varQuantityMax' else
                              4 if path == 'CfgVehicles Fabric varQuantityMax' else 0))
                manager = NS(HCGetRegisteredSalvage=cached.get)
                policy = common_policy(game, logs, manager)
                def register(recipe):
                    events.append(recipe.ClassName())
                    cached[recipe.ClassName()] = recipe
                def native():
                    events.append('native')
                    cached.update({name: object() for name in ('CraftRag', 'SplitBroom', 'SplitLongWoodenStick')})
                env = dict(super=NS(RegisterRecipies=native), RegisterRecipe=register,
                           UnregisterRecipe=lambda name: events.append(name), HCCommonRecoveryPolicy=policy)
                env.update({name: (lambda name=name: common_state(name) if name in additions
                                  else NS(ClassName=lambda: name))
                            for name in re.findall(r'RegisterRecipe\(new (\w+)\)', registration)})
                translate(registration, 'RegisterRecipies', env)()
                approved = [name for name, disposition in zip(additions, (teddy, fabric))
                            if disposition == 'approved']
                self.assertEqual(['native', 'CraftFenceKit', 'CraftWatchtowerKit',
                                  'CraftTerritoryFlagKit', 'CraftShelterKit', *existing, *approved], events)
                self.assertTrue(policy.HCValidateRegistered())

                # Core calls IsEnabled once, then OnStart only when enabled.
                # Direct OnStart calls also cover every early-return path.
                cases = ('ready', 'hc4-failed', 'hc30-drift', 'no-manager', 'disabled',
                         'null-settings', 'direct-disabled', 'direct-null', 'no-game', 'client')
                for case in cases:
                    with self.subTest(path=case):
                        # Include registration diagnostics in the boot line count.
                        boot_logs = list(logs)
                        starts, validations, reports = [], [], []
                        gate = NS(m_Started=True, m_Validated=True)
                        boot_game = None if case == 'no-game' else NS(IsServer=lambda: case != 'client')
                        settings = None if case in ('null-settings', 'direct-null') else NS(
                            EnableCrafting=case not in ('disabled', 'direct-disabled'))
                        boot_policy = common_policy(game, boot_logs, None if case == 'no-manager' else manager)
                        if case == 'hc30-drift' and approved:
                            cached[approved[0]].m_ResultSetFullQuantity[0] = True
                        def validate():
                            validations.append('hc30')
                            return boot_policy.HCValidateRegistered()
                        def report(enabled, admitted):
                            reports.append((enabled, admitted, gate.m_Started, gate.m_Validated))
                            boot_policy.HCReport(enabled, admitted)
                        def hc4():
                            validations.append('hc4')
                            return case != 'hc4-failed'
                        context = dict(HCModule=object, HCOperationalStatus=object, HCCraftingGate=gate, GetGame=lambda: boot_game,
                                       HCCraftingNativeChecks=NS(Run=hc4),
                                       HCCommonRecoveryPolicy=NS(HCValidateRegistered=validate, HCReport=report),
                                       HCActionSiphonFuel=NS(ProductionStart=starts.append), Print=boot_logs.append)
                        for code in MethodsTranslator(module_source, 'HCCraftingModule',
                                                      ('IsEnabled', 'OnStart')).classes():
                            exec(code, context)
                        module = context['HCCraftingModule']()
                        if case.startswith('direct-') or module.IsEnabled(settings):
                            module.OnStart(settings)
                        active = case in ('ready', 'hc4-failed', 'hc30-drift', 'no-manager')
                        admitted = active and case != 'hc4-failed' and case != 'no-manager'
                        admitted = admitted and not (case == 'hc30-drift' and approved)
                        self.assertEqual(1, len(reports), 'exactly one report per boot path')
                        self.assertEqual((active, admitted), reports[0][:2])
                        if active:
                            self.assertEqual((admitted, admitted), reports[0][2:], 'report follows gate admission')
                        if case not in ('disabled', 'null-settings'):
                            self.assertEqual((admitted, admitted), (gate.m_Started, gate.m_Validated))
                        self.assertEqual([admitted] if active else [], starts)
                        self.assertEqual(['hc4'] + ([] if case == 'hc4-failed' else ['hc30'])
                                         if active else [], validations)
                        receipts = [line for line in boot_logs if line.startswith('[HC Plan] HC-30 ')]
                        self.assertEqual(1, len(receipts), 'exactly one HC-30 plan line across registration and startup')
                        count = len(approved) if admitted else 0
                        self.assertIn('recoveries=' + str(count), receipts[0])
                        self.assertIn('runtime=PENDING', receipts[0])
                        if not active:
                            self.assertIn('state=off', receipts[0])
                        if case == 'hc30-drift' and approved:
                            cached[approved[0]].m_ResultSetFullQuantity[0] = False

        # The actual portable handoff must carry both authored scripts and the
        # disposition file byte-for-byte; no game assets/native data are used.
        blob = pbo.handoff(ROOT / 'mods/HollowCountry', ROOT / 'mission/hollow-country')
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            name = 'mission/hollow-country/crafting/recovery-dispositions.json'
            self.assertEqual(COMMON_MANIFEST.read_bytes(), archive.read(name))
            _, scripts = pbo.parse(archive.read('@HollowCountry/addons/hollowcountry.pbo'))
            for name in ('HCRecipeRegistration.c', 'HCCraftingModule.c', COMMON):
                self.assertEqual((crafting / name).read_bytes(), scripts['scripts/4_World/Crafting/' + name])

    def test_startup_receipt_distinguishes_authored_definitions_from_runtime_acceptance(self):
        lines = []
        check = execute_flat('HCCraftingNativeChecks.c', 'CheckCompletionGuard', '',
                             dict(HCCraftingCommitGuard=guard, Print=lines.append))
        self.assertTrue(check())
        self.assertEqual([
            '[HC Plan] HC-4 recovery definitions=11 native_safety=active '
            'state=checking observed=0 runtime=PENDING'
        ], lines)

    def test_native_upgrade_and_recovery_cannot_launder_material_properties(self):
        source = Item('WaterproofBag_Green', health=20, agents=2)
        rope = Item('Rope', health=90, wet=0.8, agents=4)
        upgraded = Item('DrysackBag_Green', health=55, wet=0, agents=0)
        upgraded.energy = 7  # Sentinel: selective inheritance must not copy energy.
        events = native_completion('CraftDrysackBag', source, rope, NativeArray([upgraded]), (True, True))
        self.assertEqual(['results', 'debit', 'native-do'], events)
        self.assertEqual(1, source.delete_calls)
        self.assertEqual((20, 0.8, 6, 1, 7),
                         (upgraded.health, upgraded.wet, upgraded.agents, upgraded.quantity, upgraded.energy))
        bag, recovered_rope = Item('BurlapSack', health=100, agents=0, wet=0), Item('Rope', health=100, agents=0, wet=0)
        tool = Item('KitchenKnife', health=90, agents=8, wet=1)
        native_completion('DeCraftCourierBag', upgraded, tool, NativeArray([bag, recovered_rope]))
        for output in (bag, recovered_rope):
            self.assertEqual((20, 0.8, 6), (output.health, output.wet, output.agents))

    def test_native_quantity_materials_contribute_but_unconsumed_tools_do_not(self):
        leather = Item('TannedLeather', health=40, quantity=2, agents=2)
        kit = Item('LeatherSewingKit', health=80, quantity=10, agents=4)
        output = Item('LeatherSack_Natural', health=60, wet=0, agents=0)
        native_completion('CraftLeatherSack', leather, kit, NativeArray([output]), (False, False), (-2, -10))
        self.assertEqual((40, 0.6, 6), (output.health, output.wet, output.agents))

    def test_failed_or_deleting_native_output_never_debits_and_cleans_provisionals(self):
        for failure in ('missing', 'deleting'):
            with self.subTest(failure=failure):
                source, tool = Item('CourierBag'), Item('KitchenKnife')
                survivor = Item('BurlapSack')
                bad = None if failure == 'missing' else Item('Rope')
                if bad: bad.deleted = True
                events = native_completion('DeCraftCourierBag', source, tool, NativeArray([survivor, bad]))
                self.assertEqual([], events)
                self.assertEqual(0, source.delete_calls)
                self.assertTrue(survivor.deleted)

    def test_native_result_mutation_failure_is_rechecked_before_debit(self):
        source, tool = Item('CourierBag'), Item('KitchenKnife')
        outputs = NativeArray([Item('BurlapSack'), Item('Rope')])
        events = native_completion('DeCraftCourierBag', source, tool, outputs, invalidate=True)
        self.assertEqual(['results'], events)
        self.assertEqual(0, source.delete_calls)
        self.assertTrue(all(item.deleted for item in outputs))

    def test_filled_waterskin_is_not_an_empty_recovery_source(self):
        env = dict(HCNativeCraftingSafety=safety_policy(), TrapBase=NS(Cast=lambda item: None))
        validate = authored('HCValidateNativeInputs', 'item1,item2,player', env, NATIVE)
        state = NS(ClassName=lambda: 'DeCraftWaterskin', m_IngredientDestroy=[True, False],
                   m_IngredientAddQuantity=[0, 0])
        source, tool = Item('Waterskin_Natural', quantity=1), Item('KitchenKnife')
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        self.assertFalse(validate(state, source, tool, actor))
        source.quantity = 0
        self.assertTrue(validate(state, source, tool, actor))

    def test_all_eleven_hc_recoveries_use_the_same_selective_snapshot_policy(self):
        from tests.legacy.test_crafting_families import FAMILIES
        from tests.legacy.test_crafting_completion import PILOTS
        families = list(FAMILIES) + [p[0] for p in PILOTS]
        self.assertEqual(11, len(families))
        for name in families:
            with self.subTest(recipe=name):
                state = state_for(name if name in FAMILIES else 'HCRecoverBatWood')
                if name not in FAMILIES:
                    pilot = next(p for p in PILOTS if p[0] == name)
                    state.m_ItemsToCreate, state.m_ResultSetQuantity = [pilot[3]], [pilot[4]]
                    state.m_NumberOfResults = 1
                source = Item('synthetic-source', health=40)
                outputs = NativeArray(Item(kind, health=100, quantity=quantity, wet=0, agents=0)
                                      for kind, quantity in zip(state.m_ItemsToCreate, state.m_ResultSetQuantity))
                state.native.SpawnItems = lambda pair, actor, dest: dest.extend(outputs)
                state.native.ApplyModificationsResults = lambda *args: None
                dest = NativeArray()
                state.SpawnItems([source, object()], object(), dest)
                state.ApplyModificationsResults([source, object()], dest, None, object())
                state.Do([source, object()], object(), dest, 0)
                for result in dest:
                    self.assertAlmostEqual(10 if state.m_HCRuinedOnly else 30, result.health)
                    self.assertEqual((0.6, 2, 0), (result.wet, result.agents, result.energy))

    def test_drysack_selects_health_agents_wetness_and_preserves_output_quantity(self):
        source = Item('DrysackBag_Green', health=20, quantity=0)
        bag, rope = Item('WaterproofBag_Green', health=100, quantity=0), Item('Rope', health=100, quantity=1)
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        source.owner = actor
        outcomes = iter([bag, rope])
        actor.SpawnEntityOnGroundRaycastDispersed = lambda kind: next(outcomes)

        def transfer(old, new, agents=True, variables=True, health=True, exclude_quantity=False):
            # Explicit native TransferItemProperties seam, not HC policy.
            if agents: new.agents |= old.agents
            if health: new.health = old.health
            if variables:
                new.energy = old.energy
                new.wet = old.wet
                if not exclude_quantity: new.quantity = old.quantity

        env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                   MiscGameplayFunctions=NS(TransferItemProperties=transfer))
        validate = authored('HCValidDrysack', 'item,player', env, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=False, HCValidDrysack=lambda *args: validate(None, *args))
        finish = authored('OnFinishProgressServer', 'action_data', env, 'HCDrysackSafety.c')
        finish(state, NS(m_MainItem=source, m_Player=actor))
        finish(state, NS(m_MainItem=source, m_Player=actor))
        self.assertEqual(1, source.delete_calls)
        self.assertEqual((0, 1), (bag.quantity, rope.quantity))
        for output in (bag, rope):
            self.assertEqual((20, 0.6, 2), (output.health, output.wet, output.agents))

    def test_occupied_source_is_refused_before_native_drysack_allocation(self):
        source = Item('DrysackBag_Green')
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        source.owner, source.IsEmpty = actor, lambda: False
        validate = authored('HCValidDrysack', 'item,player', {}, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=False, HCValidDrysack=lambda *args: validate(None, *args))
        finish = authored('OnFinishProgressServer', 'action_data',
                          {'GetGame': lambda: NS(IsServer=lambda: True)}, 'HCDrysackSafety.c')
        finish(state, NS(m_MainItem=source, m_Player=actor))
        self.assertEqual(0, source.delete_calls)


if __name__ == '__main__':
    unittest.main()
