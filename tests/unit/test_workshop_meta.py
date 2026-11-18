"""Workshop meta.cpp ships with both mods (owner report 2026-11-18, synthetic fixtures only).

Every other subscribed Workshop mod carries a top-level meta.cpp with ``publishedid``; ours did not,
so the DayZ launcher did not list Hollow Country and a server staged from our folder advertised it
without a Workshop id ("Choose action" with no Steam icon). This proves only that the files exist and
are carried through packaging and staging; the launcher behaviour itself is checked on the client.
"""
import re
import tempfile
import unittest
from pathlib import Path

from tools.package import pbo
from tests.unit.test_local_test_session import SessionCase

ROOT = Path(__file__).resolve().parents[2]
ITEMS = {'HollowCountry': ('3841628320', 'Hollow Country'),
         'HollowCountryExpansionAI': ('3841637854', None)}


class RepoMeta(unittest.TestCase):
    def test_each_mod_has_meta_cpp_with_its_own_published_id(self):
        for folder, (item, name) in ITEMS.items():
            with self.subTest(folder=folder):
                text = (ROOT / 'mods' / folder / 'meta.cpp').read_text()
                self.assertIn('protocol = 1;', text)
                self.assertEqual(re.findall(r'^publishedid\s*=\s*(\d+);', text, re.M), [item])
                if name:
                    self.assertIn('name = "%s";' % name, text)

    def test_meta_cpp_stays_outside_the_pbo(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'config.cpp').write_text('class Synthetic {};')
            (root / 'meta.cpp').write_text('protocol = 1;\npublishedid = 1;\n')
            self.assertNotIn('meta.cpp', pbo.collect_addon(root))


class StagedMeta(SessionCase):
    def test_apply_stages_meta_cpp_next_to_mod_cpp(self):
        meta = b'protocol = 1;\npublishedid = 3841628320;\nname = "Hollow Country";\n'
        (self.built / 'meta.cpp').write_bytes(meta)
        code, out, err = self.run_cli(self.args('apply'))
        self.assertEqual(code, 0, err)
        self.assertEqual((self.dest / 'meta.cpp').read_bytes(), meta)


if __name__ == '__main__':
    unittest.main()
