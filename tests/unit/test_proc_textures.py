"""Original map generation and sealed admission only; no native converters."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.assets.blender_runner import BlenderRefusal
from tools.assets import licence_gate, pbr_pack, proc_textures, provenance


class ProceduralTexturesTests(unittest.TestCase):
    def test_seeded_maps_scalar_channels_and_layout(self):
        for material in proc_textures.MATERIALS:
            first = proc_textures.generate(material, size=8)
            self.assertEqual(first, proc_textures.generate(material, size=8))
            self.assertEqual(set(first), pbr_pack.MAPS)
            for key in ['roughness', 'metallic', 'ao']:
                data = first[key].rgba
                self.assertTrue(all(data[i] == data[i+1] == data[i+2] for i in range(0, len(data), 4)))
            pbr_pack.pack_pixels(first)
        self.assertNotEqual(proc_textures.generate('tin', size=8), proc_textures.generate('tin', size=8, seed=1))

    def test_refuse_invalid_inputs(self):
        for kwargs in [{'material':'download'}, {'material':'tin','size':1025},
                       {'material':'tin','size':True}, {'material':'tin','seed':-1},
                       {'material':'tin','seed':True}]:
            with self.assertRaises(ValueError): proc_textures.generate(**kwargs)

    def test_sealed_candidates_admit_and_detect_tampering(self):
        with tempfile.TemporaryDirectory() as scratch, patch.object(proc_textures, 'build_directory', side_effect=lambda p:p):
            root = Path(scratch)
            maps = proc_textures.write_candidates(root, size=8)
            for material in proc_textures.MATERIALS:
                folder = root/material
                self.assertTrue(licence_gate.audit(folder/'provenance.json')['shippable'])
                provenance.verify_candidate(folder)
                self.assertEqual(set(maps[material]), pbr_pack.MAPS)
            with self.assertRaisesRegex(ValueError, 'output_exists'):
                proc_textures.write_candidates(root, size=8)
            (root/'tin/base_color.tga').write_bytes(b'tampered')
            self.assertFalse(licence_gate.audit(root/'tin/provenance.json')['shippable'])

    def test_output_refuses_source_tree(self):
        with self.assertRaises(BlenderRefusal):
            proc_textures.write_candidates(Path('assets_src/lantern/generated'), size=4)
