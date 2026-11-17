"""Execute existing B04 BDD bindings only; never claim runtime acceptance."""
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'isolated-source'
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from tools.validate import bdd

scenarios = bdd.parse_scenarios((ROOT / 'tests/features/offline.feature').read_text())
assert {name for name, _ in scenarios} == set(bdd.BINDINGS)
for name, steps in scenarios:
    assert steps == bdd.BINDINGS[name][0], name
patterns = {'test_infected_contract.py', 'test_infected_completion.py',
            'test_infected_persistence.py', 'test_infected_routes.py',
            'test_infected_wave.py', 'test_infected_death_probe.py',
            'test_death_selection_probe.py', 'test_room_catalog_completion.py',
            'test_observer_transition.py'}
suite = unittest.TestSuite()
for name, _ in scenarios:
    pattern = bdd.BINDINGS[name][1]
    if pattern in patterns:
        print('BOUND: ' + name + ' -> ' + pattern, flush=True)
        suite.addTests(unittest.defaultTestLoader.discover('tests/unit', pattern=pattern))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print('B04 focused bindings only; runtime acceptance: NOT EXECUTED')
sys.exit(not result.wasSuccessful())
