"""Stage an explicitly disposable diagnostic mission; never launch the engine.

Only the stock factory return type and an appended authored subclass change.
Purchased mission contents remain outside source/Steam; provenance contains hashes.
Failed partial output is preserved and cannot be reused or overwritten.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_ENTRIES = 256
MAX_DEPTH = 12
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_INIT_BYTES = 65536
MAX_HOOK_BYTES = 256 * 1024
MARKER_NAME = ".hollow-country-diagnostic-mission.json"

# Existing methods inspected in installed 1.30 scripts and the authored addon.
# The superclass preserves CustomMission -> modded MissionServer -> native chain.
DIAGNOSTIC_HOOK = b"""

// Hollow Country DISPOSABLE diagnostic experiment; no gameplay acceptance.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCDiagnosticExecuted = false;

    override void OnInit()
    {
        super.OnInit();
#ifdef DIAG_DEVELOPER
        if (!GetGame() || !GetGame().IsServer() || m_HCDiagnosticExecuted)
            return;
        m_HCDiagnosticExecuted = true;
        Print("[HC Diagnostic Mission] BEGIN epoch=900001; synthetic storage only");
        bool infectedResult = HCInfectedSelfTests.Run();
        Print("[HC Diagnostic Mission] infected scalar result=" + infectedResult);
        bool storageResult = HCInteriorSelfTests.RunStorageProbe(900001);
        Print("[HC Diagnostic Mission] interior storage result=" + storageResult);
        if (infectedResult && storageResult)
            Print("[HC Diagnostic Mission] PASS; no inventory/gameplay acceptance");
        else
            Print("[HC Diagnostic Mission] FAIL; preserve profile and inspect logs");
#endif
    }
}
"""

ITEM_AUDIT_HOOK = b"""

// Hollow Country DISPOSABLE metadata acquisition; no gameplay acceptance.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCDiagnosticExecuted = false;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCDiagnosticExecuted)
            return;
        m_HCDiagnosticExecuted = true;
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        string outputPath;
        string error;
        Print("[HC Item Audit] BEGIN; metadata only");
        bool complete = HCItemCompatibilityAudit.ExportAll("native-item-audit", world, version, "isolated compiler-report PBO/config hashes and mission provenance", true, outputPath, error);
        Print("[HC Item Audit] complete=" + complete + "; output=" + outputPath + "; error=" + error);
    }
}
"""

GROUP_CHECKS_HOOK = b"""

// Hollow Country DISPOSABLE policy fixtures; no network/gameplay acceptance.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCDiagnosticExecuted = false;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCDiagnosticExecuted)
            return;
        m_HCDiagnosticExecuted = true;
        string error;
        Print("[HC Group Checks] BEGIN; synthetic policy fixtures only");
        bool result = HCGroupNativeChecks.Run(error);
        Print("[HC Group Checks] result=" + result + "; error=" + error + "; no network/gameplay acceptance");
    }
}
"""

_PURPOSES = {
    'selftests': ('disposable-diagnostic-selftests', DIAGNOSTIC_HOOK,
                  ["actual DIAG_DEVELOPER", "server mode", "unchanged HC PBO", "fresh profile epoch 900001"]),
    'item-audit': ('disposable-item-compatibility-audit', ITEM_AUDIT_HOOK,
                   ["server mode", "matching HCItemCompatibilityAudit PBO", "fresh profile outside Git", "inspect export completeness separately from startup"]),
    'group-checks': ('disposable-group-policy-checks', GROUP_CHECKS_HOOK,
                     ["server mode", "matching HCGroupNativeChecks PBO", "inspect fixture result separately from startup"]),
    # Hook text is generated per run by tools/setup/ce_probe.py and passed as `hook=`.
    'ce-probe': ('disposable-ce-probe', None,
                 ["server mode", "fresh storage and profiles", "inspect census completeness separately from startup"]),
}

_FACTORY = re.compile(
    rb"(Mission\s+CreateCustomMission\s*\(\s*string\s+path\s*\)\s*"
    rb"\{\s*return\s+new\s+)CustomMission(\s*\(\s*\)\s*;\s*\})")


def _safe_path(value):
    path = Path(value).absolute()
    if ".." in path.parts:
        raise ValueError("parent traversal forbidden")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink paths/ancestors forbidden")
    if any(part.casefold() in {"steamapps", ".git"} for part in path.parts):
        raise ValueError("mission must be outside Steam/source")
    checkout = Path(__file__).absolute().parents[2]
    if path == checkout or checkout in path.parents:
        raise ValueError("mission must be outside source checkout")
    return path


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _unchanged(path, expected):
    _safe_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or _identity(info) != _identity(expected):
        raise ValueError("source changed during staging")


def _inventory(source):
    files, directories, pending = [], [], [(source, 0)]
    entries = total = 0
    while pending:
        directory, depth = pending.pop()
        children = []
        with os.scandir(directory) as scan:
            for entry in scan:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError("mission entry budget exceeded")
                children.append(Path(entry.path))
        for path in sorted(children):
            _safe_path(path)
            relative = path.relative_to(source)
            info = path.lstat()
            if path.name == MARKER_NAME or "HCDisposableDiagnosticMission" in path.name:
                raise ValueError("previously instrumented source forbidden")
            if stat.S_ISDIR(info.st_mode):
                if depth + 1 > MAX_DEPTH:
                    raise ValueError("mission depth budget exceeded")
                directories.append(relative)
                pending.append((path, depth + 1))
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if info.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise ValueError("mission byte budget exceeded")
                files.append((relative, info))
            else:
                raise ValueError("only regular files/directories allowed")
    return sorted(files), sorted(directories), total


def _hook_for(purpose, hook):
    fixed = _PURPOSES[purpose][1]
    if fixed is not None:
        if hook is not None:
            raise ValueError("this diagnostic purpose has a fixed hook")
        return fixed
    if not isinstance(hook, bytes) or not hook or len(hook) > MAX_HOOK_BYTES:
        raise ValueError("bounded generated hook bytes required for this purpose")
    return hook


def _instrument(blob, *, purpose='selftests', hook=None):
    if purpose not in _PURPOSES:
        raise ValueError('unsupported diagnostic purpose')
    body = _hook_for(purpose, hook)
    if len(blob) > MAX_INIT_BYTES:
        raise ValueError("init.c byte budget exceeded")
    if b"HCDisposableDiagnosticMission" in blob or b"[HC Diagnostic Mission]" in blob:
        raise ValueError("previously instrumented init.c forbidden")
    if len(re.findall(rb"\bclass\s+CustomMission\s*:\s*MissionServer\b", blob)) != 1:
        raise ValueError("expected stock CustomMission inheritance")
    if len(re.findall(rb"\bCreateCustomMission\s*\(", blob)) != 1:
        raise ValueError("expected exactly one stock mission factory")
    result, count = _FACTORY.subn(rb"\g<1>HCDisposableDiagnosticMission\g<2>", blob)
    if count != 1:
        raise ValueError("unsupported stock mission factory shape")
    return result + body


def prepare_diagnostic_mission(source, destination, *, purpose='selftests', hook=None):
    """Return/write provenance for a fresh isolated mission, without engine launch.

    Source must be an unmodified stock-shaped Chernarus mission in an isolated
    cache. Destination must not exist, including dangling symlinks. All static
    validation precedes creation. Runtime storage uses the server's fresh profile;
    epoch 900001 must be absent there (the existing native probe enforces this).
    This helper does not edit settings, feature flags, profiles or the addon PBO.
    """
    if purpose not in _PURPOSES:
        raise ValueError('unsupported diagnostic purpose')
    hook = _hook_for(purpose, hook)
    source, destination = _safe_path(source), _safe_path(destination)
    if not source.is_dir():
        raise ValueError("source mission directory required")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    files, directories, total = _inventory(source)
    initial = next((info for name, info in files if name.as_posix() == "init.c"), None)
    if initial is None or initial.st_size > MAX_INIT_BYTES:
        raise ValueError("bounded stock init.c required")
    init_path = source / "init.c"
    _unchanged(init_path, initial)
    with init_path.open("rb") as stream:
        original = stream.read(MAX_INIT_BYTES + 1)
    _unchanged(init_path, initial)
    instrumented = _instrument(original, purpose=purpose, hook=None if _PURPOSES[purpose][1] is not None else hook)
    # Validate parents again immediately before mutation; never clean failed output.
    _safe_path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for relative in directories:
        (destination / relative).mkdir(exist_ok=False)
    kind, _fixed, requires = _PURPOSES[purpose]
    manifest = {"schema": 1, "kind": kind,
                "runtime_acceptance": "pending", "source_root": str(source),
                "mission_path": str(destination), "storage_probe_epoch": 900001 if purpose == 'selftests' else None,
                "source_bytes": total, "files": {},
                "init_change": "stock factory subclass substitution plus authored appended OnInit hook",
                "hook_sha256": hashlib.sha256(hook).hexdigest(),
                "requires": list(requires)}
    for relative, info in files:
        src, dst = source / relative, destination / relative
        _unchanged(src, info)
        digest = hashlib.sha256()
        if relative.as_posix() == "init.c":
            digest.update(original)
            with dst.open("xb") as output:
                output.write(instrumented)
            staged_hash = hashlib.sha256(instrumented).hexdigest()
            staged_bytes = len(instrumented)
        else:
            remaining = info.st_size
            with src.open("rb") as stream, dst.open("xb") as output:
                while remaining:
                    chunk = stream.read(min(131072, remaining))
                    if not chunk:
                        raise ValueError("source truncated during copy")
                    digest.update(chunk)
                    output.write(chunk)
                    remaining -= len(chunk)
                if stream.read(1):
                    raise ValueError("source grew during copy")
            staged_hash, staged_bytes = digest.hexdigest(), info.st_size
        _unchanged(src, info)
        manifest["files"][relative.as_posix()] = {
            "source_sha256": digest.hexdigest(), "staged_sha256": staged_hash,
            "source_bytes": info.st_size, "staged_bytes": staged_bytes}
    with (destination / MARKER_NAME).open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return manifest
