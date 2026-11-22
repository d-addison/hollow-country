"""Read-only capability discovery for the autonomous validation framework (spec 002 AV-T002).

inventory(repo_root, machine=None) inspects repository seams only. discover_machine(paths=None)
looks for installed tools by file presence. Neither starts a process, reads an account, a
Steam file or a user folder, or opens a network connection. A fact says "this was observed
present or absent"; it never says a tool works, that a client is authenticated, that two
observers exist, or that any gameplay is accepted. Those stay "unverified".

Statuses: known (observed present), absent (observed missing), unverified (not observable
here). The planner vocabulary maps known -> available, absent -> blocked, unverified ->
unknown, so a capability can never be granted by an installed path alone.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("known", "absent", "unverified")
PLANNER_STATUS = {"known": "available", "absent": "blocked", "unverified": "unknown"}
DEFERRED = "deferred_owner_2026-11-22"
# Owner 2026-11-22: two licensed clients, audio judgement and load qualification are not
# built now. Discovery never reports them as anything but unverified.
DEFERRED_CAPABILITIES = {
    "licensed_authenticated_rendered_client_pair": "two licensed clients (AV-T017/AV-T018)",
    "synchronized_client_capture": "two licensed clients (AV-T017)",
    "qualified_network_fault_driver": "network fault adapter (AV-T018)",
    "paired_rendered_audio_capture": "rendered audio capture and judgement (AV-T019)",
    "separate_six_and_ninety_player_load": "co-op-6 and public-90 load qualification (AV-T022)",
}
OPTIONAL_MODULES = ("numpy", "PIL", "yaml")


def redact(text):
    """Remove home and Windows user-folder paths from any text before it is stored."""
    text = str(text)
    home = os.path.expanduser("~")
    if home and home != "~":
        text = text.replace(home, "~")
    return re.sub(r"(?i)(?:[a-z]:[\\/]|/mnt/[a-z]/)users[\\/][^\\/\s\"']+", "~", text)


def _fact(status, evidence):
    if status not in STATUSES:
        raise ValueError("unknown status")
    return {"status": status, "evidence": redact(evidence)}


def _default_paths():
    """Existing path constants of the native tools; import failure leaves a fact unverified."""
    paths = {}
    try:
        from tools.setup import diag_session, winproc
        paths.update(client=diag_session.CLIENT, server=diag_session.SERVER,
                     workshop=diag_session.WORKSHOP, system32=winproc.SYSTEM32)
    except Exception:  # noqa: BLE001 - discovery must report, not crash
        pass
    try:
        from tools.release import wb_compile
        paths["workbench"] = wb_compile.WORKBENCH
    except Exception:  # noqa: BLE001
        pass
    try:
        from tools.validate import cfgconvert_check
        paths["cfgconvert"] = cfgconvert_check.DEFAULT_TOOL
    except Exception:  # noqa: BLE001
        pass
    return paths


def discover_machine(paths=None):
    """File-presence facts about installed tools. Starts nothing; evidence has no paths."""
    resolved = _default_paths()
    resolved.update({key: Path(value) for key, value in (paths or {}).items()})
    facts = {}

    def present(key, label, check, location=None):
        path = resolved.get(location or key)
        if path is None:
            facts[key] = _fact("unverified", f"{label}: no configured location")
            return
        try:
            found = check(Path(path))
        except OSError as error:
            facts[key] = _fact("unverified", f"{label}: not readable ({type(error).__name__})")
            return
        facts[key] = _fact("known" if found else "absent",
                           f"{label}: {'found' if found else 'not found'} (location redacted)")

    present("client", "DayZ client install", lambda p: (p / "DayZ_x64.exe").is_file())
    present("diag", "DayZDiag executable", lambda p: (p / "DayZDiag_x64.exe").is_file(),
            location="client")
    present("server", "DayZ dedicated server install", lambda p: (p / "DayZServer_x64.exe").is_file())
    present("workshop", "Workshop content root", lambda p: p.is_dir())
    present("workbench", "DayZ Tools Workbench directory", lambda p: p.is_dir())
    present("cfgconvert", "DayZ Tools CfgConvert", lambda p: p.is_file())
    # Presence of the Windows interop binaries only; no process is queried or started.
    present("winproc", "Windows interop (powershell, tasklist)",
            lambda p: (p / "WindowsPowerShell/v1.0/powershell.exe").is_file()
            and (p / "tasklist.exe").is_file(), location="system32")
    facts["wine"] = _fact("known" if shutil.which("wine") else "absent",
                          "wine on PATH: " + ("found" if shutil.which("wine") else "not found"))
    facts["agent_run"] = _fact("known" if shutil.which("agent-run") else "absent",
                               "agent-run on PATH: " + ("found" if shutil.which("agent-run") else "not found"))
    for name in OPTIONAL_MODULES:
        found = importlib.util.find_spec(name) is not None
        facts["python:" + name] = _fact("known" if found else "absent",
                                        f"python module {name}: {'importable' if found else 'missing'}")
    facts["python:version"] = _fact("known", "python " + ".".join(map(str, sys.version_info[:3])))
    return {"schema_version": 1, "performed": True, "facts": dict(sorted(facts.items()))}


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def capability_names(repo_root):
    """Every capability a catalog row requires (the checked-in list only when no catalog exists)."""
    root = Path(repo_root)
    names = set()
    catalog = _load(root / "tests/catalog.json")
    if isinstance(catalog, dict):
        for row in catalog.get("tests", []):
            names.update(row.get("requires", []))
    if not names:  # no catalog: fall back to the checked-in list
        listed = _load(root / "tests/capabilities.json")
        if isinstance(listed, dict):
            names.update(listed.get("capabilities", {}))
    return sorted(names)


def inventory(repo_root, machine=None):
    """Capability observations. Repository seams always; machine facts only when supplied."""
    root = Path(repo_root)
    names = capability_names(root)
    seam = {rel: (root / rel).is_file() for rel in (
        "tools/validate/evidence.py", "tools/validate/hygiene.py", "tools/validate/automation_drift.py",
        "tools/release/compile_gate.py", "tools/release/checkstart.py", "tools/setup/diag_session.py")}
    catalog = _load(root / "tests/catalog.json")
    sources = catalog.get("sources", []) if isinstance(catalog, dict) else []
    facts = (machine or {}).get("facts", {})
    result = {}
    for name in names:
        if name in DEFERRED_CAPABILITIES:
            result[name] = _fact("unverified", f"{DEFERRED}: {DEFERRED_CAPABILITIES[name]}")
        elif name == "schema_validator":
            result[name] = _fact("known" if seam["tools/validate/evidence.py"] else "absent",
                                 "evidence-v1 validator " + ("present" if seam["tools/validate/evidence.py"] else "missing"))
        elif name == "secret_scan":
            result[name] = _fact("known" if seam["tools/validate/hygiene.py"] else "absent",
                                 "repository hygiene scan " + ("present" if seam["tools/validate/hygiene.py"] else "missing"))
        elif name == "pinned_inputs":
            pinned = bool(sources) and all(isinstance(s, dict) and re.fullmatch(r"[0-9a-f]{64}", str(s.get("sha256", "")))
                                           for s in sources)
            result[name] = _fact("known" if pinned else "absent",
                                 "catalog sources carry sha256 pins" if pinned else "catalog sources lack sha256 pins")
        elif name in ("normal_server", "dayzdiag"):
            key = "server" if name == "normal_server" else "diag"
            seen = facts.get(key)
            if seen is None:
                result[name] = _fact("unverified", "machine discovery not performed")
            else:
                result[name] = _fact(seen["status"], "installed executable observed by file presence only; "
                                     "never launched: " + seen["evidence"])
        elif name == "signed_package":
            result[name] = _fact("unverified", "needs an official signing and positive check run")
        else:
            result[name] = _fact("unverified", "no read-only probe can establish this; needs a qualified driver or human review")
    return {"schema_version": 1, "machine_discovery_performed": bool(machine),
            "capabilities": result}


def planner_capabilities(report):
    """Planner vocabulary (available|blocked|unknown) for an inventory() report."""
    return {name: PLANNER_STATUS[fact["status"]] for name, fact in sorted(report["capabilities"].items())}


def capabilities_document(repo_root):
    """Content of tests/capabilities.json: repository-only inventory, no machine facts."""
    root = Path(repo_root)
    report = inventory(root)
    existing = _load(root / "tests/capabilities.json") or {}
    return {
        "schema_version": 1,
        "catalog_id": existing.get("catalog_id", (_load(root / "tests/catalog.json") or {}).get("catalog_id")),
        "capabilities": planner_capabilities(report),
        "observations": dict(sorted(report["capabilities"].items())),
        "context": {
            "environment": "repository-only",
            "session_id": None,
            "machine_discovery_performed": False,
            "availability_values": ["available", "blocked", "unknown"],
            "observation_values": list(STATUSES),
            "verification": "Repository seams only. known means present, never qualified; "
                            "unverified stays unknown to the planner. No acceptance is inferred.",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--machine", action="store_true", help="also record file-presence facts (reads, starts nothing)")
    parser.add_argument("--write-capabilities", action="store_true",
                        help="rewrite tests/capabilities.json from the repository-only inventory")
    args = parser.parse_args(argv)
    if args.write_capabilities:
        document = capabilities_document(args.repo)
        (args.repo / "tests/capabilities.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return 0
    machine = discover_machine() if args.machine else None
    print(json.dumps(inventory(args.repo, machine), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
