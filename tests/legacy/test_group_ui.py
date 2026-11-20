"""Synthetic execution of authored UI methods; never engine/UI acceptance."""
from pathlib import Path
import copy
import json
import re
from types import SimpleNamespace as NS
import unittest
from tests.legacy.test_group_server import EArray, body, translated_rules, execute_member

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry'


def ui_member(source, name, state, env, *args):
    """Adapt receiver/type syntax; execute the authored method body."""
    match = re.search(r'\b(?:bool|int|void|string) ' + name + r'\(([^)]*)\)\s*\{', source)
    if not match:
        raise AssertionError('Missing authored method: ' + name)
    code = body(source, match.end())
    def literal(match):
        key = '_ui_literal_' + str(len(env))
        env[key] = json.loads(match[0])
        return key
    code = re.sub(r'"(?:\\.|[^"\\])*"', literal, code)
    code = re.sub(r'\bmHC\w+\b', lambda m: 'self.' + m[0], code)
    for method in re.findall(r'\b(?:bool|int|void|string) (\w+)\(', source):
        code = re.sub(r'(?<![\w.])' + method + r'\(', 'self.' + method + '(', code)
    code = re.sub(r'\b(?:Widget|PlayerBase|TextWidget|TextListboxWidget|ImageWidget)\s+(?=\w+\s*[=;])',
                  'HCGroupNative ', code)
    wrapper = 'void ' + name + '(' + match[1] + '){' + code + '}'
    return execute_member(wrapper, name, env, state, *args)


class SyntheticList:
    def __init__(self): self.items, self.selected = [], -1
    def ClearItems(self): self.items.clear(); self.selected = -1
    def AddItem(self, text, *_): self.items.append(text); return len(self.items)-1
    def GetSelectedRow(self): return self.selected
    def SelectRow(self, row): self.selected = row


class SyntheticEdit:
    def __init__(self, text): self.text = text
    def GetText(self): return self.text
    def SetText(self, text): self.text = text


def menu_method(name, env):
    source = (ROOT/'scripts/5_Mission/Groups/HCGroupMapMenu.c').read_text()
    match = re.search(r'bool ' + name + r'\(([^)]*)\)\s*\{', source)
    if not match:
        raise AssertionError('Missing authored native callback: ' + name)
    code = re.sub(r'//[^\n]*', '', body(source, match.end()))
    code = re.sub(r'if\s*\(([^{};]+)\)\s*([^{};]+);',
                  r'if (\1) {\2;}', code)
    args = [arg.strip().split()[-1] for arg in match[1].split(',')]
    lines, indent = ['def run(' + ','.join(args) + '):'], 1
    for token in re.split(r'([{};])', code):
        token = token.strip()
        if not token or token == ';': continue
        if token == '{': indent += 1; continue
        if token == '}': indent -= 1; continue
        token = re.sub(r'\bHCGroupRequest q = new HCGroupRequest\b',
                       'q = HCGroupRequest()', token)
        token = re.sub(r'\bint (\w+)\s*=', r'\1 =', token)
        token = token.replace('&&', ' and ').replace('||', ' or ')
        token = re.sub(r'!(?!=)', 'not ', token)
        token = re.sub(r'\btrue\b', 'True', token)
        token = re.sub(r'\bfalse\b', 'False', token)
        if token.startswith('if ('):
            token = 'if ' + token[4:-1] + ':'
        lines.append('    '*indent + token)
    exec(compile('\n'.join(lines), '<authored-menu-subset>', 'exec'), env)
    return env['run']


class GroupUITests(unittest.TestCase):
    def test_menu_factory_preserves_native_dispatch_and_sets_custom_id(self):
        source = (ROOT/'scripts/5_Mission/Groups/HCGroupMenuFactory.c').read_text()
        source = source.replace('UIScriptedMenu CreateScriptedMenu', 'int CreateScriptedMenu')
        source = source.replace('UIScriptedMenu menu', 'HCGroupMapMenu menu')
        calls = []
        custom = NS(SetID=calls.append)
        native = object()
        env = {'HCGroupProtocol': NS(MENU_MAP=48537),
               'HCGroupMapMenu': lambda: custom,
               'super': NS(CreateScriptedMenu=lambda id: native)}
        self.assertIs(execute_member(source, 'CreateScriptedMenu', env, NS(), 48537), custom)
        self.assertEqual(calls, [48537])
        self.assertIs(execute_member(source, 'CreateScriptedMenu', env, NS(), 5), native)
        self.assertEqual(calls, [48537])

    def setUp(self):
        self.e = translated_rules()
        self.e.update(
            HCGroupRules=NS(TextValid=self.e['TextValid']),
            HCGroupClock=NS(Utc=lambda: 1000),
            mHCHasPoint=True, mHCMarkerId=7, mHCColor=123,
            mHCConflict=False, mHCRefreshing=False,
            mHCIcon=4, mHCExpires=1010, mHCPoint=[100., 0., 200.],
            mHCName=NS(GetText=lambda: 'Rally'),
            mHCNote=NS(GetText=lambda: 'Shared note'))
        self.sent = []
        self.client = NS(Send=self.sent.append)

    def test_edit_preserves_metadata_without_renewing_deadline(self):
        menu_method('SaveMarker', self.e)(self.client)
        q, = self.sent
        self.assertEqual((q.Op, q.EntityId, q.Name, q.Note),
                         (10, 7, 'Rally', 'Shared note'))
        self.assertEqual((q.Position, q.Color, q.Icon, q.TtlSeconds),
                         ([100., 0., 200.], 123, 4, 0))
        self.assertEqual(self.e['mHCExpires'], 1010)

    def test_clock_skew_cannot_change_update_ttl(self):
        for local_utc in (900, 1005, 1011):
            self.e['HCGroupClock'] = NS(Utc=lambda: local_utc)
            menu_method('SaveMarker', self.e)(self.client)
        self.assertEqual(len(self.sent), 3)
        self.assertEqual([q.TtlSeconds for q in self.sent], [0, 0, 0])
        self.assertEqual(self.e['mHCExpires'], 1010)

    def test_unplaced_marker_cannot_send(self):
        self.e['mHCHasPoint'] = False
        menu_method('SaveMarker', self.e)(self.client)
        self.assertEqual(self.sent, [])

    def test_create_and_note_boundary_use_server_limits(self):
        self.e.update(mHCMarkerId=0, mHCExpires=0,
                      mHCNote=NS(GetText=lambda: 'n'*512))
        menu_method('SaveMarker', self.e)(self.client)
        self.assertEqual((self.sent[0].Op, self.sent[0].EntityId), (9, 0))
        self.e['mHCNote'] = NS(GetText=lambda: 'n'*513)
        menu_method('SaveMarker', self.e)(self.client)
        self.assertEqual(len(self.sent), 1)

    def test_native_selection_edits_only_valid_marker_rows(self):
        widget = object()
        marker = NS(Id=7)
        edited = []
        self.e.update(mHCMarkers=widget, mHCMarkerRows=EArray([marker]), mHCMarkerId=0,
                      EditMarker=edited.append)
        select = menu_method('OnItemSelected', self.e)
        self.assertTrue(select(widget, 0, 0, 0, 0, -1, -1))
        self.assertEqual(edited, [marker])
        self.assertTrue(select(widget, 0, 0, 1, 0, 0, 0))
        self.assertTrue(select(widget, 0, 0, -1, 0, 0, 0))
        self.assertEqual(edited, [marker])

    def test_layout_bindings_and_rebindable_gameplay_seam(self):
        menu = (ROOT/'scripts/5_Mission/Groups/HCGroupMapMenu.c').read_text()
        layout = (ROOT/'gui/layouts/hc_group_map.layout').read_text()
        names = set(re.findall(r'\w+WidgetClass\s+(\w+)\s*\{', layout))
        bindings = set(re.findall(r'FindAnyWidget\("(\w+)"\)', menu))
        self.assertTrue(bindings <= names)
        gameplay = (ROOT/'scripts/5_Mission/Groups/HCGroupGameplay.c').read_text()
        self.assertIn('UAMapToggle', gameplay)
        self.assertIn('IsControlDisabled()', gameplay)
        self.assertNotIn('KeyCode.KC_M', gameplay)


class GroupUIDraftTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT/'scripts/5_Mission/Groups/HCGroupMapMenu.c').read_text()
        self.env = translated_rules()
        self.env.update(GetFocus=lambda: None, vector=NS(Zero=[0,0,0]),
            HCGroupWorldIcons=NS(RoleLabel=lambda role:'Member'))
        f = self.env['HCGroupSnapshot']()
        f.GroupId, f.Revision, f.Session, f.Name = 1, 1, 'live', 'Team'
        f.Enabled = True
        marker = self.env['HCGroupMarker']()
        marker.Id, marker.Name, marker.Note = 7, 'Rally', 'Original'
        f.Markers.Insert(marker)
        f.Members = EArray([NS(Id='a', Name='A',Role=2), NS(Id='b', Name='B',Role=0)])
        f.Candidates = EArray([NS(Id='c', Name='C'), NS(Id='d', Name='D')])
        f.Invitations = EArray([NS(Id=11, GroupName='X'), NS(Id=12, GroupName='Y')])
        self.state = NS(mHCBound=f, mHCMarkerId=7, mHCOriginal=marker,
            mHCMarkerRows=EArray([marker]), mHCName=SyntheticEdit('Draft'),
            mHCNote=SyntheticEdit('Unsaved note'), mHCGroupName=SyntheticEdit('Team'),
            mHCPoint=[100,0,200], mHCHasPoint=True, mHCColor=-1, mHCIcon=0,
            mHCExpires=0, mHCConflict=False, mHCMessage='', mHCRefreshing=False)
        for name in ('mHCMarkers','mHCMembers','mHCCandidates','mHCInvites'):
            widget = SyntheticList()
            widget.selected = 0 if name == 'mHCMarkers' else 1
            setattr(self.state, name, widget)
        for method in re.findall(r'\b(?:bool|int|void|string) (\w+)\(', self.source):
            setattr(self.state, method, lambda *a, m=method:
                ui_member(self.source,m,self.state,self.env,*a))
        self.frame = copy.deepcopy(f)
        self.frame.Revision = 2
        self.frame.Members.reverse()
        self.frame.Candidates.reverse()
        self.frame.Invitations.reverse()

    def test_unrelated_revision_preserves_unsaved_note(self):
        self.state.RebuildLists(self.frame)
        self.assertEqual(self.state.mHCNote.GetText(), 'Unsaved note')
        self.assertEqual(self.state.mHCMarkerId, 7)
        self.assertFalse(self.state.mHCConflict)

    def test_roster_selections_follow_ids_after_reorder(self):
        self.state.RebuildLists(self.frame)
        for name in ('mHCMembers','mHCCandidates','mHCInvites'):
            self.assertEqual(getattr(self.state,name).GetSelectedRow(), 0)

    def test_changed_or_deleted_marker_keeps_draft_and_reports_conflict(self):
        for deleted in (False, True):
            self.setUp()
            if deleted: self.frame.Markers.Clear()
            else: self.frame.Markers.Get(0).Note = 'Remote edit'
            self.state.RebuildLists(self.frame)
            self.assertEqual(self.state.mHCNote.GetText(), 'Unsaved note')
            self.assertTrue(self.state.mHCConflict)
            self.assertTrue(self.state.mHCMessage)

    def test_conflicted_update_never_sends(self):
        self.state.mHCConflict = True
        sent = []
        self.state.SaveMarker(NS(Send=sent.append))
        self.assertEqual(sent, [])

    def test_doubleclick_current_list_entry_explicitly_reloads(self):
        self.state.mHCConflict = True
        self.state.mHCMap = object()
        self.env['super'] = NS(OnDoubleClick=lambda *a: False)
        self.assertTrue(self.state.OnDoubleClick(self.state.mHCMarkers,0,0,0))
        self.assertEqual(self.state.mHCNote.GetText(), 'Original')
        self.assertFalse(self.state.mHCConflict)

    def test_conflict_notice_survives_regular_status_updates(self):
        self.state.mHCMessage = 'Conflict remains'
        self.state.mHCStatus = SyntheticEdit('')
        self.state.mHCMap = object()
        self.state.mHCOpening = True
        self.state.mHCRenderTime = 0
        client = NS(GetSnapshot=lambda: self.state.mHCBound,
                    GetNotice=lambda: 'Idle')
        viewer = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        self.env.update(super=NS(Update=lambda *a: None),
            HCGroupClient=NS(Get=lambda: client),
            PlayerBase=NS(Cast=lambda p:p),
            GetGame=lambda: NS(GetPlayer=lambda: viewer))
        self.state.Update(0)
        self.assertEqual(self.state.mHCStatus.GetText(), 'Conflict remains')


class GroupUIRenderTests(unittest.TestCase):
    def test_unconscious_viewer_clears_world_icons(self):
        source = (ROOT/'scripts/5_Mission/Groups/HCGroupWorldIcons.c').read_text()
        events = []
        viewer = NS(IsAlive=lambda: True, IsUnconscious=lambda: True,
                    GetIdentity=lambda: NS(GetId=lambda:'self'))
        game = NS(GetPlayer=lambda:viewer,
            GetUIManager=lambda:NS(GetMenu=lambda:None),
            GetCurrentCameraPosition=lambda:[0,0,0],
            GetCurrentCameraDirection=lambda:[0,0,1])
        frame = NS(Enabled=True, GroupId=1, Epoch=1,
                   Settings=NS(WorldIcons=True), Members=EArray())
        state = NS(mHCGroup=1, mHCEpoch=1,
            Clear=lambda:events.append('clear'),
            HideUnused=lambda n:events.append('hide'))
        ui_member(source,'Update',state,
            {'GetGame':lambda:game,'PlayerBase':NS(Cast=lambda p:p)},frame)
        self.assertEqual(events, ['clear'])

    def test_marker_icon_uses_native_mapping_and_rejects_invalid_id(self):
        source = (ROOT/'scripts/5_Mission/Groups/HCGroupWorldIcons.c').read_text()
        calls = []
        widget = NS(ClearUserMarks=lambda:None,
                    AddUserMark=lambda *a:calls.append(a))
        marker = NS(Icon=19, ExpiresUtc=0, Name='Rally',
                    Position=[0,0,0], Color=123)
        frame = NS(Enabled=True, GroupId=1, Markers=EArray([marker]),
                   Settings=NS(MapIcons=False))
        env = {'HCGroupClock':NS(Utc=lambda:1000),
               'MapMarkerTypes':NS(GetMarkerTypeFromID=lambda i:'native-'+str(i)),
               'eMapMarkerTypes':NS(MARKERTYPE_MAX=20)}
        ui_member(source,'DrawMap',NS(),env,widget,frame)
        self.assertEqual(calls[0][-1], 'native-19')
        marker.Icon = 20
        ui_member(source,'DrawMap',NS(),env,widget,frame)
        self.assertEqual(len(calls), 1)
