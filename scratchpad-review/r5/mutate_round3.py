"""Run targeted mutation checks against only the archived review commit."""
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE / "baseline"
PROBE = "tools/setup/weather_probe.py"
REPORT = "tools/audit/weather_report.py"
MUTATIONS = [('R1_bypass_live_application', 'tools/audit/weather_report.py', 'if not applied:', 'if False:'), ('R2_ignore_stock_differential', 'tools/audit/weather_report.py', 'applied = applied and matches and differs', 'applied = applied and matches'), ('R3_treat_every_attribute', 'tools/audit/weather_report.py', 'return [key for key in _ATTRIBUTES if not _close(stock["xml"][key], candidate["xml"][key])]', 'return list(_ATTRIBUTES)'), ('R4_allow_no_treatment', 'tools/audit/weather_report.py', 'if not any(treated.values()):', 'if False:'), ('R5_crossing_alone_is_cycle', 'tools/audit/weather_report.py', 'return crossed, False', 'return crossed, crossed'), ('R6_ignore_cycle_gate', 'tools/audit/weather_report.py', 'if not candidate["cycle_observed"]:', 'if False:'), ('R7_one_matching_candidate_readback', 'tools/audit/weather_report.py', 'matches = bool(theirs) and all(_close(pair, wanted) for pair in theirs)', 'matches = bool(theirs) and any(_close(pair, wanted) for pair in theirs)'), ('R8_one_different_stock_readback', 'tools/audit/weather_report.py', 'differs = bool(ours) and not any(_close(pair, wanted) for pair in ours)', 'differs = bool(ours) and not all(_close(pair, wanted) for pair in ours)')]

results = []
for name, relative, old, new in MUTATIONS:
    path = BASE / relative
    original = path.read_text()
    if original.count(old) != 1:
        raise RuntimeError((name, "mutation is not unique", original.count(old)))
    mutant = original.replace(old, new)
    try:
        path.write_text(mutant)
        process = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/unit",
                                  "-p", "test_weather*.py", "-v"], cwd=BASE,
                                 env=dict(os.environ, TMPDIR=str(HERE / "tmp"), PYTHONDONTWRITEBYTECODE="1"),
                                 capture_output=True, text=True)
        (HERE / (name + ".log")).write_text(process.stdout + process.stderr)
        (HERE / (name + ".diff")).write_text("".join(difflib.unified_diff(
            original.splitlines(keepends=True), mutant.splitlines(keepends=True),
            fromfile=relative, tofile=relative)))
        result = {"mutation": name, "exit_code": process.returncode,
                  "result": "SURVIVED" if process.returncode == 0 else "KILLED"}
        results.append(result)
        print(json.dumps(result), flush=True)
    finally:
        path.write_text(original)
(HERE / "round3-mutation-results.json").write_text(json.dumps(results, indent=2) + "\n")
