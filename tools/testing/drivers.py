"""Trusted driver registry for the autonomous validation runner (spec 002 AV-T003/AV-T005).

A manifest only names driver IDs and validated inputs. Argv, cwd and environment are built
here, never taken from a manifest, and nothing runs through a shell. Each driver declares the
capabilities it needs, its trust class and a judge that turns the child's exit status and
output into PASS, FAIL or BLOCKED. A zero exit with no terminal result is FAIL, never PASS.

Trust: offline drivers wrap existing validators and are builtin. Native drivers (compile gate,
checkstart, DayZDiag session) are registered but run only when the caller lists their ID in
trusted_drivers; otherwise the runner reports NOTRUN reason=untrusted_native. This module
never starts DayZ, DayZDiag or Workbench itself; the framework never launches a session.
"""
from tools.validate import dayz_build
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Callable, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
NATIVE_SCRIPTS = dayz_build.native_scripts_dir()
OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOTRUN")
SKIPPED_CODES = (2, 3)  # layout_lint and cfgconvert_check SKIPPED exit codes
_COMMIT = re.compile(r"[0-9a-f]{7,40}\Z")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[A-Za-z0-9_. \\-]{1,200}\Z")
_PATH = re.compile(r"[A-Za-z0-9_./ -]{1,300}\Z")


@dataclass(frozen=True)
class Driver:
    id: str
    kind: str                      # "offline" or "native"
    description: str
    needs: Tuple[str, ...]         # capability names that must read "available"
    argv: Callable                 # (repo_root, inputs) -> list[str]
    judge: Callable                # (returncode, output) -> (outcome, reason)
    inputs: Tuple[str, ...] = ()   # input names a manifest may supply
    timeout: int = 900             # seconds
    memory: Optional[str] = None   # agent-run --memory value for heavy native tools

    @property
    def trust(self):
        return "builtin" if self.kind == "offline" else "explicit"

    @property
    def layer(self):
        return "offline-framework" if self.kind == "offline" else "zero-client-native"


def _module(name, *arguments):
    def build(repo_root, inputs):
        return [sys.executable, "-B", "-m", name, *arguments]
    return build


def _json_last(output):
    """Parse the whole output, or its last nonempty line, as one JSON object."""
    for candidate in (output.strip(), (output.strip().splitlines() or [""])[-1]):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def judge_exit(returncode, output):
    if returncode in SKIPPED_CODES:
        return "BLOCKED", "skipped_coverage"
    if returncode != 0:
        return "FAIL", "nonzero_exit"
    if not output.strip():
        return "FAIL", "no_terminal_result"
    return "PASS", "exit_zero_with_output"


def judge_preland_piece(name):
    """Exit status plus the preland gap detector: a skipped or unavailable gate is not PASS."""
    def judge(returncode, output):
        outcome, reason = judge_exit(returncode, output)
        if outcome == "PASS":
            from tools.validate import preland
            if preland.incomplete_lines(name, output):
                return "BLOCKED", "skipped_coverage"
        return outcome, reason
    return judge


def judge_hygiene(returncode, output):
    report = _json_last(output)
    if returncode != 0 or report is None:
        return ("FAIL", "nonzero_exit") if returncode != 0 else ("FAIL", "no_terminal_result")
    return ("PASS", "valid_true") if report.get("valid") is True else ("FAIL", "valid_not_true")


def judge_automation_drift(returncode, output):
    report = _json_last(output)
    if report is None:
        return "FAIL", "no_terminal_result"
    return ("PASS", "valid_true") if returncode == 0 and report.get("valid") is True else ("FAIL", "valid_not_true")


def judge_bdd_offline(returncode, output):
    if returncode != 0:
        return "FAIL", "nonzero_exit"
    match = re.search(r"Bound offline scenarios: (\d+); runtime acceptance: NOT EXECUTED", output)
    if not match or int(match.group(1)) == 0:
        return "FAIL", "no_terminal_result"   # zero bound scenarios is never a pass
    return "PASS", "bound_scenarios_executed"


def judge_bdd_runtime(returncode, output):
    """Intact runtime protocols are still manual and pending: BLOCKED, never PASS."""
    report = _json_last(output)
    if report is None:
        return "FAIL", "no_terminal_result"
    if returncode != 0 or report.get("intact") is not True:
        return "FAIL", "runtime_protocol_drift"
    return "BLOCKED", "manual_runtime_protocol_pending"


def judge_compile_gate(returncode, output):
    if returncode == 0 and re.search(r"^compile_gate: PASS status=", output, re.M):
        return "PASS", "mission_marker_observed"
    if re.search(r"^compile_gate: FAIL", output, re.M) or returncode != 0:
        return "FAIL", "compile_gate_failed"
    return "FAIL", "no_terminal_result"


def judge_checkstart(returncode, output):
    verdict = re.search(r"^boot_verdict=(\w+)$", output, re.M)
    if not verdict:
        return "FAIL", "no_terminal_result"
    if returncode == 0 and verdict.group(1) == "connect_enabled":
        return "PASS", "boot_verdict_connect_enabled"
    if verdict.group(1) in ("input_error", "interop_unknown"):
        return "BLOCKED", "boot_" + verdict.group(1)
    return "FAIL", "boot_" + verdict.group(1)


def judge_plan_only(returncode, output):
    if returncode != 0:
        return "FAIL", "nonzero_exit"
    return "BLOCKED", "plan_only_no_session"


def _compile_gate_argv(repo_root, inputs):
    argv = [sys.executable, "-B", "-m", "tools.release.compile_gate", "--tree", str(repo_root)]
    if "commit" in inputs:
        if not isinstance(inputs["commit"], str) or not _COMMIT.fullmatch(inputs["commit"]):
            raise ValueError("commit input must be a lowercase hex revision")
        argv += ["--commit", inputs["commit"]]
    return argv


def _checkstart_argv(repo_root, inputs):
    bundle, rpt = inputs.get("bundle"), inputs.get("rpt")
    if not isinstance(bundle, str) or not _WINDOWS_PATH.fullmatch(bundle):
        raise ValueError("bundle input must be a Windows path")
    if not isinstance(rpt, str) or not _PATH.fullmatch(rpt) or ".." in rpt.split("/"):
        raise ValueError("rpt input must be an existing log path")
    # Attach-only: --start is never passed, so the framework cannot start a server.
    return [sys.executable, "-B", "-m", "tools.release.checkstart", "--bundle", bundle, "--rpt", rpt]


def _preland_driver(name, *arguments, needs=()):
    def build(repo_root, inputs):
        extra = ["--native-scripts", str(NATIVE_SCRIPTS)] if name == "enforce_lint" else []
        return [sys.executable, "-B", "-m", "tools.validate." + name, *extra, *arguments]
    return Driver("offline." + name, "offline", f"preland piece tools.validate.{name}", needs,
                  build, judge_preland_piece(name), timeout=600)


DRIVERS = {d.id: d for d in (
    Driver("offline.hygiene", "offline", "repository hygiene scan", ("secret_scan",),
           _module("tools.validate.hygiene"), judge_hygiene, timeout=300),
    Driver("offline.bdd", "offline", "bound offline BDD subset (runs the bound unit tests)", (),
           _module("tools.validate.bdd"), judge_bdd_offline, timeout=1800),
    Driver("offline.bdd_runtime", "offline", "runtime protocol bindings; scenarios stay BLOCKED", (),
           _module("tools.validate.bdd", "--runtime"), judge_bdd_runtime, timeout=60),
    Driver("offline.automation_drift", "offline", "catalog, capability and runtime feature drift check",
           ("schema_validator",), _module("tools.validate.automation_drift"), judge_automation_drift, timeout=120),
    _preland_driver("enforce_lint"),
    _preland_driver("enforce_perf", "--strict-baseline"),
    _preland_driver("layout_lint"),
    _preland_driver("settings_consistency"),
    _preland_driver("wiring_audit"),
    Driver("native.compile_gate", "native", "native compile gate; PASS needs the Mission marker",
           ("normal_server",), _compile_gate_argv, judge_compile_gate, inputs=("commit",),
           timeout=1500, memory="12G"),
    Driver("native.checkstart", "native", "attach-only boot verdict over an existing RPT",
           ("normal_server",), _checkstart_argv, judge_checkstart, inputs=("bundle", "rpt"), timeout=900),
    Driver("native.diag_session", "native", "DayZDiag session plan only; never launches",
           ("dayzdiag",), _module("tools.setup.diag_session", "--plan"), judge_plan_only, timeout=120),
    Driver("native.soak_campaign", "native", "soak campaign plan only; the lead runs the campaign",
           (), _module("tools.testing.soak_campaign", "plan"), judge_plan_only, timeout=120),
)}


def get(registry, driver_id):
    """Resolve a manifest-supplied driver ID; unknown IDs are rejected, never improvised."""
    if not isinstance(driver_id, str) or driver_id not in registry:
        raise ValueError("Unknown driver ID")
    return registry[driver_id]
