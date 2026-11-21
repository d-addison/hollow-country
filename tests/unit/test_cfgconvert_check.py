"""Fake native processes; these tests establish tooling behaviour only."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.setup.winproc import InteropError, Result
from tools.validate import cfgconvert_check as gate


class ConfigGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'mods/Test/config.cpp'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('class CfgPatches {};')
        self.tool = self.root / 'CfgConvert.exe'
        self.tool.touch()

    def run_gate(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = gate.main(['--root', str(self.root), '--tool', str(self.tool)])
        return code, out.getvalue()

    def test_discovery_selects_addon_for_header_and_model(self):
        model = self.source.with_name('model.cfg')
        model.touch()
        self.source.with_name('mod.cpp').touch()
        self.source.with_name('include.hpp').touch()
        self.assertEqual({self.source, model}, set(gate.discover(self.root)))
        self.assertEqual({self.source, model}, set(gate.discover(self.root, ['mods/Test/include.hpp'])))
        self.assertEqual([], gate.discover(self.root, ['mods/Other/config.cpp']))
        self.assertEqual({self.source, model}, set(gate.discover(self.root, ['tools/package/pbo.py'])))

    def test_unavailable_is_distinct_from_pass_and_error(self):
        self.tool.unlink()
        self.assertEqual(gate.SKIPPED, self.run_gate()[0])
        self.tool.touch()
        with patch.object(gate, 'convert', side_effect=InteropError()):
            self.assertEqual(gate.SKIPPED, self.run_gate()[0])
        with patch.object(gate, 'convert', return_value=(False, 'syntax error line 9')):
            code, output = self.run_gate()
        self.assertEqual(1, code)
        self.assertIn('mods/Test/config.cpp:9:', output)

    def test_native_receipt_required_and_failure_output_overrides_it(self):
        with patch.object(gate, 'windows_path', side_effect=lambda p: str(p)), patch.object(gate.winproc, 'run') as run:
            for receipt, expected in [('HC_CFG_RESULT=0:True', True),
                                      ('HC_CFG_RESULT=1:True', False),
                                      ('HC_CFG_RESULT=0:False', False), ('', False),
                                      ('syntax error\nHC_CFG_RESULT=0:True', False)]:
                run.return_value = Result(0, receipt, '', 1)
                self.assertEqual(expected, gate.convert(self.source, self.tool)[0])
            script = run.call_args.args[1][0]
            self.assertIn('-bin -dst', script)
            self.assertIn('Copy-Item', script)
            self.assertNotIn('Kill()', script, 'never force-kill a stalled converter')
            self.assertIn('finally', script)
            self.assertIn('$env:TEMP', script)

    def test_privacy_does_not_change_failure_verdict(self):
        raw = 'Error line 7 C:' + '\\Users\\Example\\secret.cpp\nSteam ID 12345678901234567'
        with patch.object(gate, 'convert', return_value=(False, raw)):
            code, out = self.run_gate()
        self.assertEqual(1, code)
        self.assertNotIn('Example', out)
        self.assertNotIn('12345678901234567', out)
        self.assertIn('mods/Test/config.cpp:7:', out)


if __name__ == '__main__':
    unittest.main()
