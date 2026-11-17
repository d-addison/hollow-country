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
    ("M03", "review M03: casefolded implicated slot names", REPORT,
     'return conflict is not None and (conflict["all"] or slot in conflict["slots"])',
     'return conflict is not None and (conflict["all"] or slot.casefold() in {name.casefold() for name in conflict["slots"]})'),
    ("M08", "review M08: case-sensitive config class identity", REPORT,
     'klass = values["cfg_class"].casefold()', 'klass = values["cfg_class"]'),
    ("X1", "implicated reads the conflict only for kind ok (round 9)", REPORT,
     'conflict = proxies[4]       # whatever', 'conflict = proxies[4] if proxies[0] == "ok" else None       # whatever'),
    ("X2", "malformed kind drops the conflict", REPORT,
     'return (kind, [], False, None, found)', 'return (kind, [], False, None, None)'),
    ("X3", "legacy mismatch kind drops the conflict", REPORT,
     '    kind = "malformed" if malformed else "mismatch" if mismatch else "ok"\n',
     '    kind = "malformed" if malformed else "mismatch" if mismatch else "ok"\n    found = None if kind == "mismatch" else found\n'),
    ("X4", "host reason only for kind ok", REPORT,
     '    if proxies[4] is not None:\n        reasons.add("proxy_alias_conflict")',
     '    if proxies[0] == "ok" and proxies[4] is not None:\n        reasons.add("proxy_alias_conflict")'),
    ("X5", "generic malformed checked before the implicated conflict", REPORT,
     '    if _implicated(proxies, slot):\n        return {"source": "pending", "detail": "proxy_evidence_malformed", "conflict": True}\n    if proxies[0] == "malformed":\n        return {"source": "pending", "detail": "proxy_evidence_malformed", "conflict": False}\n',
     '    if proxies[0] == "malformed":\n        return {"source": "pending", "detail": "proxy_evidence_malformed", "conflict": False}\n    if _implicated(proxies, slot):\n        return {"source": "pending", "detail": "proxy_evidence_malformed", "conflict": True}\n'),
    ("X6", "raw model path in the comparison signature", REPORT,
     'lookup = (values["cfg_exists"], _path(values["model"]),', 'lookup = (values["cfg_exists"], values["model"],'),
    ("X7", "raw resolution selection in the comparison signature", REPORT,
     '_selection_key(item["selection"]), item["vertex_ok"]', 'item["selection"], item["vertex_ok"]'),
    ("X8", "resolution selection key drops the instance number", REPORT,
     'return name if name else selection', 'return name[0] if name else selection'),
    ("X9", "unreadable sibling stops the scan", REPORT,
     '            malformed = True       # unreadable: it gives no row, but its readable siblings still answer for themselves\n            continue',
     '            malformed = True\n            break'),
    ("X10", "legacy-class mismatch sibling stops the scan", REPORT,
     '            mismatch = True       # the earlier producer', '            mismatch = True\n            break       # the earlier producer'),
    ("X11", "non-legacy class mismatch sibling stops the scan", REPORT,
     '                malformed = True\n                continue', '                malformed = True\n                break'),
    ("X12", "model path signature drops the basename", REPORT,
     '_path(values["model"]),', '_path(values["model"]).rsplit("/", 1)[0],'),
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
    (OUT / "mutation-results.json").write_text(json.dumps(records, indent=2) + "\n")
