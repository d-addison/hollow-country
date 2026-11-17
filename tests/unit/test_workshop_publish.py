"""Workshop publishing tool: synthetic content folders only.

Nothing here runs steamcmd, Steam, DayZ or the network; subprocess is patched to fail the test if
anything tries to start a process. Offline checks establish nothing about Workshop or DayZ behaviour.
"""
import contextlib
import io
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tools.package import workshop_publish as wp

KEY = 'hollowcountry_synthetic'
PNG = b'\x89PNG\r\n\x1a\n' + b'synthetic-preview' * 8
MARKER = 'S3CRET-MARKER-9f2'
META = 'protocol = 1;\npublishedid = 0;\nname = "Hollow Country";\n'


def make_mod(root, name='@HollowCountry', meta=None, key=KEY):
    mod = Path(root) / name
    (mod / 'addons').mkdir(parents=True)
    (mod / 'keys').mkdir()
    (mod / 'addons' / 'hollowcountry.pbo').write_bytes(b'synthetic-pbo-bytes')
    (mod / 'addons' / ('hollowcountry.pbo.%s.bisign' % key)).write_bytes(b'synthetic-signature')
    (mod / 'keys' / (key + '.bikey')).write_bytes(b'synthetic-public-key')
    (mod / 'mod.cpp').write_text('name = "Hollow Country";\n')
    if meta is not None:
        (mod / 'meta.cpp').write_text(meta)
    return mod


def parse_vdf(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    assert lines[0] == '"workshopitem"' and lines[1] == '{' and lines[-1] == '}', lines
    out = {}
    for line in lines[2:-1]:
        m = re.fullmatch(r'"([a-z]+)"\s+"([^"]*)"', line)
        assert m, line
        out[m.group(1)] = m.group(2)
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mod = make_mod(self.tmp, meta=META)
        self.out_dir = Path(self.tmp) / 'out'
        # Any attempt to start a process is a test failure.
        for target in ('subprocess.run', 'subprocess.Popen', 'subprocess.call', 'subprocess.check_call',
                       'subprocess.check_output'):
            patcher = mock.patch(target, side_effect=AssertionError('process started: ' + target))
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, *argv):
        buf = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = wp.main(list(argv), out=buf)
        return code, buf.getvalue(), err.getvalue()

    def prepare(self, *extra, mod=None):
        return self.run_main('prepare', '--mod', str(mod or self.mod), '--out', str(self.out_dir), *extra)

    def preview(self, data=PNG, name='preview.png'):
        path = Path(self.tmp) / name
        path.write_bytes(data)
        return str(path)

    def vdf(self):
        return parse_vdf((self.out_dir / 'workshop_item.vdf').read_text())


class ValidateContent(Base):
    def test_good_folder_lists_exactly_the_allowlisted_files(self):
        info = wp.validate_content(self.mod)
        self.assertEqual(sorted(info['files']), [
            'addons/hollowcountry.pbo', 'addons/hollowcountry.pbo.%s.bisign' % KEY,
            'keys/%s.bikey' % KEY, 'meta.cpp', 'mod.cpp'])

    def test_meta_cpp_is_optional_before_the_first_upload(self):
        (self.mod / 'meta.cpp').unlink()
        self.assertNotIn('meta.cpp', wp.validate_content(self.mod)['files'])

    def test_private_key_refused_anywhere(self):
        for rel in ('keys/hollowcountry.biprivatekey', 'addons/x.BIPRIVATEKEY', 'secret.biprivatekey'):
            with self.subTest(rel=rel):
                path = self.mod / rel
                path.write_bytes(b'private')
                with self.assertRaisesRegex(wp.PublishError, 'private key'):
                    wp.validate_content(self.mod)
                path.unlink()

    def test_extra_pbo_refused(self):
        (self.mod / 'addons' / 'other.pbo').write_bytes(b'x')
        with self.assertRaisesRegex(wp.PublishError, 'not allowed'):
            wp.validate_content(self.mod)

    def test_unlisted_extra_files_and_folders_refused(self):
        for rel in ('readme.txt', 'addons/notes.txt', 'keys/readme.txt', 'profiles/x.rpt', 'source/a.c',
                    'logs/x.log', 'addons/sub/hollowcountry.pbo'):
            with self.subTest(rel=rel):
                mod = make_mod(tempfile.mkdtemp(dir=self.tmp), meta=META)
                path = mod / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'x')
                with self.assertRaises(wp.PublishError):
                    wp.validate_content(mod)

    def test_symlinks_refused(self):
        target = Path(self.tmp) / 'elsewhere.bin'
        target.write_bytes(b'x')
        link = self.mod / 'mod.cpp'
        link.unlink()
        os.symlink(target, link)
        with self.assertRaisesRegex(wp.PublishError, 'symlink'):
            wp.validate_content(self.mod)

    def test_symlinked_directory_refused(self):
        shutil.rmtree(self.mod / 'keys')
        elsewhere = Path(self.tmp) / 'realkeys'
        elsewhere.mkdir()
        (elsewhere / (KEY + '.bikey')).write_bytes(b'k')
        os.symlink(elsewhere, self.mod / 'keys')
        with self.assertRaisesRegex(wp.PublishError, 'symlink'):
            wp.validate_content(self.mod)

    def test_symlinked_mod_folder_refused(self):
        link = Path(self.tmp) / 'link'
        os.symlink(self.mod, link)
        with self.assertRaisesRegex(wp.PublishError, 'symlink'):
            wp.validate_content(link)

    def test_hard_links_refused(self):
        os.link(self.mod / 'mod.cpp', Path(self.tmp) / 'second-name')
        with self.assertRaisesRegex(wp.PublishError, 'hard link'):
            wp.validate_content(self.mod)

    def test_pbo_without_bisign_refused(self):
        (self.mod / 'addons' / ('hollowcountry.pbo.%s.bisign' % KEY)).unlink()
        with self.assertRaisesRegex(wp.PublishError, 'bisign'):
            wp.validate_content(self.mod)

    def test_missing_pbo_refused(self):
        (self.mod / 'addons' / 'hollowcountry.pbo').unlink()
        with self.assertRaises(wp.PublishError):
            wp.validate_content(self.mod)

    def test_missing_bikey_refused(self):
        (self.mod / 'keys' / (KEY + '.bikey')).unlink()
        with self.assertRaisesRegex(wp.PublishError, 'bikey'):
            wp.validate_content(self.mod)

    def test_bisign_key_without_matching_bikey_refused(self):
        (self.mod / 'addons' / 'hollowcountry.pbo.other_key.bisign').write_bytes(b'sig')
        with self.assertRaisesRegex(wp.PublishError, 'other_key'):
            wp.validate_content(self.mod)

    def test_missing_mod_cpp_refused(self):
        (self.mod / 'mod.cpp').unlink()
        with self.assertRaisesRegex(wp.PublishError, 'mod.cpp'):
            wp.validate_content(self.mod)

    def test_empty_files_refused(self):
        (self.mod / 'addons' / 'hollowcountry.pbo').write_bytes(b'')
        with self.assertRaisesRegex(wp.PublishError, 'empty'):
            wp.validate_content(self.mod)

    def test_not_a_directory_refused(self):
        with self.assertRaises(wp.PublishError):
            wp.validate_content(Path(self.tmp) / 'missing')


class Prepare(Base):
    def test_writes_unlisted_vdf_and_prints_the_exact_command(self):
        code, text, _ = self.prepare()
        self.assertEqual(code, 0, text)
        vdf = self.out_dir / 'workshop_item.vdf'
        self.assertTrue(vdf.is_file())
        data = self.vdf()
        self.assertEqual(data['appid'], '221100')
        self.assertEqual(data['visibility'], '3')
        self.assertEqual(data['title'], 'Hollow Country')
        self.assertEqual(data['publishedfileid'], '0')
        self.assertTrue(data['description'])
        self.assertTrue(data['changenote'])
        self.assertTrue(Path(data['contentfolder']).is_dir())
        self.assertIn('steamcmd +login <their_username> +workshop_build_item %s +quit' % vdf, text)
        self.assertIn('Unlisted', text)

    def test_vdf_keys_are_exactly_these(self):
        self.prepare('--preview', self.preview())
        self.assertEqual(sorted(self.vdf()), ['appid', 'changenote', 'contentfolder', 'description',
                                              'previewfile', 'publishedfileid', 'title', 'visibility'])

    def test_content_folder_is_a_clean_staged_copy_with_only_allowlisted_files(self):
        self.prepare()
        staged = Path(self.vdf()['contentfolder'])
        files = sorted(p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file())
        self.assertEqual(files, ['addons/hollowcountry.pbo', 'addons/hollowcountry.pbo.%s.bisign' % KEY,
                                 'keys/%s.bikey' % KEY, 'meta.cpp', 'mod.cpp'])
        self.assertEqual((staged / 'addons/hollowcountry.pbo').read_bytes(), b'synthetic-pbo-bytes')
        self.assertTrue(all(os.lstat(p).st_nlink == 1 for p in staged.rglob('*') if p.is_file()))
        self.assertFalse(any(p.is_symlink() for p in staged.rglob('*')))

    def test_published_id_flag_sets_publishedfileid(self):
        code, _, _ = self.prepare('--published-id', '3600000001')
        self.assertEqual(code, 0)
        self.assertEqual(self.vdf()['publishedfileid'], '3600000001')

    def test_recorded_meta_publishedid_is_used_for_updates(self):
        wp.record(self.mod, 3600000002)
        self.prepare()
        self.assertEqual(self.vdf()['publishedfileid'], '3600000002')

    def test_conflicting_published_ids_refused(self):
        wp.record(self.mod, 3600000002)
        code, _, err = self.prepare('--published-id', '3600000009')
        self.assertEqual(code, 1)
        self.assertIn('3600000002', err)
        self.assertFalse((self.out_dir / 'workshop_item.vdf').exists())

    def test_bad_published_id_refused(self):
        for bad in ('0', '-1', 'abc', '12x'):
            with self.subTest(bad=bad):
                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stderr(io.StringIO()):
                        wp.main(['prepare', '--mod', str(self.mod), '--out', str(self.out_dir),
                                 '--published-id', bad], out=io.StringIO())

    def test_only_unlisted_visibility_is_accepted(self):
        for bad in ('public', 'friends', 'private', 'friends-only', '0', '1', '2', '3', 'UNLISTED '):
            with self.subTest(bad=bad):
                code, _, err = self.prepare('--visibility', bad)
                self.assertEqual(code, 1)
                self.assertIn('unlisted', err)
                self.assertFalse((self.out_dir / 'workshop_item.vdf').exists())
        code, _, _ = self.prepare('--visibility', 'unlisted')
        self.assertEqual(code, 0)

    def test_no_password_option_exists_and_nothing_secret_is_written(self):
        for flag in ('--password', '--steam-password', '--pass'):
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stderr(io.StringIO()):
                        wp.main(['prepare', '--mod', str(self.mod), '--out', str(self.out_dir), flag, 'x'],
                                out=io.StringIO())
        _, text, _ = self.prepare()
        written = (self.out_dir / 'workshop_item.vdf').read_text().lower()
        self.assertNotIn('password', written)
        self.assertNotIn('guard', written)
        self.assertNotIn('+login', written)
        self.assertEqual(text.count('+login <their_username>'), 1)

    def test_secret_values_are_never_echoed_on_rejection(self):
        for argv in (['--password', MARKER], ['--password=' + MARKER], ['--steam-pass', MARKER], ['-p', MARKER],
                     ['--token', MARKER], ['--secret=' + MARKER], ['--bogus', MARKER], ['--guard-code=' + MARKER]):
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as caught:
                        wp.main(['prepare', '--mod', str(self.mod), '--out', str(self.out_dir), *argv], out=out)
                self.assertEqual(caught.exception.code, 2)
                self.assertNotIn(MARKER, out.getvalue() + err.getvalue())
                self.assertTrue(err.getvalue())
        self.assertFalse(self.out_dir.exists())

    def test_preview_is_validated_and_referenced(self):
        code, _, _ = self.prepare('--preview', self.preview())
        self.assertEqual(code, 0)
        data = self.vdf()
        self.assertEqual(Path(data['previewfile']).read_bytes(), PNG)
        self.assertNotIn(Path(data['contentfolder']), Path(data['previewfile']).parents)

    def test_missing_or_non_png_or_oversize_preview_refused(self):
        code, _, _ = self.prepare('--preview', str(Path(self.tmp) / 'nope.png'))
        self.assertEqual(code, 1)
        code, _, err = self.prepare('--preview', self.preview(b'GIF89a-not-a-png'))
        self.assertEqual(code, 1)
        self.assertIn('PNG', err)
        code, _, err = self.prepare('--preview', self.preview(PNG + b'0' * wp.MAX_PREVIEW_BYTES))
        self.assertEqual(code, 1)
        self.assertIn('too large', err)

    def test_no_preview_warns_but_omits_previewfile(self):
        code, text, _ = self.prepare()
        self.assertEqual(code, 0)
        self.assertIn('no preview', text.lower())
        self.assertNotIn('previewfile', (self.out_dir / 'workshop_item.vdf').read_text())

    def test_change_note_default_names_the_pbo_digest_and_custom_is_sanitised(self):
        self.prepare()
        self.assertRegex(self.vdf()['changenote'], r'[0-9a-f]{12}')
        self.prepare('--change-note', 'say "hi"\nsecond line')
        self.assertEqual(self.vdf()['changenote'], "say 'hi' second line")

    def test_description_never_names_third_party_mods_or_ids(self):
        self.prepare()
        text = (self.out_dir / 'workshop_item.vdf').read_text().lower()
        for banned in ('2443122116', '2646817942', '1559212036', '2545327648', '2291785308', '2793893086',
                       '2792982069', 'snafu', 'flava'):
            self.assertNotIn(banned, text)

    def test_private_key_in_folder_stops_before_anything_is_written(self):
        (self.mod / 'keys' / 'x.biprivatekey').write_bytes(b'private')
        code, _, err = self.prepare()
        self.assertEqual(code, 1)
        self.assertIn('private key', err)
        self.assertFalse(self.out_dir.exists())

    def test_output_inside_the_mod_or_containing_it_refused(self):
        code, _, _ = self.run_main('prepare', '--mod', str(self.mod), '--out', str(self.mod / 'out'))
        self.assertEqual(code, 1)
        code, _, _ = self.run_main('prepare', '--mod', str(self.mod), '--out', self.tmp)
        self.assertEqual(code, 1)

    def test_output_with_foreign_files_refused_and_rerun_is_idempotent(self):
        self.prepare()
        first = (self.out_dir / 'workshop_item.vdf').read_text()
        code, _, _ = self.prepare()
        self.assertEqual(code, 0)
        self.assertEqual((self.out_dir / 'workshop_item.vdf').read_text(), first)
        (self.out_dir / 'something-else.txt').write_text('mine')
        code, _, err = self.prepare()
        self.assertEqual(code, 1)
        self.assertIn('something-else.txt', err)
        self.assertEqual((self.out_dir / 'something-else.txt').read_text(), 'mine')

    def test_windows_path_style_converts_wsl_drive_paths(self):
        self.assertEqual(wp.to_windows('/mnt/g/Stuff/mod'), 'G:\\Stuff\\mod')
        self.assertEqual(wp.to_windows('srv/x/mod'), 'srv/x/mod')
        self.assertEqual(self.prepare('--path-style', 'windows')[0], 0)

    def test_no_subprocess_is_used(self):
        # setUp patches every process launcher to raise; reaching here with exit 0 proves none ran.
        self.assertEqual(self.prepare()[0], 0)


class Record(Base):
    def test_creates_meta_cpp_with_name_and_publishedid(self):
        (self.mod / 'meta.cpp').unlink()
        path = wp.record(self.mod, 3600000003)
        self.assertEqual(path, self.mod / 'meta.cpp')
        self.assertEqual(path.read_text(), 'protocol = 1;\npublishedid = 3600000003;\nname = "Hollow Country";\n')

    def test_updates_existing_value_and_keeps_other_lines(self):
        (self.mod / 'meta.cpp').write_text('protocol = 1;\npublishedid = 0;\nname = "Hollow Country";\n'
                                           'timestamp = 5250960208020560000;\n')
        wp.record(self.mod, 3600000004)
        self.assertEqual((self.mod / 'meta.cpp').read_text(),
                         'protocol = 1;\npublishedid = 3600000004;\nname = "Hollow Country";\n'
                         'timestamp = 5250960208020560000;\n')

    def test_inserts_when_missing_from_an_existing_meta_cpp(self):
        (self.mod / 'meta.cpp').write_text('protocol = 1;\nname = "Hollow Country";\n')
        wp.record(self.mod, 3600000005)
        self.assertEqual((self.mod / 'meta.cpp').read_text(),
                         'protocol = 1;\npublishedid = 3600000005;\nname = "Hollow Country";\n')

    def test_idempotent_and_preserves_crlf(self):
        (self.mod / 'meta.cpp').write_bytes(b'protocol = 1;\r\npublishedid = 0;\r\nname = "Hollow Country";\r\n')
        wp.record(self.mod, 3600000006)
        once = (self.mod / 'meta.cpp').read_bytes()
        wp.record(self.mod, 3600000006)
        self.assertEqual((self.mod / 'meta.cpp').read_bytes(), once)
        self.assertEqual(once, b'protocol = 1;\r\npublishedid = 3600000006;\r\nname = "Hollow Country";\r\n')

    def test_duplicate_publishedid_lines_refused_and_file_untouched(self):
        body = 'publishedid = 1;\npublishedid = 2;\n'
        (self.mod / 'meta.cpp').write_text(body)
        with self.assertRaisesRegex(wp.PublishError, 'more than one'):
            wp.record(self.mod, 3)
        self.assertEqual((self.mod / 'meta.cpp').read_text(), body)

    def test_symlinked_meta_cpp_refused(self):
        (self.mod / 'meta.cpp').unlink()
        target = Path(self.tmp) / 'target.txt'
        target.write_text('x')
        os.symlink(target, self.mod / 'meta.cpp')
        with self.assertRaisesRegex(wp.PublishError, 'symlink'):
            wp.record(self.mod, 4)
        self.assertEqual(target.read_text(), 'x')

    def test_bad_ids_and_non_mod_folders_refused(self):
        for bad in (0, -5, 'abc', True):
            with self.subTest(bad=bad):
                with self.assertRaises(wp.PublishError):
                    wp.record(self.mod, bad)
        with self.assertRaises(wp.PublishError):
            wp.record(Path(self.tmp) / 'missing', 5)

    def test_cli_record(self):
        code, text, _ = self.run_main('record', '--mod', str(self.mod), '--published-id', '3600000007')
        self.assertEqual(code, 0)
        self.assertIn('3600000007', text)
        self.assertIn('publishedid = 3600000007;', (self.mod / 'meta.cpp').read_text())
        with self.assertRaises(SystemExit):
            self.run_main('record', '--mod', str(self.mod), '--published-id', 'zero')

    def test_recorded_meta_is_still_valid_content(self):
        wp.record(self.mod, 3600000008)
        self.assertIn('meta.cpp', wp.validate_content(self.mod)['files'])


ADDON_KEY = 'hollowcountry_synthetic'
ADDON_TITLE = 'Hollow Country Expansion AI (server)'
ADDON_META = 'protocol = 1;\npublishedid = 0;\nname = "%s";\n' % ADDON_TITLE


def make_addon(root, name='@HollowCountryExpansionAI', meta=ADDON_META, mod_cpp=True, key=ADDON_KEY):
    mod = Path(root) / name
    (mod / 'addons').mkdir(parents=True)
    (mod / 'keys').mkdir()
    (mod / 'addons' / 'hollowcountryexpansionai.pbo').write_bytes(b'synthetic-addon-pbo')
    (mod / 'addons' / ('hollowcountryexpansionai.pbo.%s.bisign' % key)).write_bytes(b'synthetic-addon-sig')
    (mod / 'keys' / (key + '.bikey')).write_bytes(b'synthetic-public-key')
    if mod_cpp:
        (mod / 'mod.cpp').write_text('name = "Hollow Country Expansion AI";\n')
    if meta is not None:
        (mod / 'meta.cpp').write_text(meta)
    return mod


class AddonItem(Base):
    def setUp(self):
        super().setUp()
        self.addon = make_addon(self.tmp)

    def prepare_addon(self, *extra, mod=None):
        return self.run_main('prepare', '--item', 'addon', '--mod', str(mod or self.addon),
                             '--out', str(self.out_dir), *extra)

    def test_good_addon_lists_exactly_the_allowlisted_files(self):
        info = wp.validate_content(self.addon, item='addon')
        self.assertEqual(sorted(info['files']), [
            'addons/hollowcountryexpansionai.pbo',
            'addons/hollowcountryexpansionai.pbo.%s.bisign' % ADDON_KEY,
            'keys/%s.bikey' % ADDON_KEY, 'meta.cpp', 'mod.cpp'])

    def test_mod_cpp_and_meta_cpp_are_optional_for_the_addon(self):
        (self.addon / 'meta.cpp').unlink()
        (self.addon / 'mod.cpp').unlink()
        info = wp.validate_content(self.addon, item='addon')
        self.assertNotIn('mod.cpp', info['files'])
        self.assertNotIn('meta.cpp', info['files'])

    def test_base_folder_given_as_addon_is_refused(self):
        with self.assertRaisesRegex(wp.PublishError, '--item base'):
            wp.validate_content(self.mod, item='addon')
        code, _, err = self.prepare('--item', 'addon')
        self.assertEqual(code, 1)
        self.assertIn('--item base', err)
        self.assertFalse(self.out_dir.exists())

    def test_addon_folder_given_as_base_is_refused(self):
        with self.assertRaisesRegex(wp.PublishError, '--item addon'):
            wp.validate_content(self.addon)
        code, _, err = self.prepare_addon_as_base()
        self.assertEqual(code, 1)
        self.assertIn('--item addon', err)
        self.assertFalse(self.out_dir.exists())

    def prepare_addon_as_base(self):
        return self.run_main('prepare', '--mod', str(self.addon), '--out', str(self.out_dir))

    def test_every_refusal_rule_still_applies_to_the_addon(self):
        for rel in ('keys/hollowcountry.biprivatekey', 'addons/x.BIPRIVATEKEY'):
            with self.subTest(rel=rel):
                path = self.addon / rel
                path.write_bytes(b'private')
                with self.assertRaisesRegex(wp.PublishError, 'private key'):
                    wp.validate_content(self.addon, item='addon')
                path.unlink()
        (self.addon / 'addons' / 'other.pbo').write_bytes(b'x')
        with self.assertRaisesRegex(wp.PublishError, 'not allowed'):
            wp.validate_content(self.addon, item='addon')
        (self.addon / 'addons' / 'other.pbo').unlink()
        os.link(self.addon / 'meta.cpp', Path(self.tmp) / 'second-name')
        with self.assertRaisesRegex(wp.PublishError, 'hard link'):
            wp.validate_content(self.addon, item='addon')

    def test_addon_symlink_and_empty_file_refused(self):
        (self.addon / 'addons' / 'hollowcountryexpansionai.pbo').write_bytes(b'')
        with self.assertRaisesRegex(wp.PublishError, 'empty'):
            wp.validate_content(self.addon, item='addon')
        (self.addon / 'addons' / 'hollowcountryexpansionai.pbo').write_bytes(b'pbo')
        target = Path(self.tmp) / 'elsewhere.bin'
        target.write_bytes(b'x')
        (self.addon / 'meta.cpp').unlink()
        os.symlink(target, self.addon / 'meta.cpp')
        with self.assertRaisesRegex(wp.PublishError, 'symlink'):
            wp.validate_content(self.addon, item='addon')

    def test_addon_without_signature_or_key_refused(self):
        (self.addon / 'addons' / ('hollowcountryexpansionai.pbo.%s.bisign' % ADDON_KEY)).unlink()
        with self.assertRaisesRegex(wp.PublishError, 'bisign'):
            wp.validate_content(self.addon, item='addon')

    def test_unknown_item_is_refused(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.run_main('prepare', '--item', 'both', '--mod', str(self.mod), '--out', str(self.out_dir))
        with self.assertRaises(wp.PublishError):
            wp.validate_content(self.mod, item='both')

    def test_prepare_writes_the_addon_title_description_and_unlisted_vdf(self):
        code, text, _ = self.prepare_addon()
        self.assertEqual(code, 0, text)
        data = self.vdf()
        self.assertEqual(data['title'], ADDON_TITLE)
        self.assertEqual(data['visibility'], '3')
        self.assertEqual(data['publishedfileid'], '0')
        description = data['description']
        for needle in ('server-side', '-serverMod', 'Hollow Country', 'Expansion AI', 'Expansion', 'CF', 'Dabs',
                       'never bundled'):
            self.assertIn(needle, description)
        self.assertRegex(description, r'(?i)players do not need')
        self.assertIn('Unlisted', text)
        self.assertRegex(data['changenote'], r'Expansion AI.*[0-9a-f]{12}')

    def test_addon_description_names_no_ids_or_weapon_packs(self):
        self.prepare_addon()
        text = (self.out_dir / 'workshop_item.vdf').read_text().lower()
        for banned in ('2443122116', '2646817942', '1559212036', '2545327648', '2291785308', '2793893086',
                       '2792982069', 'snafu', 'flava'):
            self.assertNotIn(banned, text)

    def test_base_title_and_description_are_unchanged_by_the_addon_item(self):
        self.prepare()
        data = self.vdf()
        self.assertEqual(data['title'], 'Hollow Country')
        self.assertNotIn('-serverMod', data['description'])

    def test_addon_content_folder_stages_only_allowlisted_files(self):
        self.prepare_addon()
        staged = Path(self.vdf()['contentfolder'])
        files = sorted(p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file())
        self.assertEqual(files, ['addons/hollowcountryexpansionai.pbo',
                                 'addons/hollowcountryexpansionai.pbo.%s.bisign' % ADDON_KEY,
                                 'keys/%s.bikey' % ADDON_KEY, 'meta.cpp', 'mod.cpp'])

    def test_addon_published_id_flag_and_recorded_id_are_used(self):
        self.assertEqual(self.prepare_addon('--published-id', '3900000001')[0], 0)
        self.assertEqual(self.vdf()['publishedfileid'], '3900000001')
        wp.record(self.addon, 3900000002, item='addon')
        code, _, err = self.prepare_addon('--published-id', '3900000001')
        self.assertEqual(code, 1)
        self.assertIn('3900000002', err)

    def test_addon_only_unlisted_is_accepted(self):
        for bad in ('public', 'friends-only', 'private', '3'):
            with self.subTest(bad=bad):
                code, _, err = self.prepare_addon('--visibility', bad)
                self.assertEqual(code, 1)
                self.assertIn('unlisted', err)
                self.assertFalse((self.out_dir / 'workshop_item.vdf').exists())

    def test_record_creates_addon_meta_with_the_addon_name(self):
        (self.addon / 'meta.cpp').unlink()
        path = wp.record(self.addon, 3900000003, item='addon')
        self.assertEqual(path.read_text(),
                         'protocol = 1;\npublishedid = 3900000003;\nname = "%s";\n' % ADDON_TITLE)

    def test_record_refuses_a_folder_of_the_other_item(self):
        with self.assertRaisesRegex(wp.PublishError, '--item base'):
            wp.record(self.mod, 3900000004, item='addon')
        with self.assertRaisesRegex(wp.PublishError, '--item addon'):
            wp.record(self.addon, 3900000004)
        self.assertNotIn('3900000004', (self.mod / 'meta.cpp').read_text())

    def test_cli_record_item_addon(self):
        code, text, _ = self.run_main('record', '--item', 'addon', '--mod', str(self.addon),
                                      '--published-id', '3900000005')
        self.assertEqual(code, 0)
        self.assertIn('publishedid = 3900000005;', (self.addon / 'meta.cpp').read_text())
        code, _, err = self.run_main('record', '--item', 'addon', '--mod', str(self.mod),
                                     '--published-id', '3900000005')
        self.assertEqual(code, 1)
        self.assertIn('--item base', err)

    def test_cli_record_defaults_to_the_base_item(self):
        (self.mod / 'meta.cpp').unlink()
        code, _, _ = self.run_main('record', '--mod', str(self.mod), '--published-id', '3900000006')
        self.assertEqual(code, 0)
        self.assertIn('name = "Hollow Country";', (self.mod / 'meta.cpp').read_text())

    def test_each_item_refuses_the_other_items_workshop_id(self):
        # Base is 3841628320 and the addon is 3841637854 on the Workshop; a crossed id would make an
        # upload overwrite the other item.
        for item, mod, other_id in (('addon', self.addon, '3841628320'), ('base', self.mod, '3841637854')):
            with self.subTest(item=item):
                code, _, err = self.run_main('prepare', '--item', item, '--mod', str(mod),
                                             '--out', str(self.out_dir), '--published-id', other_id)
                self.assertEqual(code, 1)
                self.assertIn(other_id, err)
                self.assertFalse(self.out_dir.exists())
                with self.assertRaisesRegex(wp.PublishError, other_id):
                    wp.record(mod, int(other_id), item=item)
        (self.addon / 'meta.cpp').write_text('protocol = 1;\npublishedid = 3841628320;\n')
        code, _, err = self.prepare_addon()
        self.assertEqual(code, 1)
        self.assertIn('3841628320', err)
        self.assertFalse(self.out_dir.exists())

    def test_each_item_accepts_its_own_workshop_id(self):
        self.assertEqual(self.prepare_addon('--published-id', '3841637854')[0], 0)
        self.assertEqual(self.vdf()['publishedfileid'], '3841637854')

    def test_no_subprocess_is_used_for_the_addon(self):
        self.assertEqual(self.prepare_addon()[0], 0)


class Documentation(unittest.TestCase):
    def test_docs_describe_the_publisher_alternative_and_unlisted(self):
        text = (Path(__file__).resolve().parents[2] / 'docs/FRIEND_SERVER.md').read_text()
        self.assertIn('Publisher', text)
        self.assertIn('Unlisted', text)
        self.assertIn('workshop_publish.py', text)
        self.assertIn('--item addon', text)
        self.assertIn('3841628320', text)
        self.assertNotRegex(text, r'(?i)password\s*[:=]\s*\S')


if __name__ == '__main__':
    unittest.main()
