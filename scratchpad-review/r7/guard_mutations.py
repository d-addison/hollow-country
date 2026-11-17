"""State exact replacements for the claimed equivalent guards, then test them.

Named worker mutant bodies were not supplied. These explicit alternatives avoid
inferring equivalence from a surviving mutation alone. No checkout file changes.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
import tempfile

ROOT = Path(__file__).resolve().parent
tempfile.tempdir = str(ROOT / "tmp")
sys.path.insert(0, str(ROOT/'head'))
from tools.audit import taped_light_report as original
from tests.unit import test_taped_light_report as f

source = Path(original.__file__).read_text()
mutations = (
    ("not_dot_removed", "not dot or not number or", "not number or"),
    ("not_number_removed", "not dot or not number or", "not dot or"),
    ("raw_trailing_slash_guard_removed", " or stem.endswith(\"/\")", ""),
    ("normalized_empty_basename_guard_removed", ' or not path.rsplit("/", 1)[-1]', ""),
)

def slot(module, item):
    row = f.row("AK74", "slot_host", f.gun_slots(weapon_model=False), f.good_gun_lights(), proxies=[item])
    result = module.build_report(f.classification([f.host("AK74", "slot_host")]), f.observations([row]))
    value = result["hosts"][0]["lights"]["UniversalLight"]["slots"]["weaponFlashlight"]
    return value["verdict"], value["reason"]

cases = {
    "empty_suffix_with_coherent_config": f.proxy(number=""),
    "empty_basename_with_coherent_config": dict(f.proxy(path="/dz/weapons/attachments/light"),
                                                  selection="proxy:/dz/weapons/attachments/light/.001"),
}
for name, before, after in mutations:
    assert source.count(before) == 1, (name, source.count(before))
    module = types.ModuleType("tools.audit.review_guard_mutant")
    module.__file__ = original.__file__
    exec(compile(source.replace(before, after), str(ROOT / (name + ".py")), "exec"), module.__dict__)
    f.report = module
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log).run(unittest.defaultTestLoader.loadTestsFromModule(f))
    (ROOT / (name + ".log")).write_text(log.getvalue())
    print(json.dumps({"mutation": name, "before": before, "after": after,
                      "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "cases": {label: {"baseline": slot(original, item), "mutant": slot(module, item)}
                                for label, item in cases.items()}}, sort_keys=True), flush=True)
f.report = original

# Exhaustively compare the two apparently redundant guards over this small alphabet;
# the source arguments below establish the full equivalence, not finite fuzzing.
import itertools
for name, before, after in (mutations[0], mutations[3]):
    module = types.ModuleType("tools.audit.review_guard_fuzz")
    exec(compile(source.replace(before, after), name, "exec"), module.__dict__)
    differences, checked = [], 0
    for size in range(6):
        for chars in itertools.product("a/\\.01", repeat=size):
            selection = "proxy:" + "".join(chars)
            checked += 1
            if original._proxy_name(selection) != module._proxy_name(selection):
                differences.append(selection)
    print(json.dumps({"equivalence_check": name, "checked": checked, "differences": differences}))
