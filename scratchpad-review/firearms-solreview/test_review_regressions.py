"""Review-only behavioral regressions; all fixtures are synthetic and stay here.

These tests do not modify production source and do not establish DayZ behavior.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from tests.unit.test_firearms_roster import entry, synthetic as synthetic_mission
from tests.unit.test_snafu_optional import GOOD, allowlist, build_install
from tools.package import firearms, snafu_optional


class RollbackRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        workshop = self.root / 'synthetic-workshop'
        build_install(workshop)
        self.mission = self.root / 'mission'
        self.mission.mkdir()
        synthetic_mission(self.mission)
        allow = allowlist(*GOOD)
        report = snafu_optional.verify_install(workshop, allow)
        stage = self.root / 'delta'
        snafu_optional.write_delta(stage, snafu_optional.generate(self.mission, allow, report))
        snafu_optional.install(stage, self.mission)
        self.managed = self.mission / snafu_optional.MANAGED

    def test_rollback_must_not_overwrite_a_hardlinked_file_outside_mission(self):
        outside = self.root / 'operator-file-outside-mission.txt'
        marker = b'operator data: preserve exactly\n'
        outside.write_bytes(marker)
        os.link(outside, self.managed / 'core.next')
        try:
            snafu_optional.rollback(self.mission)
        except ValueError:
            self.assertEqual(outside.read_bytes(), marker)
            return
        self.assertEqual(outside.read_bytes(), marker,
                         'rollback wrote through core.next into a file outside the mission')
        self.fail('rollback accepted drift instead of refusing the hardlinked core.next')

    def test_rollback_must_refuse_changed_verification_receipt(self):
        core_before = (self.mission / 'cfgeconomycore.xml').read_bytes()
        evidence = self.managed / 'verification.json'
        evidence.write_bytes(b'{"status":"unverified","operator_note":"preserve"}\n')
        with self.assertRaises(ValueError, msg='rollback must check verification_sha256'):
            snafu_optional.rollback(self.mission)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_bytes(), core_before)
        self.assertTrue(evidence.exists())


class DataminedAcceptance(unittest.TestCase):
    def test_default_delta_does_not_activate_unaccepted_unused_vanilla(self):
        # Explicit synthetic stock: these three zero-nominal classes match the
        # installed Chernarus stock/census classification, not an engine trial.
        unused = {'LeeEnfield', 'MP18', 'Luger'}
        roster = json.loads(firearms.ROSTER_PATH.read_bytes())
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            mission = Path(tmp)
            synthetic_mission(mission)
            rows = [entry(e['class'], 0 if e['class'] in unused else 20,
                          0 if e['class'] in unused else 10, 14400, 0,
                          ['Town'], []) for e in roster['entries']]
            (mission / 'db/types.xml').write_text('<types>' + ''.join(rows) + '</types>')
            usages = {'Town'} | {u for e in roster['entries'] for u in e.get('add_usage', [])}
            values = {'Tier1', 'Tier2', 'Tier3', 'Tier4'}
            (mission / 'cfglimitsdefinition.xml').write_text(
                '<lists><usageflags>' + ''.join(f'<usage name="{u}"/>' for u in sorted(usages))
                + '</usageflags><valueflags>'
                + ''.join(f'<value name="{v}"/>' for v in sorted(values))
                + '</valueflags></lists>')
            delta = firearms.generate(mission, roster)
            import xml.etree.ElementTree as ET
            activated = {t.get('name') for t in ET.fromstring(delta['ce/types.xml'])
                         if t.get('name') in unused and int(t.findtext('nominal')) > 0}
            self.assertEqual(activated, set(),
                             'unused vanilla weapons need local acceptance before activation')


if __name__ == '__main__':
    unittest.main()
