"""Catalog contracts and authored client behavior with explicit synthetic natives.

These tests execute small authored methods using the existing statement adapter;
they do not establish Enforce compilation, DayZ rendering or network behavior.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.legacy.test_admin_test_kit import authored_method, compile_authored, base_scope, strip_comments
from tests.legacy.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
CATALOG = SCRIPTS / '3_Game/Admin/HCAdminCatalog.c'
SERVER = SCRIPTS / '4_World/Admin/HCAdminModule.c'
CLIENT = SCRIPTS / '5_Mission/Admin/HCAdminClient.c'
MENU = SCRIPTS / '5_Mission/Admin/HCAdminMenu.c'
LAYOUTS = ROOT / 'mods/HollowCountry/gui/layouts'


def entries():
    text = strip_comments(CATALOG.read_text())
    pattern = r'HCAdd\("(\w+)", "(\w+)", "([^"]+)", "([^"]+)", (true|false), (true|false), (true|false), (\d+), (\d+), (\d+), "([^"]*)"\);'
    return [NS(id=m[0], section=m[1], label=m[2], help=m[3], read_only=m[4]=='true',
               at_position=m[5]=='true', integer=m[6]=='true', lo=int(m[7]), hi=int(m[8]), default=int(m[9]), unit=m[10])
            for m in re.findall(pattern, text)]


class CatalogContracts(unittest.TestCase):
    def test_catalog_equals_all_dispatched_commands_exactly_once(self):
        ids = [e.id for e in entries()]
        dispatched = set()
        # HCExtra is the final HCCommand branch, so its handlers are included.
        for name in ('HCDispatch', 'HCCommand', 'HCExtra', 'HCOperatorCommand'):
            _, body = authored_method(SERVER, 'HCAdminModule', name, modded=False)
            dispatched.update(re.findall(r'command == "(\w+)"', body))
        self.assertEqual(dispatched, set(ids))
        self.assertEqual(len(ids), len(set(ids)))
        _, known = authored_method(SERVER, 'HCAdminModule', 'HCKnown', modded=False)
        self.assertIn('HCAdminCatalog.HCKnown(command)', known)
        self.assertNotIn('command ==', known)

    def test_sections_and_metadata(self):
        self.assertEqual({'overview', 'infected', 'ai', 'world', 'economy', 'time'}, {e.section for e in entries()})
        text = CATALOG.read_text()
        for section in ('overview', 'infected', 'ai', 'world', 'economy', 'time', 'map'):
            self.assertIn('HCSection("' + section + '"', text)
        self.assertEqual({'status','kit','list','snapshot','tplist','tprefresh'}, {e.id for e in entries() if e.read_only})
        for entry in entries():
            self.assertTrue(entry.label and entry.help)
            self.assertLessEqual(entry.lo, entry.default)
            self.assertLessEqual(entry.default, entry.hi)

    def test_value_ranges_match_server_clamps_and_validation(self):
        values = {e.id: (e.lo, e.hi) for e in entries() if e.integer}
        directors = strip_comments((SCRIPTS / '4_World/Admin/HCAdminDirectors.c').read_text())
        weather = strip_comments((SCRIPTS / '4_World/Weather/HCWeatherDaysModule.c').read_text())
        day = re.search(r'Math.Clamp\(requested, (\d+), (\d+)\)', directors)
        memory = re.search(r'shots < (\d+) \|\| shots > (\d+)', directors)
        code = re.search(r'code < (\d+) \|\| code > (\d+)', weather)
        self.assertEqual({'day': tuple(map(int,day.groups())), 'memory': tuple(map(int,memory.groups())),
                          'weather': tuple(map(int,code.groups())), 'camptier': (0, 3),
                          'tp': (0, 255), 'tplist': (0, 255)}, values)

    def test_authored_clamp_handles_both_boundaries(self):
        fn = compile_authored(CATALOG, 'HCAdminCommand', 'HCClamp', base_scope(), modded=False)
        for entry in entries():
            command = NS(m_Min=entry.lo, m_Max=entry.hi)
            for given, expected in ((-1,entry.lo), (99999,entry.hi), (entry.default,entry.default)):
                self.assertEqual(expected, fn(command, given))

    def test_menu_builds_generic_cards_and_tabs_without_dispatch_ids(self):
        _, build = authored_method(MENU, 'HCAdminMenu', 'HCBuildCards', modded=False)
        self.assertIn('HCAdminCatalog.Commands()', build)
        self.assertIn('entry.Section', build)
        self.assertIn('hc_admin_card.layout', build)
        _, click = authored_method(MENU, 'HCAdminMenu', 'OnClick', modded=False)
        self.assertIn('card.Entry.Id', click)
        for entry in entries():
            self.assertNotIn('"' + entry.id + '"', click)
        _, update = authored_method(MENU, 'HCAdminMenu', 'Update', modded=False)
        self.assertNotIn('CreateWidgets', update)
        self.assertNotIn('HCRender', update)
        self.assertIn('HCApplyBusy', update)

    def test_templates_match_all_literal_script_lookups(self):
        text = MENU.read_text()
        for path in re.findall(r'CreateWidgets\("HollowCountry/gui/layouts/([^"]+)"', text):
            self.assertTrue((LAYOUTS / path).is_file(), path)
        layouts = '\n'.join(p.read_text() for p in LAYOUTS.glob('hc_admin*.layout'))
        for name in re.findall(r'Find(?:Any)?Widget\("([^"]+)"\)', text):
            self.assertRegex(layouts, r'WidgetClass ' + re.escape(name) + r'\s*\{', name)
        console = (LAYOUTS / 'hc_admin_line.layout').read_text()
        self.assertIn('MultilineTextWidgetClass HCAdminLine', console)
        self.assertIn('wrap 1', console)
        self.assertIn('"size to text v" 1', console)


class SyntheticArray(EArray):
    def InsertAt(self, value, index):
        self.insert(index, value)


class ClientBehavior(unittest.TestCase):
    def fixture(self):
        self.now = 10.0
        self.sent = []
        self.logged = []
        self.changed = []
        self.client = NS(m_Pending=False, m_RequestUntil=20.0, m_NextSend=0.0, m_Expected=7,
                         m_Command='status', m_Checks=SyntheticArray(['status','kit','list']), Revision=0)
        self.client.HCValid = lambda: True
        self.client.HCSend = self.send
        self.client.HCLog = lambda *args: self.logged.append(args)
        self.client.Changed = NS(Invoke=lambda: self.changed.append(True))
        self.scope = base_scope(GetGame=lambda: NS(GetTickTime=lambda:self.now))
        self.tick = compile_authored(CLIENT,'HCAdminClient','HCRequestTick',self.scope,
                                    ('HCValid','HCSend','HCLog'),modded=False, fields=('Revision','Notice','Changed'))

    def send(self, command, value):
        self.sent.append((self.now,command,value))
        self.client.m_Pending = True
        self.client.m_NextSend = self.now + 1.1
        return True

    def test_checks_wait_for_each_reply_and_rate_limit(self):
        self.fixture()
        self.tick(self.client)
        self.assertEqual([(10.0,'status',0)],self.sent)
        self.now = 10.5
        self.tick(self.client)
        self.assertEqual(1,len(self.sent))
        self.client.m_Pending = False  # synthetic validated current-ticket reply
        self.tick(self.client)
        self.assertEqual(1,len(self.sent))
        self.now = 11.11
        self.tick(self.client)
        self.assertEqual('kit',self.sent[-1][1])
        self.client.m_Pending = False
        self.now = 12.22
        self.tick(self.client)
        self.assertEqual(['status','kit','list'],[s[1] for s in self.sent])
        self.assertEqual([],self.client.m_Checks)

    def test_timeout_cancels_remaining_checks_and_never_retries(self):
        self.fixture()
        self.client.m_Pending = True
        self.now = 20.0
        self.tick(self.client)
        self.assertFalse(self.client.m_Pending)
        self.assertEqual(0,self.client.m_Expected)
        self.assertEqual([],self.client.m_Checks)
        self.assertEqual([],self.sent)
        self.assertIn('timeout',self.logged[0][2])
        self.tick(self.client)
        self.assertEqual([],self.sent)

    def test_console_keeps_newest_fifty_full_lines(self):
        line = lambda: NS()
        fn = compile_authored(CLIENT,'HCAdminClient','HCLog',base_scope(HCAdminConsoleLine=line,
            HCStamp=lambda:'12:34:56'),modded=False)
        client = NS(m_Console=SyntheticArray())
        for index in range(65):
            fn(client,'kit',True,'line '+str(index)+' '+('x'*1000))
        self.assertEqual(50,len(client.m_Console))
        self.assertTrue(client.m_Console[0].Text.endswith('x'*1000))
        self.assertIn('line 64',client.m_Console[0].Text)
        self.assertIn('line 15',client.m_Console[-1].Text)
        self.assertIn('12:34:56',client.m_Console[0].Text)
        self.assertIn('kit',client.m_Console[0].Text)
        self.assertTrue(client.m_Console[0].Ok)

    def test_only_validated_current_reply_releases_pending(self):
        _, body = authored_method(CLIENT,'HCAdminClient','HCReceive',modded=False)
        release = body.index('m_Pending = false')
        self.assertLess(body.index('if (!current && !capture && !loot)'),release)
        self.assertLess(body.index('reply.Marks.Count() > 512'),release)
        self.assertIn('if (current)',body[:release])
        self.assertIn('HCLogReply',body)
        _, stop = authored_method(CLIENT,'HCAdminClient','HCStop',modded=False)
        self.assertIn('m_Checks.Clear()',stop)


class NativeString(str):
    """Only documented native string operations; no HC policy."""
    def Length(self): return len(self)
    def IndexOf(self, other): return self.find(other)
    def Get(self, index): return self[index]
    def ToInt(self): return int(self)


class SyntheticWidget:
    def __init__(self, name='Button', text=''):
        self.name, self.text, self.enabled = name, text, True
    def GetName(self): return self.name
    def GetText(self): return NativeString(self.text)
    def SetText(self, value): self.text = value
    def Enable(self, value): self.enabled = value


class CardBehavior(unittest.TestCase):
    def make_card(self, entry):
        clamp = compile_authored(CATALOG,'HCAdminCommand','HCClamp',base_scope(),modded=False)
        descriptor = NS(Id=entry.id, Integer=entry.integer, m_Min=entry.lo, m_Max=entry.hi,
                        HCRange=lambda: 'fixture range')
        descriptor.HCClamp = lambda value: clamp(descriptor,value)
        step = compile_authored(CATALOG,'HCAdminCommand','HCStep',base_scope(),('HCClamp',),modded=False)
        descriptor.HCStep = lambda value,direction:step(descriptor,value,direction)
        card = NS(Entry=descriptor, Value=entry.default, Run=SyntheticWidget(), Minus=SyntheticWidget(),
                  Plus=SyntheticWidget(), Edit=SyntheticWidget(text=str(entry.default)))
        read = compile_authored(MENU,'HCAdminCard','HCReadValue',base_scope(),modded=False,
                                fields=('Entry','Value','Edit'),native_strings=NativeString)
        card.HCReadValue = lambda: read(card)
        return card

    def test_typed_values_clamp_and_malformed_values_never_become_zero(self):
        for entry in entries():
            if not entry.integer: continue
            card = self.make_card(entry)
            for invalid in ('','-1','1a','1.2','2147483648'):
                card.Edit.text = invalid
                self.assertFalse(card.HCReadValue(), (entry.id,invalid))
                self.assertEqual(entry.default,card.Value)
            card.Edit.text = '9999'
            self.assertTrue(card.HCReadValue())
            self.assertEqual(entry.hi,card.Value)
            self.assertEqual(str(entry.hi),card.Edit.text)
            card.Edit.text = '0'
            self.assertTrue(card.HCReadValue())
            self.assertEqual(entry.lo,card.Value)

    def fixture(self, card):
        self.sent, self.feedback = [], []
        client = NS(HCValid=lambda:True,HCBusy=lambda:False,
                    HCSend=lambda cmd,value:self.sent.append((cmd,value)),
                    HCFeedback=self.feedback.append)
        owner = NS(m_Client=client,m_Tabs=EArray(),m_Cards=EArray([card]),m_Checks=SyntheticWidget('checks'),
                   HCApplyBusy=lambda:None)
        click = compile_authored(MENU,'HCAdminMenu','OnClick',base_scope(),
                                 ('HCSelect','HCRenderMap','HCApplyBusy','Close','HCRunLootMap'),modded=False)
        return owner,click

    def test_every_run_button_dispatches_its_catalog_id_and_value(self):
        for entry in entries():
            card = self.make_card(entry)
            owner,click = self.fixture(card)
            self.assertTrue(click(owner,card.Run,0,0,0))
            self.assertEqual([(entry.id,entry.default)],self.sent)

    def test_minus_plus_clamp_and_busy_or_invalid_input_cannot_send(self):
        entry = next(e for e in entries() if e.id=='memory')
        card = self.make_card(entry)
        owner,click = self.fixture(card)
        card.Edit.text = '0'
        click(owner,card.Minus,0,0,0)
        self.assertEqual(0,card.Value)
        card.Edit.text = str(entry.hi)
        click(owner,card.Plus,0,0,0)
        self.assertEqual(entry.hi,card.Value)
        self.assertEqual([],self.sent)
        card.Edit.text = 'bad'
        click(owner,card.Run,0,0,0)
        self.assertEqual([],self.sent)
        self.assertEqual(1,len(self.feedback))
        owner.m_Client.HCBusy = lambda:True
        card.Edit.text = '1'
        click(owner,card.Run,0,0,0)
        self.assertEqual([],self.sent)

    def test_busy_disables_all_action_and_value_controls(self):
        card = self.make_card(entries()[0])
        owner = NS(m_Client=NS(HCBusy=lambda:True,HCState=lambda:'admin | waiting for server'),
                   m_State=SyntheticWidget(),m_Checks=SyntheticWidget(),m_Cards=EArray([card]),
                   m_LootRun=SyntheticWidget(),m_LootFilter=SyntheticWidget())
        apply = compile_authored(MENU,'HCAdminMenu','HCApplyBusy',base_scope(),modded=False)
        apply(owner)
        for widget in (card.Run,card.Minus,card.Plus,card.Edit,owner.m_Checks,owner.m_LootRun,owner.m_LootFilter):
            self.assertFalse(widget.enabled)
        owner.m_Client.HCBusy = lambda:False
        apply(owner)
        for widget in (card.Run,card.Minus,card.Plus,card.Edit,owner.m_Checks,owner.m_LootRun,owner.m_LootFilter):
            self.assertTrue(widget.enabled)

    def test_map_tab_lootmap_run_sends_the_typed_filter_and_is_gated_on_busy(self):
        card = self.make_card(entries()[0])
        owner,click = self.fixture(card)
        asked = []
        owner.m_Client.HCLootMap = lambda text: asked.append(str(text)) or True
        owner.m_LootFilter = SyntheticWidget('HCAdminLootFilter', 'Bandage*')
        owner.m_LootRun = SyntheticWidget('HCAdminLootRun')
        run = compile_authored(MENU,'HCAdminMenu','HCRunLootMap',base_scope(),('HCApplyBusy',),modded=False)
        owner.HCRunLootMap = lambda: run(owner)
        self.assertTrue(click(owner,owner.m_LootRun,0,0,0))
        self.assertEqual(['Bandage*'],asked)
        self.assertEqual([],self.sent)  # not a catalog card: no integer command dispatched
        owner.m_Client.HCBusy = lambda:True
        self.assertTrue(click(owner,owner.m_LootRun,0,0,0))
        self.assertEqual(['Bandage*'],asked)  # busy: nothing sent
        owner.HCRunLootMap()
        self.assertEqual(['Bandage*'],asked)  # the helper is gated as well

    def test_map_panel_layout_holds_one_edit_box_and_a_run_button_with_vanilla_widget_types(self):
        text = (LAYOUTS / 'hc_admin.layout').read_text()
        panel = text.split('FrameWidgetClass HCAdminMapPanel')[1]
        self.assertRegex(panel, r'EditBoxWidgetClass HCAdminLootFilter \{')
        self.assertRegex(panel, r'ButtonWidgetClass HCAdminLootRun \{')
        self.assertEqual(1, text.count('EditBoxWidgetClass'))
        menu = MENU.read_text()
        for name in ('HCAdminLootFilter', 'HCAdminLootRun'):
            self.assertIn('FindAnyWidget("%s")' % name, menu)
        # Vanilla natives (1_Core/proto/EnWidgets.c:347-350 EditBoxWidget.GetText/SetText,
        # :126 Widget.Enable) are the only widget calls the lootmap controls use.
        self.assertIn('m_LootFilter.GetText()', menu)
        self.assertIn('m_LootFilter.Enable(!busy)', menu)

    def test_selecting_current_tab_does_not_rebuild_or_reset_values(self):
        select = compile_authored(MENU,'HCAdminMenu','HCSelect',base_scope(),
                                  ('HCBuildCards','HCRenderRoutes','Close'),modded=False)
        # No widgets are supplied: selecting the current section must return
        # before accessing or rebuilding any widgets.
        select(NS(m_Section='overview'),NS(Id='overview'))

    def test_invalid_value_stays_invalid_when_edit_loses_focus_before_run(self):
        entry = next(e for e in entries() if e.id=='weather')
        card = self.make_card(entry)
        owner,click = self.fixture(card)
        change = compile_authored(MENU,'HCAdminMenu','OnChange',base_scope(),modded=False)
        card.Edit.text = 'bad'
        change(owner,card.Edit,0,0,True)  # native finished-edit event before click
        click(owner,card.Run,0,0,0)
        self.assertEqual([],self.sent, 'invalid input must not silently become the old default')
        self.assertEqual('bad',card.Edit.text)

    def test_new_catalog_integer_ranges_do_not_need_menu_changes(self):
        # Explicit synthetic future command: no existing wire handler is added.
        entry = NS(id='fixture', integer=True, lo=-200000, hi=100000, default=0)
        card = self.make_card(entry)
        for text, expected in (('99999',99999),('-123456',-123456),
                               ('2147483647',100000),('-2147483648',-200000)):
            card.Edit.text = text
            self.assertTrue(card.HCReadValue(), text)
            self.assertEqual(expected,card.Value)
        for invalid in ('2147483648','-2147483649'):
            card.Edit.text = invalid
            self.assertFalse(card.HCReadValue(), invalid)

    def test_step_at_native_integer_limits_never_overflows(self):
        step = compile_authored(CATALOG,'HCAdminCommand','HCStep',base_scope(),('HCClamp',),modded=False)
        clamp = compile_authored(CATALOG,'HCAdminCommand','HCClamp',base_scope(),modded=False)
        entry = NS(m_Min=-2147483648,m_Max=2147483647)
        entry.HCClamp = lambda value:clamp(entry,value)
        for value, direction, expected in ((entry.m_Min,-1,entry.m_Min), (entry.m_Max,1,entry.m_Max),
                                            (0,-1,-1),(0,1,1)):
            self.assertEqual(expected,step(entry,value,direction))
