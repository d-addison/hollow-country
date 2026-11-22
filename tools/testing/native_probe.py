"""Diagnostic native probe and subcase adapter (spec 002 AV-T008).

Wraps the existing DayZDiag self-test harness (tools.setup.wine_compile_probe --diagnostic
--diagnostic-selftests) and its settings negatives (--settings-case). It adds what that harness lacks as a
verdict: every requested subcase must print its own exact marker, a missing marker is a rejection, a failed
marker or a stock SCRIPT (E) is never a clean PASS, a negative input passes only its specified
rejection-and-preservation assertions with the errors still listed, and the test hook bytes must be absent
from the normal artifact. Diag evidence is diagnostic-native: it differs from the normal server (an actual
DIAG_DEVELOPER build, a disposable mission, synthetic storage), says so in every verdict, and is never
accepted or inherited from older probe observations.

    python3 -B -m tools.testing.native_probe plan
    python3 -B -m tools.testing.native_probe run --probe core-selftests --tree .
    python3 -B -m tools.testing.native_probe run --probe settings-negatives --tree .
    python3 -B -m tools.testing.native_probe control missing_subcase --tree .
    python3 -B -m tools.testing.native_probe judge evidence.json
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from tools.testing import native_common as common
from tools.testing import native_server as server

ROOT = Path(__file__).resolve().parents[2]
HOLDER = "native_probe"
SELFTEST = re.compile(r"\[HC SelfTest\] name=([a-z][a-z0-9_]{0,59}) pass=(true|false) detail=([^\r\n]*)")
SOURCE_NAME = re.compile(r"""\bReceipt\("([a-z][a-z0-9_]{0,59})",|\[HC SelfTest\] name=([a-z][a-z0-9_]{0,59}) pass=""")
SUBCASE = re.compile(r"[a-z][a-z0-9_-]{0,59}\Z")
SCRIPT_ROOT = "mods/HollowCountry/scripts"
CASE_OPTION = re.compile(r"--settings-case'?,\s*choices=\[([^\]]*)\]")
MAX_SOURCE_FILES = common.MAX_DISCOVERY * 8
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_MARKERS = 2000
PROBE_SECONDS = 90
LAYER = "diagnostic-native"
DIFFERENCES = ("diag_executable_not_normal_server", "disposable_mission_and_synthetic_storage",
               "test_hook_present_only_in_the_disposable_mission", "no_client", "no_signature_or_join")
PROBES = {
    "core-selftests": {"executable": "diagnostic-server", "needs_exe": "DayZDiag_x64.exe",
                       "assertion": "markers"},
    "settings-negatives": {"executable": "dedicated-server", "needs_exe": "DayZServer_x64.exe",
                           "assertion": "rejection"},
}


# --- Discovery (derived from source and the probe tool, never a pinned list) ---------------------

def discover_subcases(root):
    """Self-test names the source can print, in sorted order. Bounded; an overflow is refused."""
    base = Path(root) / SCRIPT_ROOT
    names, seen = set(), 0
    for path in sorted(base.rglob("*.c")):
        seen += 1
        if seen > MAX_SOURCE_FILES:
            raise ValueError("source discovery exceeds the file bound")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "SelfTest" not in text:
            continue
        for match in SOURCE_NAME.finditer(text):
            names.add(match.group(1) or match.group(2))
    return sorted(names)


def settings_cases(root):
    """The --settings-case negatives the probe tool offers, read from its argument definition."""
    text = (Path(root) / "tools/setup/wine_compile_probe.py").read_text(encoding="utf-8")
    match = CASE_OPTION.search(text)
    if not match:
        raise ValueError("probe tool defines no settings cases")
    return [item.strip().strip("'\"") for item in match.group(1).split(",") if item.strip()]


def subcases_for(probe, root):
    if probe == "core-selftests":
        return discover_subcases(root)
    if probe == "settings-negatives":
        return settings_cases(root)
    raise ValueError("unknown probe")


def hook_markers(staging=None):
    """Identifiers the disposable-mission hooks add, derived from the real hook sources."""
    if staging is None:
        from tools.setup import diagnostic_mission as staging
    markers = set()
    for name in dir(staging):
        value = getattr(staging, name)
        if name.endswith("_HOOK") and isinstance(value, bytes):
            markers.update(re.findall(rb"\bclass\s+(HC\w+)", value))
    return sorted(item.decode() for item in markers)


def hook_bytes_in(blob, markers):
    return [marker for marker in markers if marker.encode() in blob]


# --- Parsing and the pure judge ------------------------------------------------------------------

def parse_markers(texts):
    """{name: [(passed, detail)]} from every fresh log text, bounded."""
    found = {}
    count = 0
    for _, text in sorted(texts.items()):
        for match in SELFTEST.finditer(text):
            count += 1
            if count > MAX_MARKERS:
                raise ValueError("marker count exceeds the bound")
            found.setdefault(match.group(1), []).append([match.group(2) == "true", match.group(3)[:200]])
    return found


def judge_subcase(assertion, name, entry):
    """One subcase verdict: PASS, FAIL or MISSING with a reason. Absent evidence is never a pass."""
    if assertion == "markers":
        marks = entry.get("markers") or []
        if not marks:
            return "MISSING", "subcase_never_ran"
        failed = [passed for passed, _ in marks if not passed]
        if failed:
            return "FAIL", "subcase_failed" if len(failed) == len(marks) else "subcase_conflicting"
        return "PASS", "marker_pass"
    status, preserved = entry.get("status"), entry.get("settings_original_preserved")
    if status is None:
        return "MISSING", "subcase_never_ran"
    if status != "settings-rejected":
        return "FAIL", "negative_input_not_rejected"
    if preserved is not True:
        return "FAIL", "original_not_preserved"
    return "PASS", "rejected_and_preserved"


def judge(evidence):
    """Evidence record to a verdict. PASS needs every requested subcase, clean logs and an absent hook."""
    probe = PROBES.get(evidence.get("probe")) if isinstance(evidence, dict) else None
    if probe is None:
        return {"schema": 1, "outcome": "FAIL", "reason": "probe_unknown", "subcases": {}, "layer": LAYER,
                "client_count": 0, "acceptance": "not_accepted", "differences": list(DIFFERENCES)}
    requested = evidence.get("requested")
    entries = evidence.get("subcases")
    problems, subcases = [], {}
    if not isinstance(requested, list) or not requested or not all(
            isinstance(name, str) and SUBCASE.fullmatch(name) for name in requested):
        problems.append("requested_subcases_invalid")
        requested = []
    if not isinstance(entries, dict):
        entries = {}
    for name in requested:
        outcome, reason = judge_subcase(probe["assertion"], name, entries.get(name) or {})
        subcases[name] = {"outcome": outcome, "reason": reason}
        if outcome != "PASS":
            problems.append(reason)
    unrequested = sorted(name for name, entry in entries.items() if name not in requested
                         and any(not passed for passed, _ in (entry.get("markers") or [])))
    if unrequested:
        problems.append("unrequested_selftest_failed")
    logs = evidence.get("logs") or {}
    if evidence.get("client_count") != 0:
        problems.append("client_claim_refused")
    if evidence.get("executable_kind") != probe["executable"]:
        problems.append("wrong_executable_kind")
    if logs.get("rejected") or logs.get("skipped"):
        problems.append("stale_or_unreadable_logs")
    if not logs.get("fresh_files"):
        problems.append("no_fresh_log")
    if logs.get("script_errors"):
        problems.append("script_errors")
    if logs.get("engine_errors") or logs.get("dumps"):
        problems.append("engine_errors")
    if probe["assertion"] == "markers" and "Mission" not in (logs.get("modules") or []):
        problems.append("mission_not_loaded")
    artifact = evidence.get("normal_artifact") or {}
    if not isinstance(artifact.get("hook_bytes"), list):
        problems.append("artifact_not_checked")
    elif artifact["hook_bytes"]:
        problems.append("test_hook_in_normal_artifact")
    cleanup = evidence.get("cleanup") or {}
    if not cleanup.get("observed"):
        problems.append("cleanup_not_observed")
    elif cleanup.get("survivors"):
        problems.append("child_survived_launcher")
    guard = evidence.get("guard") or {}
    if not guard.get("observed"):
        problems.append("guard_not_observed")
    elif guard.get("changed"):
        problems.append("stock_or_server_file_modified")
    outcome = "FAIL" if problems else "PASS"
    return {"schema": 1, "probe": evidence["probe"], "outcome": outcome,
            "reason": "all_subcases_passed" if not problems else problems[0], "problems": problems,
            "subcases": subcases, "unrequested_failures": unrequested,
            "errors": {"script": logs.get("script_errors", 0), "script_lines": logs.get("script_error_lines", []),
                       "engine": logs.get("engine_errors", []), "dumps": logs.get("dumps", 0)},
            "layer": LAYER, "client_count": 0, "acceptance": "not_accepted",
            "differences": list(DIFFERENCES), "synthetic": bool(evidence.get("synthetic"))}


# --- The native run (owner host only) -----------------------------------------------------------

def boot_argv(probe, case, experiment, stage_pbo, server_root, prefix, seconds):
    argv = [sys.executable, "-B", "-m", "tools.setup.wine_compile_probe", "--server-root", str(server_root),
            "--pbo", str(stage_pbo), "--experiment", str(experiment), "--prefix", str(prefix),
            "--seconds", str(seconds)]
    if probe == "core-selftests":
        argv += ["--diagnostic", "--diagnostic-selftests"]
    else:
        argv += ["--settings-case", case]
    return argv


def run_boot(argv, log_path, seconds, *, proc_root="/proc", net_root="/proc/net", popen=subprocess.Popen,
             sleep=time.sleep, clock=time.monotonic, grace=server.CLEANUP_GRACE_SECONDS, port=2402):
    """One owned child boot: sample the ownership ledger, bound the time, then require clean exit."""
    ledger = common.Ledger()
    timed_out = False
    with open(log_path, "wb") as log:
        process = popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = clock() + seconds + server.SETUP_RESERVE_SECONDS
        while process.poll() is None:
            if clock() >= deadline:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                break
            ledger.update(common.scan(proc_root), process.pid)
            sleep(server.SAMPLE_SECONDS)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
    cleanup = server.await_cleanup(ledger, proc_root, net_root, "127.0.0.1", port, grace, sleep, clock)
    return {"returncode": 124 if timed_out else process.returncode, "timed_out": timed_out}, cleanup


def merge_logs(parts):
    merged = {"fresh_files": 0, "rejected": {}, "skipped": {}, "modules": [], "script_errors": 0,
              "script_error_lines": [], "engine_errors": [], "dumps": 0}
    for index, part in enumerate(parts):
        merged["fresh_files"] += part.get("fresh_files", 0)
        merged["rejected"].update({"%d:%s" % (index, key): value for key, value in part.get("rejected", {}).items()})
        merged["skipped"].update({"%d:%s" % (index, key): value for key, value in part.get("skipped", {}).items()})
        merged["modules"] = list(dict.fromkeys(merged["modules"] + part.get("modules", [])))
        merged["script_errors"] += part.get("script_errors", 0)
        merged["script_error_lines"] += part.get("script_error_lines", [])
        merged["engine_errors"] += part.get("engine_errors", [])
        merged["dumps"] += part.get("dumps", 0)
    return merged


def run_probe(tree, out, probe, *, subcases=None, extra=(), commit=None, seconds=PROBE_SECONDS, cache=None,
              lock_path=None, server_root=None, prefix=None, proc_root="/proc", net_root="/proc/net",
              popen=subprocess.Popen, sleep=time.sleep, clock=time.monotonic, grace=server.CLEANUP_GRACE_SECONDS):
    """Run a probe under the shared host lock and return the judged verdict.

    extra names additional subcases to request (a negative control asks for one the source never prints).
    """
    from tools.release import compile_gate
    from tools.release.host_lock import host_lock
    if probe not in PROBES:
        raise ValueError("unknown probe")
    server.refuse_hosted_ci()
    if not 15 <= seconds <= 900:
        raise ValueError("seconds must be 15..900")
    requested = list(subcases) if subcases else subcases_for(probe, tree)
    requested = list(dict.fromkeys(requested + list(extra)))
    if not requested or not all(SUBCASE.fullmatch(name) for name in requested):
        raise ValueError("requested subcases are invalid")
    out = Path(os.path.abspath(out))
    if out.exists():
        raise ValueError("output directory must be fresh")
    cache = Path(cache) if cache else Path.home() / ".cache/hollow-country/compile-gate"
    server_root, prefix, reason = compile_gate.prerequisites(server_root, prefix)
    blocked = {"schema": 1, "probe": probe, "outcome": "BLOCKED", "client_count": 0, "layer": LAYER,
               "acceptance": "not_accepted", "subcases": {}, "differences": list(DIFFERENCES)}
    if reason:
        return dict(blocked, reason="prerequisite_absent", detail=reason)
    exe = PROBES[probe]["needs_exe"]
    if not (Path(server_root) / exe).is_file():
        return dict(blocked, reason="executable_absent", detail=exe + " is not staged in the isolated server")
    with host_lock(HOLDER, lock_path):
        compile_gate.require_client_idle(False)
        pin, blob = server.compute_pin(tree, commit, cache)
        out.mkdir(parents=True)
        stage = common.write_owned(out / "stage", server.PBO_NAME, blob)
        markers = hook_markers()
        files, directories = server.stock_guard_paths(server_root)
        before = common.snapshot_guard(files, directories)
        cases = ["-"] if probe == "core-selftests" else [name for name in requested if name in settings_cases(tree)]
        entries = {name: {} for name in requested}
        parts, exits, cleanups, kind = [], [], [], None
        for case in cases:
            experiment = out / ("exp-" + re.sub(r"[^a-z0-9]", "_", case.lower()))
            started_ns = time.time_ns()
            argv = boot_argv(probe, case, experiment, stage, server_root, prefix, seconds)
            exit_info, cleanup = run_boot(argv, out / ("boot-" + experiment.name[4:] + ".log"), seconds,
                                          proc_root=proc_root, net_root=net_root, popen=popen, sleep=sleep,
                                          clock=clock, grace=grace)
            exits.append(exit_info)
            cleanups.append(cleanup)
            texts, rejected, skipped = server.read_fresh(experiment, started_ns)
            dumps = len(list((experiment / "profiles").glob("ErrorMessage_*.mdmp")))
            parts.append(server.summarize_logs(texts, rejected, skipped, dumps))
            try:
                report = server.read_report(experiment)
            except (OSError, ValueError):
                report = {}
            kind = report.get("executable_kind", kind)
            if probe == "core-selftests":
                for name, marks in parse_markers(texts).items():
                    entries.setdefault(name, {})["markers"] = marks
            else:
                entries[case] = {"status": report.get("status"),
                                 "settings_original_preserved": report.get("settings_original_preserved")}
        after = common.snapshot_guard(files, directories)
        evidence = {"schema": 1, "probe": probe, "requested": requested, "subcases": entries,
                    "executable_kind": kind, "client_count": 0, "logs": merge_logs(parts),
                    "normal_artifact": {"sha256": pin["pbo_sha256"], "hook_bytes": hook_bytes_in(blob, markers),
                                        "markers_checked": len(markers)},
                    "cleanup": {"observed": all(item.get("observed") for item in cleanups),
                                "survivors": [s for item in cleanups for s in item.get("survivors", [])]},
                    "guard": {"observed": True, "changed": common.diff_guard(before, after)},
                    "exits": exits}
        verdict = judge(evidence)
        try:
            common.write_owned(out, "evidence.json", json.dumps(evidence, sort_keys=True, indent=1).encode())
        except (OSError, ValueError):
            pass
        return verdict


def judge_output(returncode, output):
    """Driver judge: PASS only for a terminal diagnostic-native verdict that said PASS and exited 0."""
    from tools.testing import drivers
    if "native_probe: REFUSED" in output:
        return "BLOCKED", "adapter_refused"
    verdict = drivers._json_last(output)
    if verdict is None or verdict.get("client_count") != 0 or verdict.get("acceptance") != "not_accepted":
        return "FAIL", "no_terminal_result"
    if verdict.get("outcome") == "BLOCKED":
        return "BLOCKED", str(verdict.get("reason", "blocked"))[:60]
    if returncode == 0 and verdict.get("outcome") == "PASS":
        return "PASS", "diagnostic_native_pass"
    return "FAIL", str(verdict.get("reason", "nonzero_exit"))[:60]


def drivers_for():
    from tools.testing import drivers

    def build(probe):
        def argv(repo_root, inputs):
            return [sys.executable, "-B", "-m", "tools.testing.native_probe", "run", "--probe", probe,
                    "--tree", str(repo_root)]
        return argv
    return (
        drivers.Driver("native.probe_adapter", "native",
                       "DayZDiag self-test subcase adapter; diagnostic-native layer, never accepted",
                       ("dayzdiag",), build("core-selftests"), judge_output, timeout=1500, memory="12G"),
        drivers.Driver("native.probe_settings", "native",
                       "settings-negative subcase adapter; rejection and preservation only, never accepted",
                       ("normal_server",), build("settings-negatives"), judge_output, timeout=3000, memory="12G"),
    )


# --- Command line ---------------------------------------------------------------------------------

NEVER_PRINTED = "av008_control_never_printed"
CONTROLS = {"missing_subcase": ("subcase_never_ran",
                                "a requested subcase the source never prints is rejected, not passed")}


def plan_report(root=ROOT):
    return {"adapter": "native_probe", "layer": LAYER, "differences": list(DIFFERENCES),
            "probes": {key: {"executable": value["executable"], "assertion": value["assertion"],
                             "subcases": subcases_for(key, root)} for key, value in PROBES.items()},
            "controls": {key: value[1] for key, value in CONTROLS.items()},
            "commands": ["python3 -B -m tools.testing.native_probe run --probe core-selftests --tree .",
                         "python3 -B -m tools.testing.native_probe run --probe settings-negatives --tree .",
                         "python3 -B -m tools.testing.native_probe control missing_subcase --tree ."]}


def _print(verdict):
    print("native_probe: %s reason=%s probe=%s layer=%s" % (verdict["outcome"], verdict.get("reason"),
                                                          verdict.get("probe"), LAYER))
    print(json.dumps(verdict, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    judge_parser = sub.add_parser("judge")
    judge_parser.add_argument("evidence", type=Path)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--probe", choices=sorted(PROBES), required=True)
    control = sub.add_parser("control")
    control.add_argument("control", choices=sorted(CONTROLS))
    for item in (run_parser, control):
        item.add_argument("--tree", type=Path, default=Path.cwd())
        item.add_argument("--commit")
        item.add_argument("--seconds", type=int, default=PROBE_SECONDS)
        item.add_argument("--out", type=Path)
        item.add_argument("--subcase", action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(json.dumps(plan_report(), sort_keys=True, indent=2))
        return 0
    if args.command == "judge":
        try:
            evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        verdict = judge(evidence)
        _print(verdict)
        return 0 if verdict["outcome"] == "PASS" else 1
    out = args.out or Path.home() / ".cache/hollow-country/native-adapter" / ("probe-%d" % time.time_ns())
    probe = args.probe if args.command == "run" else "core-selftests"
    extra = [NEVER_PRINTED] if args.command == "control" else []
    try:
        verdict = run_probe(args.tree, out, probe, subcases=args.subcase or None, extra=extra,
                            commit=args.commit, seconds=args.seconds)
    except Exception as error:  # LockRefused, ValueError and friends: a refusal, not a result
        print("native_probe: REFUSED %s" % server.common_text(error))
        return 1
    if args.command == "run":
        _print(verdict)
        return 0 if verdict["outcome"] == "PASS" else 1
    expected = CONTROLS[args.control][0]
    seen = verdict.get("subcases", {}).get(NEVER_PRINTED, {}).get("reason")
    ok = verdict["outcome"] == "FAIL" and seen == expected
    print("native_probe: CONTROL %s control=%s observed=%s:%s expected=%s" % (
        "PASS" if ok else "FAIL", args.control, verdict["outcome"], seen, expected))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
