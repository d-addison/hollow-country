"""Offline helper contracts only; generated Enforce is never executed here."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.release.host_lock import ENV, host_lock as existing_host_lock
from tools.setup import probe_core as core, probe_runtime as runtime


class Paths(unittest.TestCase):
    def test_drive_roundtrip(self):
        for path in ('/mnt/d', '/mnt/e/Probe space/file.txt', "/mnt/c/O'Brien/$cache;test"):
            with self.subTest(path=path):
                self.assertEqual(core.linux_path(core.windows_path(path)), Path(path))
        self.assertEqual(core.windows_path('/mnt/D/probe'), 'D:\\probe')
        self.assertEqual(core.linux_path('E:/probe/file'), Path('/mnt/e/probe/file'))

    def test_refused_paths(self):
        for path in ('probe', '/tmp/probe', '/mnt/dd/probe', '/mnt/d/../probe',
                     '/mnt/d/name.', '/mnt/d/NUL.txt', '/mnt/d/a:b', '/mnt/d/a\\b',
                     '/mnt/d/a\n', '/mnt/d//probe'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                core.windows_path(path)
        for path in ('D:probe', 'relative', r'\\server\share', 'D:/../probe',
                     'D:/name ', 'D:/CON.log', 'D:/a\x00b', 'D://probe'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                core.linux_path(path)

    def test_powershell_literal_roundtrip(self):
        for value in ('', "O'Brien", '$env:example; `thing`', 'space and "quotes"',
                      core.windows_path('/mnt/d/probe')):
            quoted = core.quote_ps(value)
            self.assertEqual(quoted[:1], "'")
            self.assertEqual(quoted[-1:], "'")
            self.assertEqual(quoted[1:-1].replace("''", "'"), value)
        for value in ('line\nbreak', '\x00', '\r', '\t'):
            with self.assertRaises(ValueError):
                core.quote_ps(value)

    def test_safe_missing_and_regular(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            leaf = root / 'regular'
            leaf.write_bytes(b'probe')
            for path in (root, leaf, root / 'new' / 'leaf'):
                self.assertEqual(core.safe(path), path.absolute())
            with self.assertRaises(ValueError):
                core.safe(root / '..' / 'escape')

    def test_symlink_leaf_ancestor_and_dangling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'target'
            target.mkdir()
            link = root / 'link'
            link.symlink_to(target, target_is_directory=True)
            dangling = root / 'dangling'
            dangling.symlink_to(root / 'absent')
            for path in (link, link / 'missing', dangling):
                with self.subTest(path=path.name), self.assertRaises(ValueError):
                    core.safe(path)

    def test_reparse_attributes_and_inspection_errors(self):
        original = Path.lstat
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def reparse(path):
                if path == root:
                    return SimpleNamespace(st_mode=stat.S_IFDIR,
                                           st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                return original(path)

            with patch.object(Path, 'lstat', reparse), self.assertRaises(ValueError):
                core.safe(root / 'new')
            with patch.object(Path, 'lstat', side_effect=PermissionError('refused')):
                with self.assertRaises(PermissionError):
                    core.safe(root)


class Emitters(unittest.TestCase):
    def test_generated_helpers_pass_compile_shape_lint(self):
        for limit in (1, 96, 4096):
            source = 'class HCOfflineProbe {\n' + core.enforce_json_helpers(max_string_bytes=limit) + '\n};'
            self.assertEqual(runtime.lint_hook(source, explicit_numbers=True), [])
            self.assertLessEqual(runtime.max_statement_plus(source), runtime.MAX_STATEMENT_PLUS)

    def test_invalid_bounds(self):
        for limit in (0, -1, 4097, True, 1.5, '96', None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                core.enforce_json_helpers(max_string_bytes=limit)

    def test_sanitizing_helpers_pass_lint_and_follow_their_parameters(self):
        for style in ('tostring', 'plain'):
            for limit in (1, 96, 4096):
                with self.subTest(style=style, limit=limit):
                    text = core.enforce_sanitizing_json_helpers('HCX', 'm_Quote', 'm_Slash', vector=style,
                                                                max_string_bytes=limit)
                    source = ('class HCOfflineProbe {\n    protected string m_Quote = "";\n'
                              '    protected string m_Slash = "";\n' + text + '\n};')
                    self.assertEqual(runtime.lint_hook(source, explicit_numbers=style == 'tostring'), [])
                    self.assertLessEqual(runtime.max_statement_plus(source), runtime.MAX_STATEMENT_PLUS)
                    for name in ('Key', 'Str', 'Bool', 'Vector'):
                        self.assertIn('string HCX%s(' % name, text)
                    self.assertEqual(text.count('.ToString()'), 3 if style == 'tostring' else 0)
                    self.assertIn('Length() > %d' % limit, text)
                    self.assertNotIn('@', text)

    def test_sanitizing_helpers_refuse_bad_parameters(self):
        good = dict(prefix='HCX', quote='m_Quote', slash='m_Slash')
        for key, value in (('prefix', 'a b'), ('prefix', ''), ('quote', '1x'), ('slash', 'x;y')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                core.enforce_sanitizing_json_helpers(**{**good, key: value})
        for kwargs in (dict(vector='num'), dict(max_string_bytes=0), dict(max_string_bytes=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                core.enforce_sanitizing_json_helpers(**good, **kwargs)

    def test_taped_light_hook_embeds_the_shared_helpers(self):
        from tools.setup import taped_light_probe as taped
        document = {'kind': taped.CLASSIFICATION_KIND,
                    'hosts': [{'group': 'slot_host', 'name': 'HostA', 'root': 'RootA'}],
                    'lights': [{'name': 'LightA', 'probe_role': 'representative', 'group': 'x'}],
                    'native_light_slots': ['Light']}
        hook = taped.render_hook(taped.select_targets(document)).decode('ascii')
        self.assertIn(taped.JSON_HELPERS, hook)
        self.assertEqual(hook.count('string HCTLStr('), 1)
        self.assertNotIn('@@', hook)

    def test_script_style_runtime_import(self):
        result = subprocess.run([sys.executable, '-B', '-c', 'import probe_runtime'],
                                cwd=Path(core.__file__).parent, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)


class HostLease(unittest.TestCase):
    def test_shared_contention_reentry_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'host.lock'
            previous = os.environ.get(ENV)
            with existing_host_lock('test', path):
                record = json.loads(path.read_text())
                with core.host_lock('probe', path):
                    self.assertEqual(json.loads(path.read_text()), record)
                env = dict(os.environ)
                env.pop(ENV, None)
                script = ('import sys; from tools.setup.probe_core import host_lock; '
                          '\nwith host_lock("probe", sys.argv[1]): pass')
                result = subprocess.run([sys.executable, '-B', '-c', script, str(path)],
                                        env=env, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'holder=test', result.stderr)
            self.assertEqual(os.environ.get(ENV), previous)
            with self.assertRaises(RuntimeError):
                with core.host_lock('probe', path):
                    raise RuntimeError('synthetic interruption')
            with core.host_lock('probe', path):
                self.assertEqual(json.loads(path.read_text())['holder'], 'probe')


if __name__ == '__main__':
    unittest.main()
