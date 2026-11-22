"""Package manifest check (#153 WP-1): a staged or signed mod folder before it reaches players.

Synthetic temp folders only. The two shipped regressions this guards: a missing meta.cpp (the launcher
did not list the mod) and a missing Workshop "Mod" tag (launcher Added:0). One test builds the real
unsigned PBOs through the existing pbo tooling; nothing here proves DayZ or launcher behaviour.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.package import pbo, weapon_pack_guards, workshop_publish
from tools.validate import package_manifest as pm

ROOT = Path(__file__).resolve().parents[2]
BASE_ID = 3841628320
ADDON_ID = 3841637854


def make_mod(root, kind='base', signed=False, drop=(), published_id=None, mod_cpp=True, meta_cpp=True,
             bikey=True):
    """A complete synthetic mod folder; ``drop`` names relative files to leave out."""
    spec = pm.expected_spec(kind)
    root = Path(root)
    (root / 'addons').mkdir(parents=True)
    (root / 'keys').mkdir()
    for name in spec['pbos']:
        (root / 'addons' / name).write_bytes(b'synthetic pbo')
        if signed:
            (root / 'addons' / (name + '.hc_test.bisign')).write_bytes(b'synthetic sign')
    if signed and bikey:
        (root / 'keys' / 'hc_test.bikey').write_bytes(b'synthetic key')
    if mod_cpp:
        (root / 'mod.cpp').write_text('name = "Synthetic";\n')
    if meta_cpp:
        pid = spec['published_id'] if published_id is None else published_id
        (root / 'meta.cpp').write_text('protocol = 1;\npublishedid = %s;\nname = "Synthetic";\n' % pid)
    for rel in drop:
        (root / rel).unlink()
    return root


def write_vdf(path, tags='Mod', item_id=BASE_ID):
    lines = ['"workshopitem"', '{', '\t"appid"\t\t"221100"', '\t"publishedfileid"\t\t"%d"' % item_id]
    if tags is not None:
        lines.append('\t"tags"\t\t"%s"' % tags)
    lines.append('}')
    Path(path).write_text('\n'.join(lines) + '\n')
    return path


def codes(findings):
    return sorted(f.code for f in findings)


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)


class RouteInventory(Case):
    def test_generated_inventory_matches_pins_and_refuses_partial_or_mixed_data(self):
        mission = ROOT / 'mission/hollow-country'
        files = {path.relative_to(mission).as_posix(): path.read_bytes()
                 for pattern in ('travel/gapcov-roads/*.json', 'travel/routes-manifest*.json')
                 for path in mission.glob(pattern)}
        index = json.loads(files['travel/gapcov-roads/index.json'])
        manifest = json.loads(files['travel/routes-manifest.json'])
        expected = {'travel/gapcov-roads/index.json', 'travel/routes-manifest.json'}
        catalog_pins = []
        for pin in index['index_pages']:
            document = json.loads(files[pin['Path'].removeprefix('$mission:hollow-country/')])
            catalog_pins.extend(document['pages'])
        pins = index['index_pages'] + catalog_pins + manifest['HashPages']
        expected.update(pin['Path'].removeprefix('$mission:hollow-country/') for pin in pins)
        self.assertEqual(expected, pbo.route_inventory(files))
        self.assertTrue(expected <= pbo.MISSION_FILES)
        for pin in pins:
            name = pin['Path'].removeprefix('$mission:hollow-country/')
            missing = dict(files)
            del missing[name]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                pbo.route_inventory(missing)
            mixed = dict(files, **{name: files[name] + b' '})
            with self.subTest(mixed=name), self.assertRaises(ValueError):
                pbo.route_inventory(mixed)
        extra = dict(files, **{'travel/gapcov-roads/page-unlisted.json': b'{}'})
        with self.assertRaisesRegex(ValueError, 'page set mismatch'):
            pbo.route_inventory(extra)
        mixed = dict(files)
        manifest['CatalogIdentitySha256'] = '0' * len(manifest['CatalogIdentitySha256'])
        mixed['travel/routes-manifest.json'] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            pbo.route_inventory(mixed)


class ExpectedSpec(Case):
    def test_base_expects_main_and_anims_pbo_from_packaging_code(self):
        spec = pm.expected_spec('base')
        self.assertEqual(spec['published_id'], BASE_ID)
        self.assertEqual(set(spec['pbos']), {'hollowcountry.pbo', 'hollowcountryanims.pbo'})

    def test_expansionai_expects_its_own_pbo_and_id(self):
        spec = pm.expected_spec('expansionai')
        self.assertEqual(spec['published_id'], ADDON_ID)
        self.assertEqual(spec['pbos'][0], 'hollowcountryexpansionai.pbo')

    def test_expected_names_track_the_publish_tool_not_a_private_list(self):
        for kind, item in (('base', 'base'), ('expansionai', 'addon')):
            item_spec = workshop_publish.ITEMS[item]
            self.assertEqual(pm.expected_spec(kind)['pbos'], (item_spec['pbo'],) + tuple(item_spec['extra_pbos']))
            self.assertEqual(pm.expected_spec(kind)['published_id'], workshop_publish.WORKSHOP_IDS[item])

    def test_every_expected_pbo_maps_to_a_packaging_prefix_and_source_folder(self):
        for kind in ('base', 'expansionai'):
            for name, prefix in pm.expected_spec(kind)['prefixes'].items():
                self.assertIn(prefix, pbo.PREFIXES)
                if prefix == pbo.GUARD_PREFIX:
                    # Generated at package time from Workshop configs; no source folder.
                    self.assertEqual(weapon_pack_guards.PBO_NAME, name)
                    continue
                if prefix.startswith(pbo.COMPAT_PREFIX):
                    # Generated at bundle time by tools.package.compat_addon; no source folder.
                    self.assertEqual(pbo.pbo_file_name(prefix), name)
                    continue
                self.assertEqual(prefix.lower() + '.pbo', name)
                self.assertTrue((ROOT / 'mods' / prefix).is_dir())

    def test_compat_pbos_map_to_their_own_prefixes_and_only_slots_are_optional(self):
        spec = pm.expected_spec('expansionai')
        self.assertEqual(pbo.COMPAT_PREFIX, spec['prefixes'][workshop_publish.COMPAT_PBO_NAME])
        for slot in pbo.COMPAT_SLOTS:
            self.assertEqual(pbo.COMPAT_PREFIX + '-' + slot, spec['prefixes'][pbo.compat_slot_pbo(slot)])
        self.assertEqual(set(workshop_publish.COMPAT_SLOT_PBO_NAMES), set(spec['optional']))
        self.assertNotIn(workshop_publish.COMPAT_PBO_NAME, spec['optional'])
        self.assertEqual((), pm.expected_spec('base')['optional'])

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            pm.expected_spec('nonsense')


class Findings(Case):
    def check(self, mod, kind='base', signed=False, vdf=None):
        return pm.check(mod, pm.expected_spec(kind), signed=signed, vdf=vdf)

    def test_complete_unsigned_base_passes(self):
        self.assertEqual(self.check(make_mod(self.tmp / 'a')), [])

    def test_complete_signed_base_passes(self):
        self.assertEqual(self.check(make_mod(self.tmp / 'a', signed=True), signed=True), [])

    def test_complete_signed_expansionai_with_vdf_passes(self):
        mod = make_mod(self.tmp / 'a', kind='expansionai', signed=True)
        vdf = write_vdf(self.tmp / 'item.vdf', item_id=ADDON_ID)
        self.assertEqual(self.check(mod, 'expansionai', signed=True, vdf=vdf), [])

    def test_optional_compat_slot_pbos_may_be_absent_but_the_base_compat_pbo_may_not(self):
        spec = pm.expected_spec('expansionai')
        slots = [f'addons/{name}' for name in spec['optional']]
        mod = make_mod(self.tmp / 'a', kind='expansionai', signed=True, drop=[
            *slots, *(f'{s}.hc_test.bisign' for s in slots)])
        self.assertEqual(self.check(mod, 'expansionai', signed=True), [])
        base = f'addons/{workshop_publish.COMPAT_PBO_NAME}'
        mod = make_mod(self.tmp / 'b', kind='expansionai', drop=[base])
        found = self.check(mod, 'expansionai')
        self.assertEqual(['missing_pbo'], codes(found))
        self.assertIn(workshop_publish.COMPAT_PBO_NAME, found[0].detail)

    def test_present_optional_slot_pbo_must_be_signed(self):
        spec = pm.expected_spec('expansionai')
        slot = spec['optional'][0]
        mod = make_mod(self.tmp / 'a', kind='expansionai', signed=True,
                       drop=[f'addons/{slot}.hc_test.bisign'])
        found = self.check(mod, 'expansionai', signed=True)
        self.assertEqual(['missing_signature'], codes(found))
        self.assertIn(slot, found[0].detail)

    def test_missing_anims_pbo_fails_missing_pbo(self):
        mod = make_mod(self.tmp / 'a', drop=('addons/hollowcountryanims.pbo',))
        found = self.check(mod)
        self.assertEqual(codes(found), ['missing_pbo'])
        self.assertIn('hollowcountryanims.pbo', found[0].detail)

    def test_empty_pbo_counts_as_missing(self):
        mod = make_mod(self.tmp / 'a')
        (mod / 'addons' / 'hollowcountry.pbo').write_bytes(b'')
        self.assertEqual(codes(self.check(mod)), ['missing_pbo'])

    def test_missing_meta_cpp_fails_missing_meta_cpp(self):
        mod = make_mod(self.tmp / 'a', meta_cpp=False)
        self.assertEqual(codes(self.check(mod)), ['missing_meta_cpp'])

    def test_missing_mod_cpp_fails_missing_mod_cpp(self):
        mod = make_mod(self.tmp / 'a', mod_cpp=False)
        self.assertEqual(codes(self.check(mod)), ['missing_mod_cpp'])

    def test_wrong_publishedid_fails(self):
        mod = make_mod(self.tmp / 'a', published_id=ADDON_ID)  # the other item's id
        found = self.check(mod)
        self.assertEqual(codes(found), ['wrong_publishedid'])

    def test_meta_cpp_without_publishedid_fails_wrong_publishedid(self):
        mod = make_mod(self.tmp / 'a')
        (mod / 'meta.cpp').write_text('protocol = 1;\nname = "x";\n')
        self.assertEqual(codes(self.check(mod)), ['wrong_publishedid'])

    def test_vdf_without_mod_tag_fails_missing_mod_tag(self):
        mod = make_mod(self.tmp / 'a')
        for tags in (None, '', 'Server', 'Modded'):
            with self.subTest(tags=tags):
                vdf = write_vdf(self.tmp / 'item.vdf', tags=tags)
                self.assertEqual(codes(self.check(mod, vdf=vdf)), ['missing_mod_tag'])

    def test_vdf_tag_list_containing_mod_passes(self):
        mod = make_mod(self.tmp / 'a')
        vdf = write_vdf(self.tmp / 'item.vdf', tags='Server,mod')
        self.assertEqual(self.check(mod, vdf=vdf), [])

    def test_unreadable_vdf_fails_missing_mod_tag(self):
        mod = make_mod(self.tmp / 'a')
        self.assertEqual(codes(self.check(mod, vdf=self.tmp / 'absent.vdf')), ['missing_mod_tag'])

    def test_vdf_with_the_other_items_id_fails_wrong_publishedid(self):
        mod = make_mod(self.tmp / 'a')
        vdf = write_vdf(self.tmp / 'item.vdf', item_id=ADDON_ID)
        self.assertEqual(codes(self.check(mod, vdf=vdf)), ['wrong_publishedid'])

    def test_first_upload_vdf_with_zero_id_is_allowed(self):
        mod = make_mod(self.tmp / 'a')
        vdf = write_vdf(self.tmp / 'item.vdf', item_id=0)
        self.assertEqual(self.check(mod, vdf=vdf), [])

    def test_missing_bisign_fails_in_signed_mode_only(self):
        mod = make_mod(self.tmp / 'a', signed=True, drop=('addons/hollowcountryanims.pbo.hc_test.bisign',))
        found = self.check(mod, signed=True)
        self.assertEqual(codes(found), ['missing_signature'])
        self.assertIn('hollowcountryanims.pbo', found[0].detail)
        self.assertEqual(self.check(mod, signed=False), [])

    def test_empty_bisign_does_not_count(self):
        mod = make_mod(self.tmp / 'a', signed=True)
        (mod / 'addons' / 'hollowcountry.pbo.hc_test.bisign').write_bytes(b'')
        self.assertEqual(codes(self.check(mod, signed=True)), ['missing_signature'])

    def test_missing_bikey_fails_in_signed_mode(self):
        mod = make_mod(self.tmp / 'a', signed=True, bikey=False)
        self.assertEqual(codes(self.check(mod, signed=True)), ['missing_key'])

    def test_bisign_key_without_matching_bikey_fails_missing_key(self):
        mod = make_mod(self.tmp / 'a', signed=True)
        (mod / 'keys' / 'hc_test.bikey').rename(mod / 'keys' / 'other.bikey')
        self.assertEqual(codes(self.check(mod, signed=True)), ['missing_key'])

    def test_missing_addons_folder_reports_every_pbo(self):
        mod = self.tmp / 'empty'
        mod.mkdir()
        self.assertEqual(codes(self.check(mod)),
                         ['missing_meta_cpp', 'missing_mod_cpp', 'missing_pbo', 'missing_pbo'])

    def test_findings_are_deterministic_and_never_carry_absolute_paths(self):
        mod = self.tmp / 'empty'
        mod.mkdir()
        first, second = self.check(mod), self.check(mod)
        self.assertEqual([(f.code, f.detail) for f in first], [(f.code, f.detail) for f in second])
        for f in first:
            self.assertNotIn(str(self.tmp), f.detail)
            self.assertNotIn('/', f.detail.replace('addons/', '').replace('keys/', ''))


class RealUnsignedPbos(Case):
    # collect_addon refuses the binary anims source (anims/**/*.agf is built by DayZ Tools, not by our
    # stored-PBO tool), so that one PBO stays a synthetic stand-in; the script PBOs are the real output.
    NOT_BUILDABLE = 'hollowcountryanims.pbo'

    def stage(self, kind, folder):
        mod = self.tmp / folder
        (mod / 'addons').mkdir(parents=True)
        spec = pm.expected_spec(kind)
        for name, prefix in spec['prefixes'].items():
            if name == self.NOT_BUILDABLE:
                (mod / 'addons' / name).write_bytes(b'synthetic stand-in for the DayZ Tools anims PBO')
                continue
            if prefix == pbo.GUARD_PREFIX:
                # weapon_pack_guards builds this one from installed Workshop configs.
                (mod / 'addons' / name).write_bytes(b'synthetic stand-in for the generated guard PBO')
                continue
            if prefix.startswith(pbo.COMPAT_PREFIX):
                # compat_addon builds these at bundle time.
                (mod / 'addons' / name).write_bytes(b'synthetic stand-in for a generated compat PBO')
                continue
            files = pbo.collect_addon(ROOT / 'mods' / prefix, prefix)
            (mod / 'addons' / name).write_bytes(pbo.pack(files, prefix))
        (mod / 'mod.cpp').write_bytes((ROOT / 'mods' / spec['prefixes'][spec['pbos'][0]] / 'mod.cpp').read_bytes())
        (mod / 'meta.cpp').write_bytes((ROOT / 'mods' / spec['prefixes'][spec['pbos'][0]] / 'meta.cpp').read_bytes())
        return mod, spec

    def test_real_pbo_tooling_output_passes_unsigned_and_fails_signed(self):
        for kind in ('base', 'expansionai'):
            with self.subTest(kind=kind):
                mod, spec = self.stage(kind, '@' + kind)
                self.assertEqual(pm.check(mod, spec, signed=False), [])
                self.assertEqual(sorted(set(codes(pm.check(mod, spec, signed=True)))),
                                 ['missing_key', 'missing_signature'])

    def test_repo_meta_cpp_matches_the_expected_ids(self):
        for kind, folder in (('base', 'HollowCountry'), ('expansionai', 'HollowCountryExpansionAI')):
            text = (ROOT / 'mods' / folder / 'meta.cpp').read_text()
            self.assertEqual(pm.published_id(text), pm.expected_spec(kind)['published_id'])


class Cli(Case):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pm.main(list(args))
        return code, out.getvalue()

    def test_pass_exits_zero_with_one_summary_line(self):
        mod = make_mod(self.tmp / 'a')
        code, text = self.run_cli('--mod', str(mod), '--kind', 'base')
        self.assertEqual(code, 0)
        self.assertEqual(len(text.strip().splitlines()), 1)
        self.assertIn('OK', text)

    def test_failure_exits_one_and_names_each_code_without_paths(self):
        mod = make_mod(self.tmp / 'a', signed=True, meta_cpp=False)
        vdf = write_vdf(self.tmp / 'item.vdf', tags=None)
        code, text = self.run_cli('--mod', str(mod), '--kind', 'base', '--signed', '--vdf', str(vdf))
        self.assertEqual(code, 1)
        self.assertIn('missing_meta_cpp', text)
        self.assertIn('missing_mod_tag', text)
        self.assertEqual(text.strip().splitlines()[-1].split()[0], 'package_manifest:')
        self.assertNotIn(str(self.tmp), text)

    def test_missing_mod_folder_exits_one(self):
        code, text = self.run_cli('--mod', str(self.tmp / 'nope'), '--kind', 'base')
        self.assertEqual(code, 1)
        self.assertIn('FAIL', text)

    def test_bad_kind_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            pm.main(['--mod', str(self.tmp), '--kind', 'nonsense'])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
