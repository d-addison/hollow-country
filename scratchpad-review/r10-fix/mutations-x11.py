"""Run real unit suites with one scratch module mutation per subprocess."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REPORT = ROOT / "tools/audit/taped_light_report.py"
PROBE = ROOT / "tools/setup/taped_light_probe.py"

CHILD = '''import importlib.util, sys, unittest
import tools.audit, tools.setup
name, path = sys.argv[1:3]
spec = importlib.util.spec_from_file_location(name, path)
mod = importlib.util.module_from_spec(spec)
sys.modules[name] = mod
spec.loader.exec_module(mod)
package, attr = name.rsplit('.', 1)
setattr(sys.modules[package], attr, mod)
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'tests.unit.test_taped_light_report', 'tests.unit.test_taped_light_probe'])
def leaves(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from leaves(test)
        elif '.CliTests.' not in test.id() and '.StagerTests.' not in test.id():
            yield test
suite = unittest.TestSuite(leaves(suite))
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
'''

CASES = [
    ("X11", "non-legacy class mismatch sibling stops the scan", REPORT,
     '                malformed = True\n                continue', '                malformed = True\n                break'),
]


def run(case):
    ident, description, source, before, after, *all_matches = case
    directory = OUT / "mutants" / ident
    directory.mkdir(parents=True, exist_ok=True)
    original = source.read_text()
    count = original.count(before)
    assert count > 0 and (all_matches or count == 1), (ident, count)
    mutated = original.replace(before, after)
    target = directory / source.name
    target.write_text(mutated)
    module = "tools.audit.taped_light_report" if source == REPORT else "tools.setup.taped_light_probe"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT), TMPDIR=str(directory))
    result = subprocess.run([sys.executable, "-c", CHILD, module, str(target)], cwd=ROOT,
                            env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    (directory / "output.txt").write_text(result.stdout)
    record = dict(id=ident, description=description, result="KILLED" if result.returncode else "SURVIVED",
                  returncode=result.returncode, replacements=count,
                  summary=[line for line in result.stdout.splitlines()
                           if line.startswith(("Ran ", "FAILED", "OK", "FAIL:", "ERROR:"))])
    print(json.dumps(record), flush=True)
    return record


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(run, CASES))
    (OUT / "mutation-results-x11.json").write_text(json.dumps(records, indent=2) + "\n")
