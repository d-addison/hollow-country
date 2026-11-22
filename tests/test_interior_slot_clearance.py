"""Synthetic models only: the generator's slot rules must agree with the world mesh audit verdict by verdict."""
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tests.test_world_mesh_audit import Installed, cube, lod, model, prop
from tools.audit import interior_slot_clearance as clearance, world_mesh_audit as audit
from tools.package import interior_templates as tpl

REASONS = {'HOST_GEOMETRY_ENCROACHMENT': 'host_geometry', 'DOOR_APRON_INTERSECTION': 'door_apron',
           'STAIR_PATH_INTERSECTION': 'stair_path', 'PATH_LOD_INTERSECTION': 'path_lod',
           'PIECE_GEOMETRY_INTERSECTION': 'piece_geometry'}
HOST = 'House'
KIND = 'P'


def host_model():
    """A wall block, a door leaf on the plane z=-3 and a Paths LOD corridor along z at x=5."""
    wall = list(audit.corners(((-6, 0, -1), (-5.5, 2, 1))))
    leaf = [(-.5, 0, -3), (.5, 0, -3), (.5, 2, -3), (-.5, 2, -3)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3), (8, 9, 10, 11)]
    door = NS(name='door1', vertices=[8, 9, 10, 11], faces=[6])
    return model(lod(audit.GEOMETRY, wall + leaf, faces, [door]),
                 lod(audit.PATHS, [(5, 0, -2), (5, 0, 2)], [(0, 1)]))


class SlotClearanceTests(unittest.TestCase):
    def setUp(self):
        self.installed = Installed({KIND: prop(), HOST: host_model()})
        self.rules = clearance.HostClearance(self.installed)

    def audit_reasons(self, position, placed=()):
        rows = [audit.Placement('t', 'other%d' % i, s['Type'], tuple(s['Position']), tuple(s['Orientation']), host=HOST)
                for i, s in enumerate(placed)]
        rows.append(audit.Placement('t', 'candidate', KIND, tuple(position), (0, 0, 0), host=HOST))
        result = audit.audit(rows, self.installed)
        return {REASONS[f['reason']] for f in result['findings'] if f['reason'] in REASONS}

    def cases(self):
        other = {'Type': KIND, 'Position': [8, 0, 8], 'Orientation': [0, 0, 0]}
        return [('open floor', (8, 0, 3), []), ('on the path', (5, 0, 0), []),
                ('through the wall face', (-5.5, 0, 0), []), ('in the door apron', (0, 0, -3.9), []),
                ('on another slot', (8.1, 0, 8), [other]), ('beside another slot', (9, 0, 8), [other])]

    def test_every_verdict_is_the_audit_verdict(self):
        seen = set()
        for label, position, placed in self.cases():
            reasons = self.audit_reasons(position, placed)
            before = dict(self.rules.refusals)
            verdict = self.rules.clear(HOST, KIND, position, 0, placed)
            self.assertEqual(not reasons, verdict, label)
            if reasons:
                grown = {k for k, v in self.rules.refusals.items() if v != before.get(k, 0)}
                self.assertEqual(1, len(grown), label)
                self.assertTrue(grown <= reasons, (label, grown, reasons))
                seen |= grown
        # The fixture exercises every rule family it claims to, so a lost rule fails here.
        self.assertEqual({'host_geometry', 'door_apron', 'path_lod', 'piece_geometry'}, seen)

    def test_a_stair_segment_is_refused_as_a_stair(self):
        rise = audit.POLICY['stair_min_slope'] * 3 * 2
        stair = model(cube((20, 0, 20), (21, 1, 21)), lod(audit.PATHS, [(3, 0, 0), (3, rise, 3)], [(0, 1)]))
        rules = clearance.HostClearance(Installed({KIND: prop(), HOST: stair}))
        self.assertFalse(rules.clear(HOST, KIND, (3, rise / 2, 1.5), 0, []))
        self.assertEqual({'stair_path': 1}, rules.refusals)
        self.assertTrue(rules.clear(HOST, KIND, (8, 0, 8), 0, []))

    def test_yaw_is_judged_like_the_audit_row_orientation(self):
        long = Installed({KIND: prop(cube((-1.5, 0, -.1), (1.5, .4, .1))), HOST: host_model()})
        rules = clearance.HostClearance(long)
        # A long prop clears the corridor along z at x=5 only when rotated away from it.
        position = (3.2, 0, 0)
        verdicts = {}
        for yaw in (0, 90):
            row = audit.Placement('t', 'c', KIND, position, (yaw, 0, 0), host=HOST)
            result = audit.audit([row], long)
            audited = any(f['reason'] in REASONS for f in result['findings'])
            verdicts[yaw] = rules.clear(HOST, KIND, position, yaw, [])
            self.assertEqual(not audited, verdicts[yaw])
        self.assertNotEqual(verdicts[0], verdicts[90])

    def test_unavailable_models_are_refused_loudly_not_skipped(self):
        with self.assertRaises(tpl.TemplateError):
            clearance.HostClearance(Installed({HOST: host_model()})).clear(HOST, KIND, (8, 0, 3), 0, [])
        with self.assertRaises(tpl.TemplateError):
            clearance.HostClearance(Installed({KIND: prop()})).clear(HOST, KIND, (8, 0, 3), 0, [])
        with self.assertRaises(tpl.TemplateError):
            clearance.HostClearance(Installed({KIND: prop(), HOST: model(lod(audit.PATHS))})).clear(
                HOST, KIND, (8, 0, 3), 0, [])

    def test_pin_follows_the_audit_policy(self):
        pin = self.rules.pin()
        self.assertEqual(pin, clearance.HostClearance(self.installed).pin())
        with patch.dict(audit.POLICY, {'door_radius_m': audit.POLICY['door_radius_m'] + .1}):
            self.assertNotEqual(pin, self.rules.pin())

    def test_factory_refuses_missing_addons(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(tpl.TemplateError):
                clearance.factory(NS(addons=Path(folder)))

    def test_entry_point_hands_the_rules_to_the_generator(self):
        with patch.object(tpl, 'main', return_value=0) as main:
            self.assertEqual(0, clearance.main(['build']))
        self.assertIs(clearance.factory, main.call_args.kwargs['clearance_factory'])


if __name__ == '__main__':
    unittest.main()
