"""Mutate scratch sources and execute the existing offline tests, without repository edits."""
import contextlib
import importlib
import io
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'source-copy'
sys.path.insert(0, str(SOURCE))
from tools.setup import interior_sampler as sampler
from tools.audit import interior_points as points
from tests.unit import test_interior_sampler as sampler_tests
from tests.unit import test_interior_points as points_tests

KNOWN = 'test_plan_satisfies_every_field_the_unchanged_launcher_checks'
META = 'test_every_mutated_condition_is_detected'
MODULES = (sampler_tests, points_tests)
ORIGINALS = {m: Path(m.__file__).read_text() for m in (sampler, points)}
CASES = [
    ('control-self-loop', sampler,
     'if (HCProbePath(entranceSampled, m_HCProbeSampled) < 1)',
     'if (HCProbePath(m_HCProbeSampled, m_HCProbeSampled) < 1)'),
    ('path-gap-tightened-to-5cm', sampler, 'if (gap <= 2.0)', 'if (gap <= 0.05)'),
    ('path-gap-check-disabled', sampler, 'if (gap <= 2.0)', 'if (true)'),
    ('mesh-altitude-check-disabled', sampler,
     'if (Math.AbsFloat(m_HCProbeSampled[1] - floorPos[1]) > 0.75)', 'if (false)'),
    ('nonowner-clearance-skip-50cm', sampler, 'startY = hitY + 0.05;', 'startY = hitY + 0.5;'),
    ('floor-owner-check-disabled', sampler, 'if (hitObjects.Find(m_HCProbeBuilding) == -1)', 'if (false)'),
    ('path-budget-disabled', sampler, 'if (m_HCProbeBuildingPaths >= m_HCProbePathLimit)', 'if (false)'),
    ('barracks-calibration-omitted', points, 'for name in CALIBRATION_CLASSES:', 'for name in CALIBRATION_CLASSES[:1]:'),
    ('calibration-never-refuses', points, 'if coverage < min_calibration - EPSILON:', 'if False:'),
    ('clearance-picks-highest-floor-first', points,
     '(clearance, y) > (best[key][1], best[key][0])', '(y, clearance) > (best[key][0], best[key][1])'),
    ('height-average-replaced-by-first', points,
     'sum(v[0] for v in values) / len(values)', 'values[0][0]'),
    ('reach-filter-disabled', points,
     'and (reach_mode != "known" or c["reachable"] is True)', 'and True'),
    ('lootmax-floor-instead-of-ceil', points, 'math.ceil(count * loot_ratio - EPSILON)', 'math.floor(count * loot_ratio + EPSILON)'),
    ('byte-preservation-verification-disabled', points,
     'if _outside_groups(stock, edited) != _outside_groups(output, edited):', 'if False:'),
    ('stock-point-refusal-disabled', points,
     'group.get("lootmax") != "0" or group.findall(".//point") or len(containers) != 1',
     'group.get("lootmax") != "0" or False or len(containers) != 1'),
]

def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test

def run(label, include_meta):
    loaded = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in MODULES)
    suite = unittest.TestSuite(t for t in flatten(loaded)
                              if not t.id().endswith(KNOWN) and (include_meta or not t.id().endswith(META)))
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=1).run(suite)
    (HERE / 'mutations' / (label + ('.full' if include_meta else '.behavioral') + '.log')).write_text(log.getvalue())
    failures = [t.id().rsplit('.', 1)[-1] for t, _ in result.errors + result.failures]
    return result.testsRun, failures

(HERE / 'mutations').mkdir(exist_ok=True)
count, failures = run('baseline', True)
print('BASELINE:', count, 'tests;', len(failures), 'failures/errors', flush=True)
if failures:
    raise SystemExit(failures)
for label, module, old, new in CASES:
    if len(sys.argv) > 1 and label not in sys.argv[1:]:
        continue
    original = ORIGINALS[module]
    assert original.count(old) == 1, (label, original.count(old))
    path = HERE / 'mutations' / (label + '.py')
    path.write_text(original.replace(old, new, 1))
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    count, failures = run(label, True)
    print(label + ':', 'SURVIVED' if not failures else 'KILLED',
          f'({count} tests)', ', '.join(failures), flush=True)
    if failures and all(name.startswith(META) for name in failures):
        count, behavioral_failures = run(label, False)
        print('  behavioral:', 'SURVIVED' if not behavioral_failures else 'KILLED',
              f'({count} tests)', ', '.join(behavioral_failures), flush=True)
    exec(compile(original, module.__file__, 'exec'), module.__dict__)
