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

# Each substitution must hit exactly once unless explicitly marked all=True.
CASES = [
    ("R01", "alias/config readback conflict check removed", REPORT,
     'if known != reading or lookups.setdefault(values["cfg_class"].casefold(), lookup) != lookup:', 'if False:'),
    ("R02", "coherent aliases retained as duplicate evidence rows", REPORT,
     'if known is reading:', 'if True:'),
    ("R03", "proxy inventory slot comparison made exact", REPORT,
     'wanted, light_slots = slot.casefold(), {name.casefold() for name in slot_names}',
     'wanted, light_slots = slot, set(slot_names)'),
    ("R04", "nonfinite vertex guard removed", REPORT,
     'return numbers if all(math.isfinite(number) for number in numbers) else None', 'return numbers'),
    ("R05", "vertex numeric fullmatch weakened to prefix", REPORT,
     '_NUMBER_TEXT.fullmatch(item)', '_NUMBER_TEXT.match(item)'),
    ("R06", "resolution name fullmatch weakened to prefix", REPORT,
     '_RES_LOD_NAME.fullmatch(name)', '_RES_LOD_NAME.match(name)', True),
    ("R07", "per-row/host LOD list flag agreement removed", REPORT,
     'or listed != lod["list_ok"]:', ':'),
    ("R08", "legacy positive flag empty-selection guard removed", REPORT,
     'if not values["selection"]:', 'if False:'),
    ("R09", "legacy/top-level mapping agreement removed", REPORT,
     'if known is not None and (known[0] is not True or known[1] is MISSING',
     'if False and (known[0] is not True or known[1] is MISSING'),
    ("R10", "base attempt overwritten by evaluated attempt", REPORT,
     '"base_attempt": _attempt_record(attempt),', '"base_attempt": _attempt_record(evaluated),'),
    ("R11", "prerequisite handguard readback identity guard removed", REPORT,
     'if attached and not (found == label == PREREQUISITE_HANDGUARDS.get(slot) and rail):', 'if False:'),
    ("R12", "proxy model-path equality guard removed", REPORT,
     'if not item["cfg_exists"] or _path(item["model"]) != item["path"]:', 'if not item["cfg_exists"]:'),
    ("R13", "observed beam-point absence ignored", REPORT,
     'if attempt["beam"] is False:', 'if False:'),
    ("P01", "null resolution LOD guard removed", PROBE,
     'if (scanLod)\n', 'if (true)\n'),
    ("P02", "native resolution selection count replaced by zero", PROBE,
     'nativeCount = scanLod.GetSelectionCount();', 'nativeCount = 0;'),
    ("P03", "per-LOD count bound raised from 16 to 128", PROBE,
     'countIndex < lodTotal && countIndex < 16', 'countIndex < lodTotal && countIndex < 128'),
    ("P04", "LOD vertex-index guard removed", PROBE,
     ' && scanSelection.GetLODVertexIndex(0) != -1', ''),
    ("P05", "selection vertex-count guard removed", PROBE,
     ' && scanSelection.GetVertexCount() > 0', ''),
    ("P06", "proxy bone queries no longer filtered by slot", PROBE,
     ' && HCTLProxyHoldsSlot(listedName, m_HCTLSlots.Get(slotIndex))', ''),
    ("P07", "firearm control gains inventory spawn flag", PROBE,
     'int controlFlags = ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;',
     'int controlFlags = ECE_IN_INVENTORY | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;'),
    ("P08", "bone object identity comparison reduced to presence", PROBE,
     'if (boneObject == attached)', 'if (boneObject)'),
    ("P09", "variant-host proxy bone refresh removed", PROBE,
     '                HCTLSlotBones(variantHost);', ''),
    ("P10", "firearm control immediate release removed", PROBE,
     '        HCTLReleaseAll();\n        return controlText;', '        return controlText;'),
    ("P11", "explicit numeric ToString removed from JSON output", PROBE,
     'proxyTried.ToString()', 'proxyTried'),
]


def run(case):
    ident, description, source, before, after, *all_matches = case
    directory = OUT / "mutants" / ident
    directory.mkdir(parents=True, exist_ok=True)
    original = source.read_text()
    count = original.count(before)
    assert count > 0 and (all_matches or count == 1), (ident, count)
    mutated = original.replace(before, after)
    if ident == 'R03':
        mutated = mutated.replace('listed = {name.casefold() for name in item["inventory_slots"]}',
                                  'listed = set(item["inventory_slots"])')
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(run, CASES))
    (OUT / "mutation-results.json").write_text(json.dumps(records, indent=2) + "\n")
