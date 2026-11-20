"""Per-frame client cost guards. Synthetic adapters only; never DayZ evidence.

Each test fixes a cost the native action manager, recipe checks, HUD update or
input poll pays every frame. None of them changes a gameplay decision: the
server paths still run the full validation.
"""
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.legacy.test_group_server import body, EArray
from tests.legacy.test_group_ui import ui_member
from tests.legacy.test_salvage_tools import authored
from tests.legacy.test_event_transport import methods, Handle, ROOT as EVENT_ROOT

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / 'mods/HollowCountry/scripts'
NATIVE = SCRIPTS / '4_World/Survival/HCTapedLightNative.c'
ACTIONS = SCRIPTS / '4_World/Actions/HCTapedLightActions.c'
ICONS = SCRIPTS / '5_Mission/Groups/HCGroupWorldIcons.c'
CRAFT = 'HCNativeCraftingSafety.c'


def class_body(text, cls):
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    if not match:
        raise AssertionError('Missing authored class: ' + cls)
    return body(text, match.end())


def method_text(text, name):
    match = re.search(r'\b' + name + r'\([^)]*\)\s*\{', text)
    if not match:
        raise AssertionError('Missing authored method: ' + name)
    return body(text, match.end())


def runtime_member(cls, method, state, env, *args, ret=None):
    """Execute an authored static member; static fields become receiver fields."""
    source = class_body(NATIVE.read_text(), cls)
    source = re.sub(r'\bs_(\w+)', r'mHC\1', source)
    source = source.replace('new map<string, bool>', 'new HostMap')
    source = source.replace('ref array<ref HCTapedLightHostRow> ', '')
    source = re.sub(r'\bstatic (?:ItemBase|HCTapedLightHostRow) ' + method + r'\b', 'static int ' + method, source)
    source = re.sub(r'\b(?:ItemBase|EntityAI|InventoryLocation|PlayerBase|ComponentEnergyManager|HCTapedLightHostRow)\s+(?=\w+\s*[=;])',
                    'HCGroupNative ', source)
    source = source.replace('new InventoryLocation', 'new HCGroupLocation')
    env = dict(env, HINT_WINDOW_MS=300)
    return ui_member(source, method, state, env, *args)


class HostMap(dict):
    def Set(self, key, value): self[key] = value
    def Contains(self, key): return key in self


class TapedLightPreviewCostTests(unittest.TestCase):
    def preview_state(self, known, **hooks):
        calls = []
        state = NS(Held=lambda a, h: True, KnownHost=lambda h: calls.append('known') or known)
        env = dict(MountedLight=lambda h: calls.append('mounted') or hooks.get('mounted'),
                   Tape=lambda a: calls.append('tape') or hooks.get('tape'),
                   LooseLight=lambda a, h: calls.append('loose') or hooks.get('loose'))
        return state, env, calls

    def test_preview_stops_before_any_scan_when_the_host_is_not_in_the_catalog(self):
        state, env, calls = self.preview_state(False)
        for mounting in (True, False):
            del calls[:]
            self.assertFalse(runtime_member('HCTapedLightRuntime', 'Preview', state, env, NS(), NS(), mounting))
            self.assertEqual(['known'], calls)

    def test_mount_preview_checks_the_cheap_tape_before_the_loose_light_walk(self):
        state, env, calls = self.preview_state(True, tape=None, loose=NS())
        self.assertFalse(runtime_member('HCTapedLightRuntime', 'Preview', state, env, NS(), NS(), True))
        self.assertNotIn('loose', calls)
        state, env, calls = self.preview_state(True, tape=NS(), loose=NS())
        self.assertTrue(runtime_member('HCTapedLightRuntime', 'Preview', state, env, NS(), NS(), True))
        self.assertLess(calls.index('tape'), calls.index('loose'))

    def test_mount_preview_still_refuses_when_a_light_is_already_mounted(self):
        state, env, calls = self.preview_state(True, mounted=NS(), tape=NS(), loose=NS())
        self.assertFalse(runtime_member('HCTapedLightRuntime', 'Preview', state, env, NS(), NS(), True))
        self.assertNotIn('tape', calls)
        self.assertNotIn('loose', calls)

    def test_known_host_is_a_single_set_lookup_built_once(self):
        rows = EArray([NS(HostClass='CZ75'), NS(HostClass='AK101'), NS(HostClass='AK101')])
        built = []
        catalog = NS(Rows=lambda: built.append(1) or rows)
        state = NS(mHCHostTypes=None)
        env = dict(HCTapedLightCatalog=catalog, HostMap=HostMap)
        for kind, expected in (('CZ75', True), ('AK101', True), ('SNAFU_M4', False), ('', False)):
            host = NS(GetType=lambda kind=kind: kind)
            self.assertEqual(expected, runtime_member('HCTapedLightRuntime', 'KnownHost', state, env, host))
        self.assertFalse(runtime_member('HCTapedLightRuntime', 'KnownHost', state, env, None))
        self.assertEqual(1, len(built))

    def test_row_hoists_the_type_reads_out_of_the_catalog_loop(self):
        reads = {'host': 0, 'light': 0}
        host = NS(GetType=lambda: reads.__setitem__('host', reads['host'] + 1) or 'SNAFU_M4')
        light = NS(GetType=lambda: reads.__setitem__('light', reads['light'] + 1) or 'UniversalLight')
        rows = EArray([NS(HostClass='H' + str(i), SlotName='slot') for i in range(26)])
        catalog = NS(Rows=lambda: rows, Matches=lambda row, h, l, s: False, CrossRowMatch=lambda h, l: None)
        env = dict(HCTapedLightCatalog=catalog)
        source = class_body(NATIVE.read_text(), 'HCTapedLightV1Qualification')
        source = source.replace('static HCTapedLightHostRow Row', 'static int Row')
        source = source.replace('static HCTapedLightHostRow CrossRow', 'static int CrossRow')
        source = source.replace('ref array<ref HCTapedLightHostRow> ', '')
        source = re.sub(r'\b(?:HCTapedLightHostRow|InventoryLocation)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
        self.assertIsNone(ui_member(source, 'Row', NS(CrossRow=lambda h, l: None), env, host, light))
        self.assertEqual({'host': 1, 'light': 1}, reads)

    def test_mounted_light_reads_the_host_type_once_for_all_rows(self):
        reads = []
        host = NS(GetType=lambda: reads.append(1) or 'SNAFU_M4', FindAttachmentBySlotName=lambda slot: None)
        rows = EArray([NS(HostClass='H' + str(i), SlotName='slot') for i in range(26)])
        env = dict(HCTapedLightCatalog=NS(Rows=lambda: rows, Matches=lambda *a: False),
                   ItemBase=NS(Cast=lambda x: x))
        self.assertIsNone(runtime_member('HCTapedLightRuntime', 'MountedLight', NS(), env, host))
        self.assertEqual(1, len(reads))

    def test_loose_light_rejects_cheap_energy_cases_before_the_catalog_row(self):
        rows_read = []
        items = EArray()
        actor = NS(GetInventory=lambda: NS(EnumerateInventory=lambda mode, out: out.extend(items) or True))
        env = dict(InventoryTraversalType=NS(PREORDER=1), InventoryLocationType=NS(CARGO=3),
                   ItemBase=NS(Cast=lambda item: item), HCGroupLocation=lambda: NS(GetType=lambda: 3),
                   HCTapedLightV1Qualification=NS(Row=lambda h, c: rows_read.append(c) or c.known))
        def candidate(em):
            return NS(known=True, IsDamageDestroyed=lambda: False, GetCompEM=lambda: em,
                      GetHierarchyRootPlayer=lambda: actor,
                      GetInventory=lambda: NS(GetCurrentInventoryLocation=lambda location: True))
        items.extend([candidate(None), candidate(NS(IsSwitchedOn=lambda: True))])
        source = class_body(NATIVE.read_text(), 'HCTapedLightRuntime')
        source = source.replace('array<EntityAI> items = new array<EntityAI>', 'HCGroupNative items = NewItems()')
        source = re.sub(r'\b(?:ItemBase|EntityAI|InventoryLocation|ComponentEnergyManager)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
        source = source.replace('static ItemBase LooseLight', 'static int LooseLight')
        source = source.replace('new InventoryLocation', 'new HCGroupLocation')
        env['NewItems'] = EArray
        self.assertIsNone(ui_member(source, 'LooseLight', NS(), env, actor, NS()))
        self.assertEqual([], rows_read)


class TapedLightClientHintTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.previews = []
        self.held = True
        self.host = object()
        self.state = NS(mHCHintHost=None, mHCHintTime=0, mHCHintMount=False, mHCHintRemove=False,
                        Held=lambda a, h: self.held,
                        Preview=lambda a, h, mounting: self.previews.append(mounting) or (mounting is True))
        self.env = dict(GetGame=lambda: NS(GetTime=lambda: self.now))

    def hint(self, mounting, host=None):
        return runtime_member('HCTapedLightRuntime', 'PreviewHint', self.state, self.env,
                              NS(), host or self.host, mounting)

    def test_both_actions_share_one_preview_pass_per_window(self):
        self.assertTrue(self.hint(True))
        self.assertFalse(self.hint(False))
        self.now += 100
        self.assertTrue(self.hint(True))
        self.assertFalse(self.hint(False))
        self.assertEqual(2, len(self.previews))

    def test_hint_refreshes_after_the_window_a_new_host_or_a_clock_reset(self):
        self.hint(True)
        base = len(self.previews)
        self.now += 400
        self.hint(True)
        self.assertEqual(base * 2, len(self.previews))
        count = len(self.previews)
        self.hint(True, object())
        self.assertGreater(len(self.previews), count)
        count = len(self.previews)
        self.now = 10
        self.hint(True)
        self.assertGreater(len(self.previews), count)

    def test_hint_never_answers_for_a_weapon_that_is_no_longer_held(self):
        self.hint(True)
        self.held = False
        self.assertFalse(self.hint(True))

    def test_server_authority_is_untouched_by_the_client_hint(self):
        native = NATIVE.read_text()
        actions = ACTIONS.read_text()
        can_execute = method_text(native, 'CanExecute')
        self.assertIn('Preview(actor, host, mounting)', can_execute)
        self.assertNotIn('PreviewHint', can_execute)
        self.assertNotIn('PreviewHint', method_text(native, 'ExecuteOwned'))
        for mounting in ('true', 'false'):
            self.assertIn('if (!GetGame().IsServer()) { return HCTapedLightRuntime.PreviewHint(player, item, ' + mounting + '); }', actions)
            self.assertIn('if (HCTapedLightRuntime.CanExecute(player, item, ' + mounting + ')) return true;', actions)
        servers = list(re.finditer(r'override void OnExecuteServer\([^)]*\)\s*\{', actions))
        self.assertEqual(3, len(servers))
        for match in servers:
            self.assertNotIn('PreviewHint', body(actions, match.end()))


class RecipeScopeCacheTests(unittest.TestCase):
    def env(self, counter):
        scoped = authored('IsScoped', 'recipeName', {}, CRAFT)
        safety = NS(IsScoped=lambda name: counter.append(name) or scoped(None, name))
        return {'HCNativeCraftingSafety': safety}

    def recipe(self, name, counter):
        env = self.env(counter)
        state = NS(ClassName=lambda: name, m_HCScopedState=0)
        helper = authored('HCIsScoped', '', env, CRAFT)
        state.HCIsScoped = lambda: helper(state)
        return state

    def test_scope_is_computed_once_per_recipe_instance_and_matches_the_chain(self):
        reference = authored('IsScoped', 'recipeName', {}, CRAFT)
        for name, expected in (('CraftRag', True), ('OpenGunCase', True), ('SomeVanillaRecipe', False), ('', False)):
            counter = []
            state = self.recipe(name, counter)
            answers = [state.HCIsScoped() for _ in range(5)]
            self.assertEqual([expected] * 5, answers)
            self.assertEqual(reference(None, name), expected)
            self.assertEqual([name], counter)

    def test_check_and_perform_use_the_cached_scope_not_the_name_chain(self):
        text = (SCRIPTS / '4_World/Crafting' / CRAFT).read_text()
        modded = text.split('modded class RecipeBase', 1)[1].split('modded class CraftLeatherSack', 1)[0]
        check = method_text(modded, 'CheckRecipe')
        perform = method_text(modded, 'PerformRecipe')
        for source in (check, perform):
            self.assertIn('HCIsScoped()', source)
            self.assertNotIn('IsScoped(ClassName())', source)
        self.assertIn('protected int m_HCScopedState;', modded)

    def test_every_scoped_name_still_returns_true_and_unscoped_stays_false(self):
        text = (SCRIPTS / '4_World/Crafting' / CRAFT).read_text()
        names = re.findall(r'recipeName == "([^"]+)"', method_text(text, 'IsScoped'))
        self.assertEqual(len(names), method_text(text, 'IsScoped').count('return true;'))
        self.assertGreater(len(names), 100)
        for name in names:
            counter = []
            self.assertTrue(self.recipe(name, counter).HCIsScoped(), name)
        self.assertFalse(self.recipe('Craft' + 'Nothing', []).HCIsScoped())


class SettableList(EArray):
    def Set(self, index, value): self[index] = value


class WorldIconCostTests(unittest.TestCase):
    class Vec(tuple):
        def __sub__(self, other): return WorldIconCostTests.Vec(a - b for a, b in zip(self, other))

    def build(self):
        V = self.Vec
        self.calls = {'find': 0, 'text': 0, 'scale': 0, 'color': 0}
        calls = self.calls
        def widget():
            image = NS(SetColor=lambda c: calls.__setitem__('color', calls['color'] + 1))
            label = NS(SetText=lambda t: calls.__setitem__('text', calls['text'] + 1) or calls.setdefault('texts', []).append(t))
            def find(name):
                calls['find'] += 1
                return image if name == 'HCMark' else label
            return NS(FindAnyWidget=find, SetPos=lambda *a: None, Show=lambda *a: None, Unlink=lambda: None)
        viewer = NS(IsAlive=lambda: True, IsUnconscious=lambda: False, GetPosition=lambda: V((0, 0, 0)),
                    GetIdentity=lambda: NS(GetId=lambda: 'me'))
        game = NS(GetPlayer=lambda: viewer, GetUIManager=lambda: NS(GetMenu=lambda: None),
                  GetCurrentCameraPosition=lambda: V((0, 0, 0)), GetCurrentCameraDirection=lambda: V((0, 0, 1)),
                  GetScreenPosRelative=lambda p: V((0.5, 0.5, 0)), GetScreenPos=lambda p: V((100, 100, 0)),
                  GetWorkspace=lambda: NS(CreateWidgets=lambda path: widget()))
        self.settings = NS(WorldIcons=True, MaxIconDistance=100., IconScale=1., LabelScale=1.)
        self.members = EArray([NS(HasPosition=True, Online=True, Alive=True, Id='m' + str(i),
                                  Name='Mate' + str(i), Position=V((0, 0, 10 + i))) for i in range(3)])
        self.frame = NS(Enabled=True, GroupId=1, Epoch=1, Settings=self.settings, Members=self.members)
        source = ICONS.read_text()
        source = source.replace('Widget FindIconSlot', 'int FindIconSlot')
        self.state = NS(mHCPool=SettableList(), mHCLabels=SettableList(), mHCImages=SettableList(),
                        mHCNames=SettableList(), mHCStyled=SettableList(), mHCTexted=SettableList(),
                        mHCStyleIcon=0., mHCStyleLabel=0., mHCStyleEpoch=1, mHCGroup=0, mHCEpoch=0)
        env = dict(GetGame=lambda: game, PlayerBase=NS(Cast=lambda p: p),
                   TextWidget=NS(Cast=lambda w: w), ImageWidget=NS(Cast=lambda w: w),
                   ARGB=lambda *a: 0, Math=NS(Round=lambda x: x),
                   HCGroupWorldIcons=NS(Scale=lambda *a: calls.__setitem__('scale', calls['scale'] + 1)))
        self.state.Clear = lambda: ui_member(source, 'Clear', self.state, env)
        self.state.HideUnused = lambda n: None  # unchanged loop; the translator has no for-loop support
        self.state.Scale = lambda *a: calls.__setitem__('scale', calls['scale'] + 1)
        self.state.FindIconSlot = lambda i: ui_member(source, 'FindIconSlot', self.state, env, i)
        self.source, self.env = source, env

    def update(self):
        return ui_member(self.source, 'Update', self.state, self.env, self.frame)

    def test_steady_frames_do_no_widget_lookup_scale_or_text_writes(self):
        self.build()
        self.update()
        first = dict(self.calls)
        self.assertEqual(3, first['text'])
        self.assertEqual(3, first['scale'])
        for _ in range(4):
            self.update()
        self.assertEqual(first['find'], self.calls['find'])
        self.assertEqual(first['text'], self.calls['text'])
        self.assertEqual(first['scale'], self.calls['scale'])
        self.assertEqual(first['color'], self.calls['color'])

    def test_name_change_and_scale_change_refresh_only_what_changed(self):
        self.build()
        self.update()
        self.members[1].Name = 'Renamed'
        self.update()
        self.assertEqual(4, self.calls['text'])
        self.assertEqual('[Team] Renamed', self.calls['texts'][-1])
        self.assertEqual(3, self.calls['scale'])
        self.settings.LabelScale = 1.5
        self.update()
        self.assertEqual(6, self.calls['scale'])
        self.assertEqual(4, self.calls['text'])

    def test_clear_drops_every_cached_widget_reference(self):
        self.build()
        self.update()
        self.state.Clear()
        for name in ('mHCPool', 'mHCLabels', 'mHCImages', 'mHCNames', 'mHCStyled', 'mHCTexted'):
            self.assertEqual(0, len(getattr(self.state, name)), name)
        self.update()
        self.assertEqual(6, self.calls['text'])

    def test_empty_member_name_still_gets_its_team_prefix(self):
        self.build()
        self.members[0].Name = ''
        self.update()
        self.assertIn('[Team] ', self.calls['texts'])


class EventInputCacheTests(unittest.TestCase):
    def test_retired_event_hook_inherits_native_lifecycle_without_input_or_frame_work(self):
        calls = []
        class NativeMission:
            def OnInit(self): calls.append('init')
            def OnUpdate(self, dt): calls.append(('native-update', dt))
            def OnMissionFinish(self): calls.append('finish')
        env = dict(GetUApi=lambda: self.fail('retired input queried'),
                   GetGame=lambda: self.fail('retired hook queried game'),
                   native_super_OnInit=lambda: calls.append('init'),
                   native_super_OnUpdate=lambda dt: calls.append(('native-update', dt)),
                   native_super_OnMissionFinish=lambda: calls.append('finish'),
                   HCEventClient=NS(Get=lambda: self.fail('retired client polled')))
        authored = methods(EVENT_ROOT / '5_Mission/Events/HCEventGameplay.c', env)
        hook = type('SyntheticMission', (authored, NativeMission), {})()
        hook.OnInit()
        for _ in range(5): hook.OnUpdate(.1)
        hook.OnMissionFinish()
        self.assertEqual(['init'] + [('native-update', .1)] * 5 + ['finish'], calls)
        self.assertEqual({}, vars(hook))


if __name__ == '__main__':
    unittest.main()
