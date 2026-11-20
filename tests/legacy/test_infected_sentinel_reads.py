"""Wave 8 infvar: loaded journal keys, using explicit native-zero JSON ports.

Trace: .banso-writer/inputs/task.md #173 -> bounded LoadSlot presence refusal.
The shared spec/plan/tasks paths are absent; HC-11 owns central trace updates.
Executes authored store/validation methods; no parallel gameplay/recovery model.
Offline tests establish no DayZ parser, persistence or recovery acceptance.
Actual RED command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_infected_sentinel_reads -v
AssertionError: True is not false : missing horde key accepted: Living
Additional boundary RED: missing snapshot reservation accepted as zero
GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_postures test_infected_sentinel_reads -v
Ran 3 tests; OK. Explicit zero Living/empty snapshot reservations remain valid;
each row requires its own keys; refusal preserves bytes and logs a named reason.
Existing numeric validators already reject zero Reserved/AdoptionStage, unlike
Living. The load-boundary guard now distinguishes absence explicitly for all.
No new distance, store protocol, recovery capability or gameplay controller.
"""
import copy
import json
import unittest

from tests.legacy.test_infected_admission import prepared_record
from tests.legacy.test_v1_combined_restart import InfectedFiles, encode


class HordeSentinelReads(unittest.TestCase):
    def test_each_loaded_row_requires_keys_and_keeps_explicit_zero_living(self):
        store = InfectedFiles()  # explicit synthetic in-memory byte store
        path = store.paths[0]
        complete = json.loads(store.files[path])
        complete['Groups'].append(json.loads(encode(prepared_record(record_id=2))))
        complete['Reserved'] = 6
        def load(document):
            store.files[path] = json.dumps(document)
            return store.owner.LoadSlot(path, None, 'synthetic_world', 24, 2, 101)[0]
        self.assertTrue(load(complete))
        empty = copy.deepcopy(complete)
        empty['Groups'] = []
        empty['Reserved'] = 0
        self.assertTrue(load(empty))
        del empty['Reserved']
        self.assertFalse(load(empty), 'missing snapshot reservation accepted as zero')
        explicit_zero = copy.deepcopy(complete)
        explicit_zero['Groups'][1]['Living'] = 0
        self.assertTrue(load(explicit_zero), 'explicit zero living is valid spent evidence')
        for field in ('Living', 'Reserved', 'AdoptionStage'):
            with self.subTest(field=field):
                missing = copy.deepcopy(complete)
                del missing['Groups'][1][field]
                before = json.dumps(missing)
                self.assertFalse(load(missing), 'missing horde key accepted: ' + field)
                self.assertEqual(before, store.files[path], 'refusal rewrote journal bytes')
        # A nested lookalike or a first-row key cannot satisfy the second row.
        missing = copy.deepcopy(complete)
        del missing['Groups'][1]['Living']
        missing['Groups'][1]['Untrusted'] = {'Living': 0}
        self.assertFalse(load(missing))
        self.assertTrue(load(complete))
        store.files[path] = store.files[path].replace('"Living"', '"\\u004civing"')
        self.assertTrue(store.owner.LoadSlot(path, None, 'synthetic_world', 24, 2, 101)[0])
        self.assertTrue(any('missing_horde_sentinel_fields' in line for line in store.logs))


if __name__ == '__main__':
    unittest.main()
