"""Reviewer-only behavioral regressions; no production code or source mutations."""
import copy
import os
from pathlib import Path
import tempfile
import unittest

from tests.unit.test_gameplay_delta import committed, synthetic_source
from tools.package import gameplay

HERE = Path(__file__).resolve().parent


class BatchBReviewRegressions(unittest.TestCase):
    def test_rollback_refuses_hardlinked_temporary_file_without_touching_outside_file(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as directory:
            root = Path(directory)
            mission = root / 'mission'
            synthetic_source(mission)
            profile, preset = committed()
            stage = root / 'stage'
            gameplay.write_delta(stage, gameplay.generate(mission, profile, preset))
            gameplay.install(stage, mission)
            outside = root / 'outside-mission.txt'
            outside.write_bytes(b'UNRELATED OPERATOR DATA\n')
            os.link(outside, mission / gameplay.MANAGED / 'cfggameplay.next')
            errors = []
            try:
                gameplay.rollback(mission)
            except ValueError as error:
                errors.append(str(error))
            self.assertEqual(outside.read_bytes(), b'UNRELATED OPERATOR DATA\n',
                             'rollback overwrote an inode outside the mission')
            self.assertTrue(errors, 'rollback must refuse the unexpected hard link')

    def test_clothing_health_stays_at_or_below_native_worn_cutoff(self):
        # Object.c GetHealthLevelValue documents max health for each level;
        # constants.c DAMAGE_WORN_VALUE = 0.7, also present in native clothing configs.
        _, preset = committed()
        for slot in preset['attachmentSlotItemSets']:
            for item in slot['discreteItemSets']:
                self.assertLessEqual(item['attributes']['healthMax'], 0.7, item['itemType'])

    def test_hardscrabble_validator_refuses_a_native_weapon_class(self):
        _, preset = committed()
        fixture = copy.deepcopy(preset)
        fixture['discreteUnsortedItemSets'] = [{
            'name': 'M4A1', 'spawnWeight': 1,
            'simpleChildrenTypes': ['M4A1'],
            'simpleChildrenUseDefaultAttributes': True,
        }]
        with self.assertRaises(ValueError):
            gameplay.validate_preset(fixture)


if __name__ == '__main__':
    unittest.main()
