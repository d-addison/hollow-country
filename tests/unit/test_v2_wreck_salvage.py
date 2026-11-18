"""One synthetic journal smoke; authored debit, fake disk port, no DayZ proof.

Actual RED before source existed: AssertionError: False is not true : missing
finite wreck salvage implementation. GREEN: Ran 1 test / OK.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import EArray, translate

SOURCE = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c'


class WreckSalvageSmoke(unittest.TestCase):
    def test_finite_budget_stays_empty_after_reload(self):
        self.assertTrue(SOURCE.is_file(), 'missing finite wreck salvage implementation')
        with TemporaryDirectory(prefix='hc-synthetic-wreck-') as folder:
            journal = Path(folder) / 'wreck-salvage.json'
            # Explicit synthetic seeded three-part wreck; Save is a fake native port.
            module = N(m_Active=True, m_State=N(Rows=EArray([N(Left=3)])))

            def save():
                journal.write_text(json.dumps({'left': module.m_State.Rows[0].Left}))
                return True

            module.Save = save
            debit = translate(SOURCE.read_text(), 'Debit', {}, 'HCWreckSalvageModule', member=True)
            self.assertEqual([True, True, True, False], [debit(module, 0) for _ in range(4)])
            module = N(m_Active=True, m_State=N(Rows=EArray([
                N(Left=json.loads(journal.read_text())['left'])])), Save=save)
            self.assertEqual(0, module.m_State.Rows[0].Left)
            self.assertFalse(debit(module, 0))


if __name__ == '__main__':
    unittest.main()
