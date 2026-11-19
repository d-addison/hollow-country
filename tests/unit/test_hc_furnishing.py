"""HC-56 tools/package/interior_themes through HC-24's pack; all geometry/IO here is synthetic.

Trace: Wave 7 #182 / #171; native placement and production admission stay pending.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import interior_templates as tpl, interiors_profile as ip
from tests.unit import test_interior_templates as f
from tests.unit.test_interior_templates_runtime import fixture


class FurnishingPackTests(unittest.TestCase):
    def test_themes_reach_runtime_only_as_measured_pack_slots_with_named_refusals(self):
        authored = tpl.authored_inputs()
        # Synthetic class binding uses the existing surveyed-fixture geometry.
        home = json.loads(authored['home-layouts.json'])
        home['Layouts'] = [home['Layouts'][0]]
        home['Layouts'][0]['BuildingClass'] = f.HOUSE
        authored = {'home-layouts.json': tpl._dump(home)}
        raw = f.encode(f.census(f.house_rows() + f.calibration_rows(), f.CLASSES))
        with mock.patch.object(tpl, 'authored_inputs', return_value=authored):
            refused = ip.templates_build([raw], f.PROTO, f.POS, f.TYPES)
            self.assertIn('authored', refused.summary, 'profile builder did not consume HC-56 themes')
            self.assertEqual('unmeasured', f.class_rows(refused)[f.HOUSE]['Furniture'])
            self.assertEqual('missing_prop_measurements', refused.summary['authored']['layouts'][0]['Reason'])
            self.assertEqual([], f.furnish_rows(refused))
            self.assertEqual(len(set(f.CLASSES) - {f.HOUSE}), refused.summary['authored']['queued_classes'])
            boxes = tpl.ingest_boxes(b'SYNTHETIC ONLY\n' + b''.join(
                ('[HC Interiors] prop box type=%s min=<-0.1 0 -0.1> max=<0.1 0.3 0.1>\n' % kind).encode()
                for kind in home['Layouts'][0]['PropClasses']))
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                boxfile = root / 'synthetic-boxes.json'
                boxfile.write_bytes(tpl._dump(boxes))
                with mock.patch.object(tpl, 'BOXES_PATH', boxfile):
                    built = ip.templates_build([raw], f.PROTO, f.POS, f.TYPES)
                self.assertEqual('covered', f.class_rows(built)[f.HOUSE]['Furniture'])
                self.assertEqual(2 * len(f.furnish_rows(built)), built.summary['authored']['props'])
                built.manifest['Sources'].update(cfgspawnabletypes='a'*64, cfglimitsdefinition='a'*64)
                tpl._write(root / 'build', built)
                from tools.package import search_context as sc
                chunks, report = sc.build_search_groups(f.PROTO, f.TYPES)
                sc.write_pack(root / 'groups', chunks, report)
                ip.templates_assemble(root / 'build', root / 'pack', root / 'groups')
                # Round-trip the existing PBO payload path: raw authoring themes
                # never become loose server files or runtime DTOs.
                from tools.package import pbo
                payload = {'data/defaults/templates/' + p.name: p.read_bytes()
                           for p in (root / 'pack/templates').iterdir()}
                self.assertTrue(all(pbo.original_addon_name(name) for name in payload))
                _, shipped = pbo.parse(pbo.pack(payload))
                values = {name.rsplit('/', 1)[-1]: json.loads(data) for name, data in shipped.items()}
                env, _, reads, logs = fixture(values, staged=True)[:4]
                env['HCProfileDefaults'].Resolve = lambda relative, default_root:default_root+relative
                env['EngineHouse'] = lambda cls: True
                env['EnsureLoaded'](None)
                from tests.unit.test_hc_template_pack import SyntheticBudget
                for _ in range(100):
                    if env['HCLoadFinished'](): break
                    env['HCLoadStep'](None, SyntheticBudget(True))
                self.assertTrue(env['Loaded'](), logs)
                self.assertEqual('pbo', env['PackSource']())
                self.assertTrue(all(path.startswith('HollowCountry/data/defaults/templates/') for path in reads))
                loaded = env['Template'](f.HOUSE)
                self.assertEqual(set(home['Layouts'][0]['PropClasses']), {p.Type for p in loaded.PropSlots})
                self.assertEqual(len(f.furnish_rows(built)), len(env['FurnishRows']()))
                self.assertTrue(any('load_ticks=' in line and 'load_ms=' in line for line in logs if 'HC-24 pack_chunks=' in line))


if __name__ == '__main__':
    unittest.main()
