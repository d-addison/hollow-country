"""settings_consistency has one size rule: json_loader_caps (no duplicate profile-size warning)."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from tools.validate import json_loader_caps, settings_consistency as sc


def run_main(caps_result):
    output = io.StringIO()
    with patch.object(sc, 'load_targets'), patch.object(sc, 'check_consistency', return_value=[]), \
            patch.object(sc, 'check_profile_mirrors', return_value=[]), \
            patch.object(json_loader_caps, 'check', return_value=caps_result) as caps, \
            patch('sys.argv', ['settings_consistency']), redirect_stdout(output):
        failed = sc.main()
    return failed, json.loads(output.getvalue()), caps


class SettingsSizeRuleTests(unittest.TestCase):
    def test_duplicate_profile_size_check_is_gone(self):
        self.assertFalse(hasattr(sc, 'check_profile_default_sizes'))

    def test_loader_cap_error_fails_the_gate(self):
        failed, report, caps = run_main((['json loader cap path=x reason=above_limit'], 1))
        self.assertTrue(failed)
        self.assertEqual('fail', report['status'])
        self.assertEqual(['json loader cap path=x reason=above_limit'], report['errors'])
        caps.assert_called_once()

    def test_clean_loader_caps_pass_without_a_second_warning_tier(self):
        failed, report, _ = run_main(([], 1))
        self.assertFalse(failed)
        self.assertEqual('pass', report['status'])
        self.assertNotIn('warnings', report)

    def test_loader_caps_cover_everything_the_retired_check_covered(self):
        covered = json_loader_caps.loader_caps()
        for default in sc.ROOT.glob('mods/*/data/defaults/**/*'):
            if default.is_file():
                self.assertIn(default.relative_to(sc.ROOT).as_posix(), covered)
        for source, _copy in sc.PROFILE_MIRRORS:
            self.assertIn(source, covered)


if __name__ == '__main__':
    unittest.main()
