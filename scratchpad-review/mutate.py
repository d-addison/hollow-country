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
MUTATIONS = [
    ("M1_disable_duration_check", PROBE, "if (elapsedMs > m_HCWPCapMs)", "if (false)"),
    ("M2_disable_existing_output_refusal", PROBE,
     "if (FileExist(m_HCWPOutput) || FileExist(m_HCWPSentinel))", "if (false)"),
    ("M3_write_sentinel_before_end_record", PROBE,
     'HCWPAppend(HCWPEndLine(outcome));\n        HCWPWriteSentinel(outcome);',
     'HCWPWriteSentinel(outcome);\n        HCWPAppend(HCWPEndLine(outcome));'),
    ("M4_swap_actual_and_forecast_getters", PROBE,
     'HCWPKey("actual") + HCWPFloat(phenomenon.GetActual()) + "," + HCWPKey("forecast") + HCWPFloat(phenomenon.GetForecast())',
     'HCWPKey("actual") + HCWPFloat(phenomenon.GetForecast()) + "," + HCWPKey("forecast") + HCWPFloat(phenomenon.GetActual())'),
    ("M5_disable_watchdog_finish", PROBE,
     'HCWPFinish("partial");\n    }\n\n    void HCWPFinish',
     'return;\n    }\n\n    void HCWPFinish'),
    ("M6_schedule_samples_without_interval", PROBE,
     'CallLater(HCWPStep, m_HCWPIntervalMs, false)', 'CallLater(HCWPStep, 0, false)'),
    ("M7_remove_duplicate_seq_guard", REPORT, 'if seq in seen:', 'if False:'),
    ("M8_ignore_sentinel", REPORT, 'if sentinel is not _NOT_CHECKED:', 'if False:'),
]

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
(HERE / "mutation-results.json").write_text(json.dumps(results, indent=2) + "\n")
