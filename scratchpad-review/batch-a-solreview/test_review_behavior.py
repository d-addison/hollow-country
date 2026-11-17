"""Review-only synthetic authored placement execution; never a DayZ emulator.

Out Object uses an explicit cell; empty allocated arrays are non-null. The
fixtures use zero yaw, no searchable props, and successful catalog/store calls.
No collision, navigation, native deletion semantics, or timing is established.
"""
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace as NS
import unittest

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('REVIEW_ROOT', HERE.parents[1]))
sys.path.insert(0, str(ROOT / 'tests/unit'))
import test_native_wiring_batch_a as batch


class Array(batch.Array):
    def Clear(self): self.clear()


def tokens(text):
    current, quoted, escaped = '', False, False
    for ch in text:
        if ch == '"' and not escaped:
            quoted = not quoted
        if not quoted and ch in '{};':
            if current.strip(): yield current.strip()
            yield ch
            current = ''
        else:
            current += ch
        escaped = ch == '\\' and not escaped
    if current.strip(): yield current.strip()


def placement(scope):
    """Translate exact authored PlaceCandidate with explicit out-cell adaptation."""
    _, body = batch.method_body(batch.class_body(batch.MODULE, 'HCInteriorsModule'), 'PlaceCandidate')
    body = body.replace('Object reusable;', 'Object reusable = NS(value=null);')
    body = body.replace('reusableProps.Insert(reusable)', 'reusableProps.Insert(reusable.value)')
    body = re.sub(r'(?m)^(\s*)if \((.*)\) ([^\n{}]*;)\s*$', r'\1if (\2) {\3}', body)
    body = re.sub(r'(?m)^(\s*)foreach \(([^\n]+)\) ([^\n{}]*;)\s*$', r'\1foreach (\2) {\3}', body)
    body = re.sub(r'new array<[^>]+>', 'Array()', body)
    body = re.sub(r'new HCInteriorSite', 'NS()', body)
    body = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', body)
    lines, indent = ['def run(self, index):'], 1
    for token in tokens(body):
        if token == ';': continue
        if token == '{': indent += 1; continue
        if token == '}': indent -= 1; continue
        token = re.sub(r'^foreach \(\w+ (\w+) : (.*)\)$', r'for \1 in \2:', token)
        decl = re.match(r'^(int|vector|Object|array<[^>]+>|HC\w+) (\w+)(.*)$', token, re.S)
        if decl:
            typ, name, rest = decl.groups()
            token = name + rest if rest.strip() else name + (' = 0' if typ == 'int' else ' = None')
        token = re.sub(r'\b(m_\w+)\b', r'self.\1', token)
        for method in ('ResolveBuilding', 'InspectProp', 'FindSite'):
            token = re.sub(r'(?<![.\w])' + method + r'\(', 'self.' + method + '(', token)
        token = token.replace('&&', ' and ').replace('||', ' or ')
        token = re.sub(r'!(?!=)', 'not ', token)
        for old, new in (('true', 'True'), ('false', 'False'), ('null', 'None')):
            token = re.sub(r'\b' + old + r'\b', new, token)
        if token.endswith('++'): token = token[:-2] + ' += 1'
        if token.startswith('if ('): token = 'if ' + token[4:-1] + ':'
        elif token == 'else': token = 'else:'
        lines.append('    ' * indent + token)
    translated = '\n'.join(lines)
    exec(compile(translated, 'HCInteriorModule.PlaceCandidate [synthetic]', 'exec'), scope)
    return scope['run']


class Prop:
    def __init__(self, name, events):
        self.name, self.events, self.valid = name, events, True
    def __bool__(self): return self.valid
    def SetOrientation(self, orientation): self.events.append(('orient', self.name))
    def GetPosition(self):
        assert self.valid, 'Synthetic deleted prop must not be read'
        return [0, 0, 0]


def fixture(reused=0, failure=None):
    events, logs, held = [], [], []
    owned = Array()
    existing = [Prop('reuse' + str(i), events) for i in range(reused)]
    owned.extend(existing)
    calls = batch.FakeQueue()
    props = Array(NS(Type='SyntheticProp', Position=[0, 0, 0], Orientation=[0, 0, 0], Searchable=False)
                  for _ in range(2))
    layout = NS(Id='fixture', History='fixture', Props=props)
    candidate = NS(SlotId=0, Position=[0, 0, 0], Orientation=[0, 0, 0])
    assignment = NS(LayoutId='fixture', History='fixture', MeasuredRecordSha256='')
    building = NS(GetOrientation=lambda: [0, 0, 0], ModelToWorld=lambda pos: pos)
    state = NS(inspected=0, attempted=0)
    def create(*args):
        state.attempted += 1
        if state.attempted == failure: return None
        prop = Prop('new' + str(state.attempted), events)
        events.append(('create', prop.name))
        return prop
    def inspect(point, orientation, typ, cell):
        i = state.inspected
        state.inspected += 1
        cell.value = existing[i] if i < len(existing) else None
        return 1 if cell.value else 0
    def delete(prop):
        events.append(('delete', prop.name))
        prop.valid = False
    def update(prop):
        # Explicit model of inspected Game.c:1295 guard, NOT engine behavior.
        if prop:
            prop.GetPosition()
            events.append(('update', prop.name))
    game = NS(CreateObjectEx=create, ObjectDelete=delete, IsServer=lambda: True,
              GetCallQueue=lambda category: calls, UpdatePathgraphRegionByObject=update)
    schedule_scope = dict(GetGame=lambda: game, Math=NS(Min=min), CALL_CATEGORY_SYSTEM=0,
                          Print=logs.append)
    batch.translate(batch.PATHGRAPH, 'HCInteriorPathgraph', schedule_scope, ['Schedule'])
    schedule = schedule_scope['Schedule']
    def record_schedule(created):
        events.append(('schedule', tuple(p.name for p in created), tuple(p.name for p in owned)))
        return schedule(created)
    context = NS(m_Store=NS(Healthy=lambda: True, IsHeld=lambda slot: False,
                           HoldSlot=lambda slot, why: held.append(why)),
                 m_Config=NS(Candidates=[candidate], Seed=1, DiagnosticPlacementTrial=True),
                 m_Manifest=NS(Assignments=[assignment]), m_Objects=owned, m_Sites=Array(),
                 ResolveBuilding=lambda obj: building, InspectProp=inspect, FindSite=lambda obj: None)
    scope = dict(NS=NS, Array=Array, GetGame=lambda: game, Print=logs.append,
                 HCInteriorRules=NS(Layout=lambda *args: 0, Quantize=lambda x: x, Yaw=lambda x: x),
                 HCInteriorCatalog=NS(GetFor=lambda *args: layout),
                 HCInteriorMeasuredCatalog=NS(MeasuredDigest=lambda obj: ''),
                 HCInteriorPathgraph=NS(Schedule=record_schedule))
    for flag in ('ECE_SETUP', 'ECE_KEEPHEIGHT', 'ECE_CREATEPHYSICS', 'ECE_UPDATEPATHGRAPH',
                 'ECE_NOLIFETIME', 'ECE_DYNAMIC_PERSISTENCY', 'RF_IGNORE'):
        scope[flag] = 1
    return placement(scope), context, calls, events, held, delete, schedule


class PlacementIntegration(unittest.TestCase):
    def test_success_queues_new_props_after_orientation_and_ownership(self):
        run, ctx, calls, events, held, _, _ = fixture()
        run(ctx, 0)
        self.assertEqual(2, len(calls.calls))
        self.assertEqual(('schedule', ('new1', 'new2'), ('new1', 'new2')), events[-1])
        self.assertEqual([('orient', 'new1'), ('orient', 'new2')], [e for e in events if e[0] == 'orient'])
        self.assertEqual([], held)

    def test_partial_failure_deletes_only_new_props_and_never_schedules(self):
        run, ctx, calls, events, held, _, _ = fixture(failure=2)
        run(ctx, 0)
        self.assertEqual([], calls.calls)
        self.assertEqual([], ctx.m_Objects)
        self.assertEqual(['partial-placement'], held)
        self.assertEqual([('delete', 'new1')], [e for e in events if e[0] == 'delete'])
        self.assertFalse(any(e[0] == 'schedule' for e in events))

    def test_reused_props_are_neither_requeued_nor_duplicated_in_ownership(self):
        run, ctx, calls, events, held, _, _ = fixture(reused=1)
        run(ctx, 0)
        self.assertEqual(1, len(calls.calls))
        self.assertEqual(['reuse0', 'new1'], [p.name for p in ctx.m_Objects])
        self.assertEqual('new1', calls.calls[0][3][0].name)

    def test_deleted_before_callback_uses_the_inspected_native_null_guard_model(self):
        run, ctx, calls, events, _, delete, _ = fixture()
        run(ctx, 0)
        for prop in ctx.m_Objects: delete(prop)
        ctx.m_Objects.Clear()  # Explicit synthetic OnStop deletion/clear sequence.
        for callback, delay, repeat, params in calls.calls:
            self.assertEqual((100, False), (delay, repeat))
            callback(*params)
        self.assertFalse(any(e[0] == 'update' for e in events))


if __name__ == '__main__': unittest.main()
