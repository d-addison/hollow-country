"""Isolated normal-server compile, sign and launch adapter (spec 002 AV-T007).

A wrapper around the existing release tools, never new launch code: the Wine provider runs
tools.release.compile_gate (which owns the isolated server copy, the Wine prefix, the package pin and
the cleanup) as one child of this adapter, and adds the separate positive checker the gate does not
have: a pinned PBO, a verified signature report, logs fresh since launch, an exact loopback socket
owned by the child tree, process cleanup, and an unchanged stock server copy. Native Windows is a
separate provider contract: attach-only, no process or socket observation, and its own evidence label.

Native work (run, control) holds the shared host lock and refuses hosted CI. judge() is pure: it turns
one evidence record into PASS, FAIL or BLOCKED and never reads the host. No client is involved, so a
PASS is zero-client native evidence for the compile/load/launch layer only; a signature-enforced
join belongs to AV-T015 and AV-T017 and is listed as unobserved in every verdict.

    python3 -B -m tools.testing.native_server plan
    python3 -B -m tools.testing.native_server run --provider wine --tree .
    python3 -B -m tools.testing.native_server control wrong_pin|wildcard_claim|unbound_port --tree .
    python3 -B -m tools.testing.native_server judge evidence.json
"""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from tools.testing import native_common as common

ROOT = Path(__file__).resolve().parents[2]
PBO_NAME = "hollowcountry.pbo"
ALLOWED_STATUS = frozenset({"initialized", "timeout", "mission-loaded-runtime-json"})
HOLDER = "native_server"
REQUIRED_MODULES = ("World", "Mission")
SAMPLE_SECONDS = 1.0
CLEANUP_GRACE_SECONDS = 10.0
SETUP_RESERVE_SECONDS = 900
GATE_PBO = re.compile(r"^compile_gate: pbo_sha256=([0-9a-f]{64})\b", re.M)
GATE_PASS = re.compile(r"^compile_gate: PASS status=", re.M)
GATE_FAIL = re.compile(r"^compile_gate: FAIL", re.M)
BIND = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})\Z")


@dataclass(frozen=True)
class Provider:
    id: str
    label: str            # the environment label an evidence record from this provider must carry
    launcher: str         # the existing tool this adapter wraps
    required: tuple       # check names that must all pass
    claims: tuple         # what a PASS from this provider may say
    unobserved: tuple     # what this provider can never observe, always stated in the verdict


PROVIDERS = {
    "wine": Provider(
        "wine", "actual-DayZ-server-under-Wine", "tools.release.compile_gate",
        ("provider", "no_client", "pbo_pin", "signature", "gate", "logs_fresh", "modules", "errors",
         "socket", "cleanup", "guard"),
        ("pinned_pbo_official_compile", "mission_load", "loopback_socket", "process_cleanup",
         "signature_tool_verified"),
        ("signature_enforced_join", "client_join", "native_windows_behaviour")),
    "windows": Provider(
        "windows", "native-windows-server", "tools.release.checkstart (attach-only)",
        ("provider", "no_client", "pbo_pin", "boot_verdict", "logs_fresh", "guard"),
        ("boot_verdict_connect_enabled",),
        ("process_ownership", "socket_binding", "process_cleanup", "signature_enforced_join",
         "client_join", "wine_behaviour")),
}


# --- The pure judge ---------------------------------------------------------------------------

def check_signature(report, pbo_name, pin, signed_dir=None):
    """Positive structural check of a sign_and_verify report against the pinned PBO.

    The official tool already verified the signature cryptographically; this binds that result to
    this exact PBO name and hash, refuses a private key anywhere in the file list, and (when the
    signed directory is given) re-hashes the files so a later change is caught.
    """
    if not isinstance(report, dict) or report.get("status") != "signed-development":
        return False, "signature_not_verified", "no signed-development report"
    files = report.get("files")
    if not isinstance(files, dict) or not files:
        return False, "signature_not_verified", "no file list"
    if any(name.lower().endswith(".biprivatekey") for name in files):
        return False, "signature_private_key_listed", "private key material listed"
    if any(not isinstance(value, str) or not common.SHA256.fullmatch(value) for value in files.values()):
        return False, "signature_not_verified", "malformed hash"
    pbo_key = "addons/" + pbo_name
    if files.get(pbo_key) != pin:
        return False, "signature_pbo_mismatch", "signed PBO hash differs from the pin"
    signatures = [name for name in files if name.startswith(pbo_key + ".") and name.endswith(".bisign")]
    if len(signatures) != 1:
        return False, "signature_file_mismatch", "expected exactly one signature for the PBO name"
    stem = signatures[0][len(pbo_key) + 1:-len(".bisign")]
    if not stem or "keys/" + stem + ".bikey" not in files:
        return False, "signature_file_mismatch", "signature key name has no matching public key"
    if signed_dir is not None:
        for name, digest in files.items():
            try:
                target = common.require_owned(signed_dir, Path(signed_dir) / name)
                if common.sha256_file(target) != digest:
                    return False, "signature_files_changed", "a signed file differs from the report"
            except (OSError, ValueError):
                return False, "signature_files_changed", "a signed file is missing or unsafe"
    return True, "signature_ok", "pbo and signature bound to the pin"


def _check_provider(e, provider):
    report = e.get("report") or {}
    label = report.get("environment") if provider.id == "wine" else e.get("environment")
    if e.get("provider") != provider.id or label != provider.label:
        return False, "provider_mismatch", "evidence label differs from the provider contract"
    return True, "provider_ok", provider.label


def _check_no_client(e, provider):
    report = e.get("report") or {}
    if e.get("client_count") != 0 or report.get("client_count", 0) != 0 or e.get("client_claims"):
        return False, "client_claim_refused", "this adapter observes zero clients"
    return True, "zero_clients", "client_count=0"


def _check_pbo_pin(e, provider):
    pin = (e.get("pin") or {}).get("pbo_sha256")
    if not isinstance(pin, str) or not common.SHA256.fullmatch(pin):
        return False, "pbo_pin_missing", "no valid pin"
    seen = (e.get("report") or {}).get("pbo_sha256") if provider.id == "wine" else e.get("pbo_sha256_observed")
    gate = (e.get("gate") or {}).get("pbo_sha256") if provider.id == "wine" else seen
    if seen != pin or gate != pin:
        return False, "pbo_pin_mismatch", "launched or gated PBO differs from the pinned PBO"
    return True, "pbo_pinned", pin[:12]


def _check_signature(e, provider):
    pin = (e.get("pin") or {}).get("pbo_sha256")
    return check_signature(e.get("signature_report"), (e.get("pin") or {}).get("pbo_name", PBO_NAME), pin,
                           e.get("signed_dir"))


def _check_gate(e, provider):
    gate, report = e.get("gate") or {}, e.get("report") or {}
    if gate.get("returncode") != 0 or not gate.get("pass_line") or gate.get("fail_line"):
        return False, "compile_gate_failed", "compile gate did not report PASS"
    if report.get("status") not in ALLOWED_STATUS or report.get("engine_error_observed"):
        return False, "compile_gate_failed", "probe status " + str(report.get("status"))
    return True, "compile_gate_pass", str(report.get("status"))


def _check_boot_verdict(e, provider):
    gate = e.get("gate") or {}
    if gate.get("returncode") == 0 and gate.get("boot_verdict") == "connect_enabled":
        return True, "boot_verdict_ok", "connect_enabled"
    return False, "boot_verdict_" + str(gate.get("boot_verdict")), "attach-only boot verdict"


def _check_logs_fresh(e, provider):
    logs = e.get("logs") or {}
    if logs.get("rejected") or logs.get("skipped"):
        return False, "stale_or_unreadable_logs", "a log was stale, rewritten or unreadable"
    if not logs.get("fresh_files"):
        return False, "no_fresh_log", "no log written since launch"
    return True, "logs_fresh", str(logs["fresh_files"]) + " fresh logs"


def _check_modules(e, provider):
    modules = (e.get("logs") or {}).get("modules") or []
    missing = [name for name in REQUIRED_MODULES if name not in modules]
    if missing:
        return False, "mission_not_loaded", "missing " + ",".join(missing)
    return True, "modules_loaded", ",".join(modules)


def _check_errors(e, provider):
    logs = e.get("logs") or {}
    if logs.get("script_errors"):
        return False, "script_errors", str(logs["script_errors"]) + " SCRIPT (E) lines retained"
    if logs.get("engine_errors") or logs.get("dumps"):
        return False, "engine_errors", "engine error or ErrorMessage dump retained"
    return True, "no_errors", "0 script, 0 engine errors"


def _check_socket(e, provider):
    sockets = e.get("sockets") or {}
    claim = sockets.get("claim") or {}
    if not sockets.get("sampled"):
        return False, "socket_not_observed", "no socket sample taken while the server ran"
    if not claim.get("claimed"):
        return False, str(claim.get("reason") or "not_bound"), "no owned exact loopback bind"
    return True, "socket_owned_exact", "%s:%s" % (claim.get("ip"), claim.get("port"))


def _check_cleanup(e, provider):
    cleanup = e.get("cleanup") or {}
    if not cleanup.get("observed"):
        return False, "cleanup_not_observed", "no cleanup observation"
    if cleanup.get("survivors"):
        return False, "child_survived_launcher", str(len(cleanup["survivors"])) + " owned processes alive"
    if cleanup.get("port_free") is not True:
        return False, "port_not_released", "gameplay port still bound"
    return True, "cleanup_clean", "no owned process, port free"


def _check_guard(e, provider):
    guard = e.get("guard") or {}
    if not guard.get("observed"):
        return False, "guard_not_observed", "no before/after snapshot"
    if guard.get("changed"):
        return False, "stock_or_server_file_modified", ",".join(map(str, guard["changed"][:8]))
    return True, "guard_unchanged", "stock files unchanged"


CHECKS = {
    "provider": _check_provider, "no_client": _check_no_client, "pbo_pin": _check_pbo_pin,
    "signature": _check_signature, "gate": _check_gate, "boot_verdict": _check_boot_verdict,
    "logs_fresh": _check_logs_fresh, "modules": _check_modules, "errors": _check_errors,
    "socket": _check_socket, "cleanup": _check_cleanup, "guard": _check_guard,
}


def judge(evidence):
    """One evidence record to {outcome, reason, checks, claims, unobserved}. Never reads the host."""
    provider = PROVIDERS.get(evidence.get("provider")) if isinstance(evidence, dict) else None
    if provider is None:
        return {"schema": 1, "provider": None, "outcome": "FAIL", "reason": "provider_unknown",
                "checks": [], "claims": [], "unobserved": [], "client_count": 0, "acceptance": "not_accepted"}
    checks, failed = [], []
    for name in provider.required:
        try:
            ok, reason, detail = CHECKS[name](evidence, provider)
        except (AttributeError, KeyError, TypeError, ValueError):
            ok, reason, detail = False, "evidence_malformed", "check input malformed"
        checks.append({"name": name, "ok": ok, "reason": reason, "detail": str(detail)[:200]})
        if not ok:
            failed.append(reason)
    outcome = "PASS" if not failed else "FAIL"
    return {"schema": 1, "provider": provider.id, "label": provider.label, "outcome": outcome,
            "reason": "all_required_checks_passed" if not failed else failed[0],
            "failed": failed, "checks": checks,
            "claims": list(provider.claims) if outcome == "PASS" else [],
            "unobserved": list(provider.unobserved), "client_count": 0,
            "layer": "zero-client-native", "acceptance": "not_accepted",
            "synthetic": bool(evidence.get("synthetic"))}


# --- Evidence collection (reads an experiment directory the gate already finished) -------------

def _loopback_claim(report, override):
    if override:
        return override
    match = BIND.match(str(report.get("requested_gameplay_bind", "")))
    if not match:
        raise ValueError("compiler report names no gameplay bind")
    return {"ip": match.group(1), "port": int(match.group(2))}


def parse_gate_output(text, returncode):
    found = GATE_PBO.search(text)
    return {"returncode": returncode, "pass_line": bool(GATE_PASS.search(text)),
            "fail_line": bool(GATE_FAIL.search(text)), "pbo_sha256": found.group(1) if found else None}


def read_fresh(experiment, started_ns, baseline=None):
    """(fresh texts by file, rejected, skipped) for one experiment's profile logs."""
    files, skipped = common.read_logs(Path(experiment) / "profiles")
    texts, rejected = common.fresh_logs(files, baseline or {}, started_ns)
    return texts, rejected, skipped


def summarize_logs(texts, rejected, skipped, dumps):
    """Modules, error lines and rejected logs from fresh texts; the evidence the judge reads."""
    from tools.release import compile_gate
    from tools.setup import wine_compile_probe as probe
    script = "\n".join(text for name, text in sorted(texts.items()) if re.fullmatch(r"script_[^/]*\.log", name))
    modules = list(dict.fromkeys(compile_gate.MODULE_LOADED.findall(script)))
    errors = [line for line in script.splitlines() if compile_gate.SCRIPT_ERROR.search(line)]
    runtime_json = []
    if "Mission" in modules:
        runtime_json = [line for line in errors if compile_gate.RUNTIME_JSON_ERROR.search(line)]
        errors = [line for line in errors if not compile_gate.RUNTIME_JSON_ERROR.search(line)]
    everything = "\n".join(text for _, text in sorted(texts.items()))
    engine = [line for line in everything.splitlines() if compile_gate.COMPILE_FAILURE.search(line)]
    if probe.classify(everything) == "engine-crash":
        engine.append("ENGINE (F): Crashed")
    return {"fresh_files": len(texts), "rejected": rejected, "skipped": skipped, "modules": modules,
            "script_errors": len(errors), "script_error_lines": [line[:400] for line in errors[:20]],
            "runtime_json_errors": len(runtime_json), "engine_errors": [line[:400] for line in engine[:20]],
            "dumps": dumps}


def collect_logs(experiment, started_ns, baseline=None):
    """Fresh-log evidence from one experiment: modules, errors, rejected and skipped logs."""
    texts, rejected, skipped = read_fresh(experiment, started_ns, baseline)
    dumps = len(list((Path(experiment) / "profiles").glob("ErrorMessage_*.mdmp")))
    return summarize_logs(texts, rejected, skipped, dumps)


def read_report(experiment):
    path = Path(experiment) / "compiler-report.json"
    info = os.lstat(path)
    if not os.path.isfile(path) or info.st_size > 1024 * 1024 or os.path.islink(path):
        raise ValueError("compiler report missing or oversized")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("compiler report is not an object")
    return report


def run_dirs(cache):
    """Names of the experiment directories already in the cache (the host lock makes new ones ours)."""
    return {path.name for path in Path(cache).glob("run-*") if path.is_dir() and not path.is_symlink()}


def new_run_dirs(cache, before):
    return sorted(Path(cache) / name for name in run_dirs(cache) - set(before))


# --- Sampling ownership ---------------------------------------------------------------------------

def sample_once(ledger, proc_root, net_root, root_pid):
    """One bounded observation: update the ledger and return the endpoints the owned tree holds."""
    table = common.scan(proc_root)
    pids = ledger.update(table, root_pid)
    return common.observe_sockets(proc_root, net_root, pids)


def await_cleanup(ledger, proc_root, net_root, ip, port, grace=CLEANUP_GRACE_SECONDS,
                  sleep=time.sleep, clock=time.monotonic):
    """After the child exited: wait a bounded grace for owned processes (a Wine server lingers) to end."""
    deadline = clock() + grace
    while True:
        survivors = ledger.survivors(common.scan(proc_root))
        free = common.port_free(common.net_rows(net_root), ip, port)
        if (not survivors and free) or clock() >= deadline:
            return {"observed": True, "survivors": survivors, "port_free": free}
        sleep(0.5)


# --- The native run (owner host only) -----------------------------------------------------------

def stock_guard_paths(server_root):
    root = Path(server_root)
    files = {"server_exe": root / "DayZServer_x64.exe", "diag_exe": root / "DayZDiag_x64.exe",
             "battleye_dll": root / "battleye/BEServer_x64.dll",
             "mission_init": root / "mpmissions/dayzOffline.chernarusplus/init.c"}
    directories = {"mission": root / "mpmissions", "keys": root / "keys"}
    return files, directories


def compute_pin(tree, commit, cache):
    """sha256 of the PBO exactly as compile_gate packs it, computed independently before launch."""
    from tools.package import pbo
    from tools.release import compile_gate
    with compile_gate.source_tree(Path(tree).resolve(), commit, cache) as source:
        blob = pbo.pack(pbo.collect_addon(source / "mods/HollowCountry"))
    return {"pbo_name": PBO_NAME, "pbo_sha256": common.sha256_bytes(blob)}, blob


def refuse_hosted_ci(environ=None):
    environ = os.environ if environ is None else environ
    if any(str(environ.get(name, "")).lower() == "true" for name in ("GITHUB_ACTIONS", "CI")):
        raise ValueError("hosted_ci_refused")


def run_wine(tree, out, *, commit=None, seconds=900, expect_pin=None, claim=None, sign=True,
             cache=None, lock_path=None, proc_root="/proc", net_root="/proc/net", popen=subprocess.Popen,
             signer=None, server_root=None, prefix=None, sleep=time.sleep, clock=time.monotonic,
             grace=CLEANUP_GRACE_SECONDS):
    """Wrap compile_gate in an owned child, observe it, and return the judged verdict.

    Pre-launch refusals (hosted CI, a pin the tree does not produce, an unsafe output path) return a
    FAIL verdict without launching anything. Everything native runs under the shared host lock.
    """
    from tools.release import compile_gate
    from tools.release.host_lock import host_lock
    refuse_hosted_ci()
    if not 15 <= seconds <= 900:
        raise ValueError("seconds must be 15..900")
    out = Path(os.path.abspath(out))
    if out.exists():
        raise ValueError("output directory must be fresh")
    cache = Path(cache) if cache else Path.home() / ".cache/hollow-country/compile-gate"
    server_root, prefix, reason = compile_gate.prerequisites(server_root, prefix)
    if reason:
        return {"schema": 1, "provider": "wine", "outcome": "BLOCKED", "reason": "prerequisite_absent",
                "detail": reason, "client_count": 0, "acceptance": "not_accepted", "checks": [], "claims": [],
                "unobserved": list(PROVIDERS["wine"].unobserved)}
    with host_lock(HOLDER, lock_path):
        compile_gate.require_client_idle(False)
        pin, blob = compute_pin(tree, commit, cache)
        if expect_pin is not None and expect_pin != pin["pbo_sha256"]:
            return {"schema": 1, "provider": "wine", "outcome": "FAIL", "reason": "pbo_pin_mismatch",
                    "detail": "expected pin differs from the tree; nothing launched", "client_count": 0,
                    "acceptance": "not_accepted", "checks": [], "claims": [],
                    "unobserved": list(PROVIDERS["wine"].unobserved)}
        out.mkdir(parents=True)
        stage = out / "stage"
        common.write_owned(stage, PBO_NAME, blob)
        evidence = {"schema": 1, "provider": "wine", "pin": pin, "client_count": 0}
        if sign:
            signer = signer or _default_signer()
            try:
                evidence["signature_report"] = signer(stage / PBO_NAME, out / "signed")
                evidence["signed_dir"] = str(out / "signed")
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                evidence["signature_report"] = {"status": "failed", "error": compile_gate.private(error)[:300]}
        files, directories = stock_guard_paths(server_root)
        before = common.snapshot_guard(files, directories)
        argv = [sys.executable, "-B", "-m", "tools.release.compile_gate", "--tree", str(Path(tree).resolve()),
                "--seconds", str(seconds), "--cache", str(cache),
                "--server-root", str(server_root), "--prefix", str(prefix)]
        if commit:
            argv += ["--commit", commit]
        started_ns = time.time_ns()
        existing = run_dirs(cache)
        ledger = common.Ledger()
        samples, last_rows, owned, timed_out = 0, [], {}, False
        with open(out / "gate.log", "wb") as log:
            process = popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = clock() + seconds + SETUP_RESERVE_SECONDS
            while process.poll() is None:
                if clock() >= deadline:
                    timed_out = True
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    break
                last_rows = sample_once(ledger, proc_root, net_root, process.pid)
                samples += 1
                for row in last_rows:
                    if row["owner"] is not None:
                        owned[(row["proto"], row["ip"], row["port"])] = row
                sleep(SAMPLE_SECONDS)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        gate_text = (out / "gate.log").read_text(encoding="utf-8", errors="replace")
        evidence["gate"] = parse_gate_output(gate_text, process.returncode if not timed_out else 124)
        runs = new_run_dirs(cache, existing)
        if len(runs) != 1:
            evidence["report"] = None
            evidence["logs"] = {}
            verdict = judge(evidence)
            verdict["reason"] = "experiment_not_found" if len(runs) == 0 else "experiment_ambiguous"
            return verdict
        experiment = runs[0]
        evidence["report"] = report = read_report(experiment)
        evidence["logs"] = collect_logs(experiment, started_ns)
        wanted = _loopback_claim(report, claim)
        seen = list(owned.values()) + [row for row in last_rows if row["owner"] is None]
        evidence["sockets"] = {"sampled": samples, "claim": common.claim_socket(seen, wanted["ip"], wanted["port"]),
                               "wildcard_owned": [list(item) for item in common.wildcard_owned(seen)]}
        evidence["cleanup"] = await_cleanup(ledger, proc_root, net_root, wanted["ip"], wanted["port"],
                                            grace, sleep, clock)
        after = common.snapshot_guard(files, directories)
        evidence["guard"] = {"observed": True, "changed": common.diff_guard(before, after)}
        verdict = judge(evidence)
        if timed_out:
            verdict.update(outcome="FAIL", reason="adapter_timeout")
        verdict["experiment"] = compile_gate.private(experiment)
        verdict["evidence_file"] = "evidence.json"
        try:
            common.write_owned(out, "evidence.json", json.dumps(evidence, sort_keys=True, indent=1).encode())
        except (OSError, ValueError):
            pass
        return verdict


def _default_signer():
    from tools.package import sign_wine
    return sign_wine.sign


# --- Windows provider (attach-only) ---------------------------------------------------------------

def windows_evidence(pin, observed_sha256, checkstart_output, returncode, rpt_mtime_ns, since_ns, guard_changed):
    """Evidence for the attach-only Windows contract. Freshness needs an explicit since timestamp."""
    verdict = re.search(r"^boot_verdict=(\w+)$", checkstart_output, re.M)
    fresh = isinstance(since_ns, int) and isinstance(rpt_mtime_ns, int) and rpt_mtime_ns >= since_ns
    return {"schema": 1, "provider": "windows", "environment": PROVIDERS["windows"].label, "pin": pin,
            "pbo_sha256_observed": observed_sha256, "client_count": 0,
            "gate": {"returncode": returncode, "boot_verdict": verdict.group(1) if verdict else None},
            "logs": {"fresh_files": 1 if fresh else 0, "rejected": {} if fresh else {"rpt": "not_proven_fresh"},
                     "skipped": {}},
            "guard": {"observed": True, "changed": list(guard_changed)}}


# --- Command line ---------------------------------------------------------------------------------

CONTROLS = {
    "wrong_pin": ("pbo_pin_mismatch", "an expected pin that the tree does not produce is refused before any launch"),
    "wildcard_claim": ("wildcard_not_a_claim", "claiming 0.0.0.0 on the gameplay port is not a claim"),
    "unbound_port": ("not_bound", "claiming a port the server never binds fails"),
}


def plan_report():
    return {"adapter": "native_server", "layer": "zero-client-native",
            "providers": {key: {"label": p.label, "launcher": p.launcher, "required_checks": list(p.required),
                                "claims": list(p.claims), "unobserved": list(p.unobserved)}
                          for key, p in PROVIDERS.items()},
            "controls": {key: text[1] for key, text in CONTROLS.items()},
            "commands": ["python3 -B -m tools.testing.native_server run --provider wine --tree .",
                         "python3 -B -m tools.testing.native_server control wrong_pin --tree .",
                         "python3 -B -m tools.testing.native_server control wildcard_claim --tree .",
                         "python3 -B -m tools.testing.native_server control unbound_port --tree ."]}


def _print(verdict):
    print("native_server: %s reason=%s provider=%s" % (verdict["outcome"], verdict["reason"], verdict.get("provider")))
    print(json.dumps(verdict, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    judge_parser = sub.add_parser("judge")
    judge_parser.add_argument("evidence", type=Path)
    for name in ("run", "control"):
        item = sub.add_parser(name)
        if name == "control":
            item.add_argument("control", choices=sorted(CONTROLS))
        item.add_argument("--provider", choices=["wine"], default="wine")
        item.add_argument("--tree", type=Path, default=Path.cwd())
        item.add_argument("--commit")
        item.add_argument("--seconds", type=int, default=900)
        item.add_argument("--out", type=Path)
        item.add_argument("--no-sign", action="store_true")
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
    out = args.out or Path.home() / ".cache/hollow-country/native-adapter" / ("run-%d" % time.time_ns())
    options = {"commit": args.commit, "seconds": args.seconds, "sign": not args.no_sign}
    expected = None
    if args.command == "control":
        expected = CONTROLS[args.control][0]
        if args.control == "wrong_pin":
            options["expect_pin"] = "0" * 64
        elif args.control == "wildcard_claim":
            options["claim"] = {"ip": "0.0.0.0", "port": 2402}
        else:
            options["claim"] = {"ip": "127.0.0.1", "port": 2499}
    try:
        verdict = run_wine(args.tree, out, **options)
    except ValueError as error:
        print("native_server: REFUSED %s" % common_text(error))
        return 1
    except Exception as error:  # LockRefused and friends: a refusal, not a result
        print("native_server: REFUSED %s" % common_text(error))
        return 1
    if expected is None:
        _print(verdict)
        return 0 if verdict["outcome"] == "PASS" else 1
    ok = verdict["outcome"] == "FAIL" and expected in (verdict.get("failed") or [verdict["reason"]])
    print("native_server: CONTROL %s control=%s observed=%s:%s expected=%s" % (
        "PASS" if ok else "FAIL", args.control, verdict["outcome"], verdict["reason"], expected))
    return 0 if ok else 1


def judge_output(returncode, output):
    """Driver judge: PASS only for a terminal zero-client verdict that said PASS and exited 0."""
    from tools.testing import drivers
    if "native_server: REFUSED" in output:
        return "BLOCKED", "adapter_refused"
    verdict = drivers._json_last(output)
    if verdict is None or verdict.get("client_count") != 0 or verdict.get("acceptance") != "not_accepted":
        return "FAIL", "no_terminal_result"
    if verdict.get("outcome") == "BLOCKED":
        return "BLOCKED", str(verdict.get("reason", "blocked"))[:60]
    if returncode == 0 and verdict.get("outcome") == "PASS":
        return "PASS", "zero_client_native_pass"
    return "FAIL", str(verdict.get("reason", "nonzero_exit"))[:60]


def driver():
    from tools.testing import drivers

    def argv(repo_root, inputs):
        return [sys.executable, "-B", "-m", "tools.testing.native_server", "run", "--provider", "wine",
                "--tree", str(repo_root)]
    return drivers.Driver("native.server_adapter", "native",
                          "isolated normal-server compile, sign and launch adapter; zero client, never accepted",
                          ("normal_server", "signed_package"), argv, judge_output, timeout=3000, memory="12G")


def common_text(error):
    return re.sub(r"/(?:home|mnt/[a-z]/Users)/[^/\s]+", "~", str(error))[:300]


if __name__ == "__main__":
    raise SystemExit(main())
