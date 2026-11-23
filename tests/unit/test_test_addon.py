"""Dev-only test addon packing; synthetic sources and a fake signer, no key material and no DayZ."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.package import pbo
from tools.release import ship_inputs
from tools.setup import friend_bundle
from tools.testing import test_addon

CONFIG = 'class CfgPatches { class HollowCountryTest { requiredAddons[] = {"HollowCountry"}; }; };\n'
SCRIPT = 'class HCClientDriver {};\n'


def make_source(root, readme=True):
    src = Path(root) / test_addon.SOURCE_REL
    (src / 'scripts/5_Mission').mkdir(parents=True)
    (src / 'config.cpp').write_text(CONFIG)
    (src / 'mod.cpp').write_text('name = "test";\n')
    (src / 'scripts/5_Mission/HCClientDriver.c').write_text(SCRIPT)
    if readme:
        (src / 'README.md').write_text('notes\n')
    return src


def fake_signer(source, output):
    """Stand-in for the Wine signing flow: the same output shape, no key anywhere."""
    out = Path(output)
    (out / 'addons').mkdir(parents=True)
    data = Path(source).read_bytes()
    (out / 'addons' / test_addon.PBO_NAME).write_bytes(data)
    (out / 'addons' / (test_addon.PBO_NAME + '.HollowCountryDevelopment.bisign')).write_bytes(b'sig')
    (out / 'keys').mkdir()
    (out / 'keys' / 'HollowCountryDevelopment.bikey').write_bytes(b'public')


class PrefixTests(unittest.TestCase):
    def test_test_prefix_is_not_shipped(self):
        self.assertNotIn(pbo.TEST_PREFIX, pbo.PREFIXES)
        self.assertEqual(pbo.TEST_PREFIX, 'HollowCountryTest')

    def test_shipped_parse_refuses_it_and_scope_restores(self):
        files = {'config.cpp': CONFIG.encode()}
        with pbo.test_prefix_scope():
            self.assertIn(pbo.TEST_PREFIX, pbo.PREFIXES)
            blob = pbo.pack(files, pbo.TEST_PREFIX)
        self.assertNotIn(pbo.TEST_PREFIX, pbo.PREFIXES)
        with self.assertRaises(ValueError):
            pbo.parse(blob)
        with self.assertRaises(ValueError):
            pbo.parse(blob, prefixes=pbo.PREFIXES)

    def test_scope_restores_after_an_error(self):
        before = pbo.PREFIXES
        with self.assertRaises(RuntimeError), pbo.test_prefix_scope():
            raise RuntimeError('x')
        self.assertEqual(pbo.PREFIXES, before)


class ShippingTests(unittest.TestCase):
    def test_signing_inputs_never_list_the_test_addon(self):
        for guard, compat in ((None, ()), ('x', ('a',))):
            try:
                rows = ship_inputs.signing_inputs(guard, compat)
            except (ValueError, KeyError, TypeError):
                continue
            self.assertNotIn('hollowcountrytest', ' '.join(str(c).lower() for row in rows for c in row))

    def test_friend_bundle_never_lists_the_test_addon(self):
        text = Path(friend_bundle.__file__).read_text(encoding='utf-8')
        names = [str(x) for x in friend_bundle.BUNDLE_TOOLS + friend_bundle.BUNDLE_EXTRA_FILES]
        self.assertFalse([n for n in names if 'HollowCountryTest' in n or 'test_addon' in n or 'soak_' in n])
        self.assertNotIn('HollowCountryTest', text)
        self.assertNotIn('test_addon', text)

    def test_only_the_test_tools_open_the_scope(self):
        root = Path(__file__).resolve().parents[2]
        users = []
        for folder in ('tools', 'tests'):
            for path in sorted((root / folder).rglob('*.py')):
                if 'test_prefix_scope()' in path.read_text(encoding='utf-8'):
                    users.append(path.relative_to(root).as_posix())
        self.assertEqual([u for u in users if not u.startswith(('tools/testing/test_addon.py', 'tests/unit/test_test_addon.py', 'tools/package/pbo.py'))], [])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.scratch = Path(self.tmp.name) / 'scratch'
        self.root.mkdir()

    def test_missing_source_fails_with_a_reason(self):
        with self.assertRaisesRegex(test_addon.TestAddonError, 'not in this checkout'):
            test_addon.plan(self.root)

    def test_plan_ignores_readme_and_writes_nothing(self):
        make_source(self.root)
        result = test_addon.plan(self.root, self.scratch)
        self.assertEqual(result['prefix'], 'HollowCountryTest')
        self.assertEqual(result['pbo'], 'hollowcountrytest.pbo')
        self.assertEqual(result['scripts'], ['scripts/5_Mission/HCClientDriver.c'])
        self.assertFalse(self.scratch.exists())

    def test_build_packs_signs_and_replaces_the_old_folder(self):
        make_source(self.root)
        scratch = self.scratch
        first = test_addon.build(self.root, scratch, fake_signer)
        (scratch / test_addon.FOLDER / 'stale.txt').write_text('old')
        second = test_addon.build(self.root, scratch, fake_signer)
        self.assertEqual(first['sha256'], second['sha256'])
        out = scratch / test_addon.FOLDER
        self.assertFalse((out / 'stale.txt').exists())
        self.assertTrue((out / 'mod.cpp').is_file())
        self.assertEqual(second['signatures'], 1)
        blob = (out / 'addons' / test_addon.PBO_NAME).read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), second['sha256'])
        prefix, files = pbo.parse(blob, prefixes=(pbo.TEST_PREFIX,))
        self.assertEqual(prefix, pbo.TEST_PREFIX)
        self.assertIn('scripts/5_Mission/HCClientDriver.c', files)
        self.assertFalse(list(scratch.glob('work')))

    def test_compile_probe_package_matches_the_signed_input(self):
        make_source(self.root)
        probe_blob, count = test_addon.pack(self.root)
        self.assertFalse(self.scratch.exists())
        self.assertNotIn(pbo.TEST_PREFIX, pbo.PREFIXES)
        with self.assertRaises(ValueError):
            pbo.parse(probe_blob, prefixes=pbo.PREFIXES)
        result = test_addon.build(self.root, self.scratch, fake_signer)
        self.assertEqual(count, result['files'])
        self.assertEqual(hashlib.sha256(probe_blob).hexdigest(), result['sha256'])

    def test_build_refuses_a_scratch_folder_inside_the_repo(self):
        make_source(self.root)
        with self.assertRaisesRegex(test_addon.TestAddonError, 'outside the repository'):
            test_addon.build(self.root, self.root / 'scratch', fake_signer)

    def test_build_refuses_when_a_private_key_reaches_the_output(self):
        make_source(self.root)

        def leaky(source, output):
            fake_signer(source, output)
            (Path(output) / 'keys' / 'x.biprivatekey').write_bytes(b'secret')

        with self.assertRaisesRegex(test_addon.TestAddonError, 'private key'):
            test_addon.build(self.root, self.scratch, leaky)
        self.assertFalse((self.scratch / test_addon.FOLDER).exists())

    def test_unsigned_output_is_refused(self):
        make_source(self.root)

        def unsigned(source, output):
            (Path(output) / 'addons').mkdir(parents=True)
            (Path(output) / 'addons' / test_addon.PBO_NAME).write_bytes(Path(source).read_bytes())

        with self.assertRaisesRegex(test_addon.TestAddonError, 'not signed'):
            test_addon.build(self.root, self.scratch, unsigned)

    def test_signer_failure_names_no_path(self):
        make_source(self.root)

        def broken(source, output):
            raise OSError('/ho' + 'me/someone/secret failed')

        with self.assertRaises(test_addon.TestAddonError) as caught:
            test_addon.build(self.root, self.scratch, broken)
        self.assertNotIn('/home', str(caught.exception))

    def test_symlink_and_foreign_files_are_not_packed(self):
        src = make_source(self.root)
        (src / 'scripts/5_Mission/link.c').symlink_to(src / 'config.cpp')
        with self.assertRaisesRegex(test_addon.TestAddonError, 'symlink'):
            test_addon.plan(self.root)

    def test_script_outside_allowlist_is_refused(self):
        src = make_source(self.root)
        (src / 'scripts/5_Mission/payload.exe').write_bytes(b'MZ')
        with self.assertRaises(test_addon.TestAddonError):
            test_addon.plan(self.root)

    def test_cli_never_prints_the_output_path(self):
        make_source(self.root)
        from contextlib import redirect_stdout
        from io import StringIO
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = test_addon.main(['plan'])
        # The real checkout may or may not hold the addon yet; either way no path is printed.
        self.assertIn(code, (0, 2))
        self.assertNotIn('/home', buffer.getvalue())
        self.assertNotIn(str(self.scratch), buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
