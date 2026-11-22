"""Synthetic fixtures only: tiny generated boxes written with our MLOD writer and the
test ODOL56 byte writer. No game assets are read."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.assets import mlod
from tools.validate import p3d_firegeom_audit as audit
from tests import test_odol56 as odol_fixture

FIRE, VIEW = mlod.FIRE_GEOMETRY, mlod.VIEW_GEOMETRY
CUBE_FACES = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))


def box_points(low, high):
    (x0, y0, z0), (x1, y1, z1) = low, high
    return [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
            (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]


def box_lod(low=(0., 0., 0.), high=(1., 1., 1.), selections=None, collinear=False):
    points = box_points(low, high)
    faces = [mlod.Face(tuple(f), ((0., 0.), (1., 0.), (1., 1.), (0., 1.)), normals=((0., 1., 0.),) * 4)
             for f in CUBE_FACES]
    if collinear:      # one extra triangle along an edge: three distinct but collinear points
        points.append((low[0] + (high[0] - low[0]) / 2, low[1], low[2]))
        faces.append(mlod.Face((0, 8, 1), ((0., 0.), (.5, 0.), (1., 0.)), normals=((0., 1., 0.),) * 3))
    return mlod.LOD(vertices=tuple(mlod.Vertex(p) for p in points), faces=tuple(faces),
                    selections=selections or {})


def component(name='Component01'):
    return {name: mlod.Selection(faces=tuple(range(6)))}


def mlod_bytes(**lods):
    table = {'fire': FIRE, 'view': VIEW}
    return mlod.write_mlod(mlod.Asset({table[k]: v for k, v in lods.items() if v is not None}, physical=False))


def ids(findings, severity=None):
    return sorted(f['id'] for f in findings if severity in (None, f['severity']))


class ModelAuditTests(unittest.TestCase):
    def audit(self, data, **kwargs):
        return audit.audit_model(audit.load_model(data), **kwargs)

    def test_clean_model_has_no_findings(self):
        data = mlod_bytes(fire=box_lod(selections=component()), view=box_lod())
        self.assertEqual(self.audit(data), [])

    def test_missing_lods(self):
        self.assertEqual(ids(self.audit(mlod_bytes(fire=None, view=box_lod()))), ['FG001'])
        self.assertEqual(ids(self.audit(mlod_bytes(fire=box_lod(selections=component()), view=None))), ['FG002'])
        both = self.audit(mlod.write_mlod(mlod.Asset({0.: box_lod()}, physical=False)))
        self.assertEqual(ids(both), ['FG001', 'FG002'])

    def test_degenerate_lods(self):
        empty = mlod.LOD(vertices=box_lod().vertices)
        self.assertIn('FG010', ids(self.audit(mlod_bytes(fire=empty, view=box_lod()))))
        flat = box_lod(low=(0., 0., 0.), high=(1., 0., 1.), selections=component())
        self.assertIn('FG014', ids(self.audit(mlod_bytes(fire=box_lod(selections=component()), view=flat))))
        zero_area = box_lod(low=(0., 0., 0.), high=(0., 0., 0.), selections=component())
        self.assertIn('FG012', ids(self.audit(mlod_bytes(fire=zero_area, view=box_lod()))))

    def test_some_zero_area_faces_warn_only(self):
        lod = box_lod(selections=component(), collinear=True)
        findings = self.audit(mlod_bytes(fire=lod, view=box_lod()))
        self.assertEqual(ids(findings), ['FG013'])
        self.assertEqual(ids(findings, 'error'), [])

    def test_component_checks(self):
        self.assertEqual(ids(self.audit(mlod_bytes(fire=box_lod(), view=box_lod()))), ['FG020'])
        empty = {'Component01': mlod.Selection()}
        self.assertIn('FG022', ids(self.audit(mlod_bytes(fire=box_lod(selections=empty), view=box_lod()))))
        flat_points = {'Component01': mlod.Selection(vertices=(0, 1, 2, 3))}   # the bottom quad only
        self.assertIn('FG023', ids(self.audit(mlod_bytes(fire=box_lod(selections=flat_points), view=box_lod()))))

    def test_hit_components_versus_damage_zones(self):
        selections = {**component(), 'Head': mlod.Selection(faces=(0, 1)), 'Torso': mlod.Selection(faces=(2, 3))}
        data = mlod_bytes(fire=box_lod(selections=selections), view=box_lod())
        self.assertEqual(self.audit(data, zones=None), [])
        self.assertEqual(ids(self.audit(data, zones=[{'head', 'torso'}])), [])
        findings = self.audit(data, zones=[{'head', 'leg'}])
        self.assertEqual(ids(findings), ['FG030', 'FG031'])
        self.assertEqual(ids(findings, 'error'), ['FG030'])
        self.assertEqual(ids(self.audit(data, zones=[])), ['FG032'])
        # a model with only ComponentNN selections needs no DamageZones
        self.assertEqual(self.audit(mlod_bytes(fire=box_lod(selections=component()), view=box_lod()), zones=[]), [])

    def test_unknown_magic_and_garbage_are_refused(self):
        for data in (b'', b'XXXXzzzz', b'MLOD' + b'\0' * 8, b'ODOL' + b'\0' * 12):
            with self.assertRaises(audit.AuditRefusal):
                audit.load_model(data)


class OdolPathTests(unittest.TestCase):
    def spec(self, resolution, selections=()):
        return odol_fixture.Spec(
            resolution=resolution,
            vertices=[(0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)],
            faces=[[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]],
            selections=selections, bbox=((0., 0., 0.), (1., 1., 1.), (.5, .5, .5), 1.0))

    def test_odol_models_are_decoded_and_audited(self):
        fire = self.spec(7e15, [('Component01', [0, 1, 2, 3], [], [], False), ('Head', [0], [], [], False)])
        view = self.spec(6e15)
        model = audit.load_model(odol_fixture.model_bytes([self.spec(1.0), view, fire]))
        self.assertEqual(audit.audit_model(model, zones=[{'head'}]), [])
        self.assertEqual(ids(audit.audit_model(model, zones=[{'neck'}])), ['FG030', 'FG031'])
        missing = audit.load_model(odol_fixture.model_bytes([self.spec(1.0), view]))
        self.assertEqual(ids(audit.audit_model(missing)), ['FG001'])

    def test_unreadable_fire_lod_is_reported_not_missing(self):
        view = audit.ModelView(lods=[audit.LodView(6e15, [(0., 0., 0.), (1., 0., 0.), (0., 1., 1.)], [(0, 1, 2)])],
                               failed=[7e15])
        self.assertEqual(ids(audit.audit_model(view)), ['FG003'])


class ScanTests(unittest.TestCase):
    CONFIG = '''class CfgVehicles { class HC_Crate { model = "HollowCountryAssets\\crate\\crate.p3d";
    class DamageSystem { class DamageZones { class Lid { componentNames[] = {"lid"}; }; }; }; };
    class HC_Other { model = "HollowCountryAssets\\crate\\other.p3d"; }; };'''

    def tree(self, config=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        pack = base / 'mods' / 'HollowCountryAssets'
        (pack / 'crate').mkdir(parents=True)
        (pack / '$PBOPREFIX$').write_text('HollowCountryAssets\n')
        (pack / 'config.cpp').write_text(self.CONFIG if config is None else config)
        good = {**component(), 'Lid': mlod.Selection(faces=(0, 1))}
        (pack / 'crate' / 'crate.p3d').write_bytes(mlod_bytes(fire=box_lod(selections=good), view=box_lod()))
        (pack / 'crate' / 'other.p3d').write_bytes(mlod_bytes(fire=box_lod(selections=component()), view=None))
        return base

    def test_scan_matches_models_to_config_classes(self):
        base = self.tree()
        report = audit.audit_paths(['mods'], base=base)
        self.assertEqual(report['models'], 2)
        self.assertFalse(report['valid'])
        self.assertEqual([(f['id'], f['model']) for f in report['findings']],
                         [('FG002', 'mods/HollowCountryAssets/crate/other.p3d')])
        self.assertTrue(any('has no own DamageZones' in n for n in report['notes']))
        self.assertFalse(report['engine_verified'])

    def test_zone_name_mismatch_is_an_error(self):
        base = self.tree(self.CONFIG.replace('"lid"', '"hatch"'))
        findings = audit.audit_paths(['mods'], base=base)['findings']
        self.assertEqual(sorted(f['id'] for f in findings), ['FG002', 'FG030', 'FG031'])

    def test_unparseable_config_warns_and_skips_the_cross_check(self):
        base = self.tree('#define X 1\nclass A { b = X + 1; };')
        findings = audit.audit_paths(['mods'], base=base)['findings']
        self.assertEqual(sorted(f['id'] for f in findings), ['FG002', 'FG040'])

    def test_unreadable_model_is_an_error(self):
        base = self.tree()
        (base / 'mods' / 'HollowCountryAssets' / 'crate' / 'bad.p3d').write_bytes(b'junk')
        findings = audit.audit_paths(['mods'], base=base)['findings']
        self.assertIn(('FG003', 'mods/HollowCountryAssets/crate/bad.p3d'), [(f['id'], f['model']) for f in findings])

    def test_empty_tree_is_reported_not_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'mods').mkdir()
            report = audit.audit_paths(['mods'], base=temp)
            self.assertEqual((report['valid'], report['models']), (True, 0))
            self.assertIn('nothing to audit', report['notes'][0])

    def test_roots_outside_the_repository_are_refused(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as other:
            (Path(temp) / 'mods').mkdir()
            for root in (other, 'absent', '.', '../x'):
                with self.assertRaises(audit.AuditRefusal):
                    audit.audit_paths([root], base=temp)
            link = Path(temp) / 'mods' / 'link'
            link.symlink_to(other)
            with self.assertRaises(audit.AuditRefusal):
                audit.audit_paths(['mods/link'], base=temp)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = audit.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_cli_exit_codes_and_no_absolute_paths(self):
        code, result = self.run_main('--root', '/definitely/not/in/repo')
        self.assertEqual((code, result['valid']), (2, False))
        code, result = self.run_main()
        self.assertEqual((code, result['valid']), (0, True))
        self.assertNotIn(str(audit.ROOT), json.dumps(result))


if __name__ == '__main__':
    unittest.main()
