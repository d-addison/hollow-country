"""Confined source mutations; never rewrite production files.

Runs the writer's 22 noise/vision tests against separate authored-source copies.
These are offline Python translations and source checks, not engine execution.
"""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tests.unit import test_v1_native_noise_vision as subject

ORIGINAL = {"VISION": subject.VISION, "NOISE": subject.NOISE, "ACTION": subject.ACTION}
TEXT = {name: path.read_text() for name, path in ORIGINAL.items()}


def once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)


MUTANTS = [
    ("01_zero_floor", "VISION", "if (factor < 0.6)\n            return 0.6;",
     "if (factor < 0.6)\n            return 0.0;"),
    ("02_raise_ceiling", "VISION", "if (factor > 1.3)\n            return 1.3;",
     "if (factor > 1.3)\n            return 13.0;"),
    ("03_noise_either_phase", "NOISE", "return phaseBefore == 0 && phaseAfter == 2;",
     "return phaseBefore == 0 || phaseAfter == 2;"),
    ("04_ignore_clock", "VISION", "float nightness = Nightness(hour);",
     "float nightness = Nightness(12.0);"),
    ("05_force_admission", "VISION", "return s_OptIn;", "return true;"),
    ("06_reverse_vision_server_guard", "VISION", "!GetGame().IsServer()", "GetGame().IsServer()"),
    ("07_ignore_headgear", "VISION",
     'if (LitItem(ItemBase.Cast(player.FindAttachmentBySlotName("Headgear"))))',
     'if (false && LitItem(ItemBase.Cast(player.FindAttachmentBySlotName("Headgear"))))'),
    ("08_remove_actual_loop_cap", "VISION", "count = 8;", "count = inventory.AttachmentCount();"),
    ("09_discard_computed_factor", "VISION", "return nativeRange * factor;",
     "factor = 1.0;\n        return nativeRange * factor;"),
    ("10_reverse_noise_server_guard", "NOISE", "!GetGame().IsServer()", "GetGame().IsServer()"),
    ("11_notify_before_commit", "ACTION",
     "if (module) module.CommitSearch(action_data);\n        // One native AI noise only if this commit completed the search.\n        HCSearchNoise.OnCommitted(action_data, phaseBefore);",
     "HCSearchNoise.OnCommitted(action_data, phaseBefore);\n        if (module) module.CommitSearch(action_data);"),
    ("12_lights_always_unlit", "VISION", "if (item.IsLightSource())\n            return item.IsIgnited();",
     "if (item.IsLightSource())\n            return false;"),
]


def run_case(name, changed=None, old=None, new=None):
    folder = OUT / "mutants" / name
    folder.mkdir(parents=True, exist_ok=True)
    for key, path in ORIGINAL.items():
        content = TEXT[key]
        if key == changed:
            content = once(content, old, new)
        copy = folder / path.name
        copy.write_text(content)
        setattr(subject, key, copy)
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(subject)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (folder / "tests.log").write_text(log.getvalue())
    row = {"name": name, "status": "SURVIVED" if result.wasSuccessful() else "KILLED",
           "tests": result.testsRun,
           "failures": [test.id() for test, _ in result.failures],
           "errors": [test.id() for test, _ in result.errors]}
    return row


if __name__ == "__main__":
    baseline = run_case("00_baseline")
    assert baseline["status"] == "SURVIVED", baseline
    results = [run_case(*mutant) for mutant in MUTANTS]
    (OUT / "mutation-results.json").write_text(json.dumps(results, indent=2) + "\n")
    for row in results:
        print(row["name"], row["status"], "failures=", len(row["failures"]), "errors=", len(row["errors"]))
