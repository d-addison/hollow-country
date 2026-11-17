"""Stage an explicitly disposable diagnostic mission; never launch the engine.

Only the stock factory return type and an appended authored subclass change.
Purchased mission contents remain outside source/Steam; provenance contains hashes.
Failed partial output is preserved and cannot be reused or overwritten.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

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
    # Generated per run by tools/setup/taped_light_probe.py (same `hook=` contract as ce-probe).
    'taped-light-probe': ('disposable-taped-light-probe', None,
                          ["server mode", "fresh storage and profiles", "no clients",
                           "inspect observation completeness separately from startup"]),
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


# ---------------------------------------------------------------------------
# Directory-descriptor anchored file access
#
# Every operation below walks its path from "/" one component at a time, opening each directory with
# O_DIRECTORY|O_NOFOLLOW relative to the previous descriptor, and acts on the leaf through that last
# descriptor (dir_fd=, follow_symlinks=False, O_NOFOLLOW). A symlink swapped in for a component BEFORE that
# component is opened is refused by the kernel in that very call; there is no check-then-use gap on a path
# string. Concurrency contract (narrower than "at any moment"): a directory renamed AFTER it was opened keeps
# being used through its descriptor, so one leaf written in that window lands in the moved directory, outside
# the requested destination; only a protected directory/ancestor namespace could prevent that, and staging
# only guarantees that such a run ends refused with no plan. What the final tree scan (walk_plain) does add is
# that every directory it read, the root and its ancestors included, is reopened without following links and
# must still be the same (st_dev, st_ino) before the scan can certify the tree.
# Residual on a DrvFs/9p mount (/mnt/d): O_NOFOLLOW/O_DIRECTORY and *at() calls are served by the WSL
# kernel, but NTFS junctions and reparse points are interpreted by the Windows side, which these calls
# cannot see; a Windows-side process that replaces a directory by a junction between two of our calls is
# not detectable here. The Windows launcher re-verifies the staged tree before it launches anything, and
# tests/unit/test_probe_runtime.py pins this residual explicitly.
# ---------------------------------------------------------------------------

_DIRECTORY_FLAGS = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0))
_LINK_ERRORS = frozenset({errno.ELOOP, errno.ENOTDIR})


def require_fd_anchoring():
    """Staging needs directory-descriptor operations; refuse anywhere else (stage only on Linux/WSL)."""
    needed = (os.open, os.mkdir, os.stat, os.unlink)
    if not sys.platform.startswith("linux") or not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW") \
            or any(function not in os.supports_dir_fd for function in needed):
        raise ValueError("staging requires directory-descriptor operations (Linux/WSL only)")


def _link_refused(error, name):
    if error.errno in _LINK_ERRORS:
        return ValueError(f"symlinked or non-directory path component refused: {name}")
    return error


def _open_child_dir(parent_fd, name):
    try:
        return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise _link_refused(error, name) from error


def open_dir_at(path):
    """Descriptor of a directory reached from "/" without following any symlink component."""
    require_fd_anchoring()
    path = Path(path).absolute()
    descriptor = os.open("/", _DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            child = _open_child_dir(descriptor, part)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def open_file_at(path, flags, mode=0o666):
    """os.open() of a leaf under a no-follow directory walk; the leaf itself is never followed either."""
    path = Path(path).absolute()
    parent = open_dir_at(path.parent)
    try:
        return os.open(path.name, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), mode,
                       dir_fd=parent)
    except OSError as error:
        raise _link_refused(error, path.name) from error
    finally:
        os.close(parent)


def lstat_at(path):
    """lstat of ``path`` with every ancestor opened without following links."""
    path = Path(path).absolute()
    parent = open_dir_at(path.parent)
    try:
        return os.stat(path.name, dir_fd=parent, follow_symlinks=False)
    finally:
        os.close(parent)


def mkdir_at(path, *, parents=False):
    """Create one new directory (never an existing one) under a no-follow walk; parents are created the same way."""
    path = Path(path).absolute()
    require_fd_anchoring()
    descriptor = os.open("/", _DIRECTORY_FLAGS)
    try:
        components = path.parts[1:]
        for index, part in enumerate(components):
            last = index == len(components) - 1
            if last:
                os.mkdir(part, dir_fd=descriptor)
                return
            try:
                child = _open_child_dir(descriptor, part)
            except FileNotFoundError:
                if not parents:
                    raise
                os.mkdir(part, dir_fd=descriptor)
                child = _open_child_dir(descriptor, part)
            os.close(descriptor)
            descriptor = child
        raise FileExistsError(str(path))
    finally:
        os.close(descriptor)


def unlink_at(path):
    path = Path(path).absolute()
    parent = open_dir_at(path.parent)
    try:
        os.unlink(path.name, dir_fd=parent)
    finally:
        os.close(parent)


def create_exclusive(path, data):
    """Create a new file with exactly ``data`` (O_EXCL, no-follow walk); an existing name is an error."""
    descriptor = open_file_at(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def walk_plain(root):
    """{relative posix path: size} of every regular file under ``root``; links and special files are refused.

    The final lstat-walk backstop over a staged tree: every directory is opened no-follow and every entry is
    classified through that descriptor, so a swapped-in symlink cannot be mistaken for the file it replaced.
    """
    root = Path(root).absolute()
    files, pending, count = {}, [(open_dir_at(root), "")], 0
    opened = {}   # directory prefix -> (st_dev, st_ino) of the descriptor that was scanned
    try:
        while pending:
            descriptor, prefix = pending.pop()
            try:
                info = os.fstat(descriptor)
                opened[prefix] = (info.st_dev, info.st_ino)
                with os.scandir(descriptor) as scan:
                    names = sorted(entry.name for entry in scan)
                for name in names:
                    count += 1
                    if count > 4 * MAX_ENTRIES:
                        raise ValueError("staged tree entry budget exceeded")
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    relative = prefix + name
                    if stat.S_ISDIR(info.st_mode):
                        pending.append((_open_child_dir(descriptor, name), relative + "/"))
                    elif stat.S_ISREG(info.st_mode):
                        files[relative] = info.st_size
                    else:
                        raise ValueError(f"staged tree contains a link or special file: {relative}")
            finally:
                os.close(descriptor)
    finally:
        for descriptor, _prefix in pending:
            os.close(descriptor)
    _require_directories_in_place(root, opened)
    return files


def _require_directories_in_place(root, opened):
    """Every directory the scan read must still occupy its name; refuse a displaced or replaced one.

    A scan reads through descriptors, so a directory renamed after it was opened (and a symlink or other
    directory put under its name) would still be listed as if it were in place. After the scan, ``root`` is
    reopened from "/" without following links and each scanned directory is reopened through its retained
    parent, and the (st_dev, st_ino) must equal what was scanned. This covers the root and every ancestor of it
    too, since the reopen starts at "/". It closes the window up to this call only; see the concurrency
    contract in the comment block above.
    """
    held = {}
    try:
        for prefix in sorted(opened):               # a parent sorts before its children
            try:
                if prefix:
                    parent, _, name = prefix[:-1].rpartition("/")
                    descriptor = _open_child_dir(held[parent + "/" if parent else ""], name)
                else:
                    descriptor = open_dir_at(root)
            except (OSError, ValueError) as error:
                raise ValueError(f"staged directory was displaced during the scan: {prefix or '.'}") from error
            held[prefix] = descriptor
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != opened[prefix]:
                raise ValueError(f"staged directory was replaced during the scan: {prefix or '.'}")
    finally:
        for descriptor in held.values():
            os.close(descriptor)


def _unchanged(path, expected):
    _safe_path(path)
    info = lstat_at(path)
    if not stat.S_ISREG(info.st_mode) or _identity(info) != _identity(expected):
        raise ValueError("source changed during staging")


def _inventory(source):
    files, directories = [], []
    entries = total = 0
    source = Path(source)
    pending = [(open_dir_at(source), Path(), 0)]
    try:
        while pending:
            descriptor, directory, depth = pending.pop()
            try:
                children = []
                with os.scandir(descriptor) as scan:
                    for entry in scan:
                        entries += 1
                        if entries > MAX_ENTRIES:
                            raise ValueError("mission entry budget exceeded")
                        children.append(entry.name)
                for name in sorted(children):
                    relative = directory / name
                    _safe_path(source / relative)
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if name == MARKER_NAME or "HCDisposableDiagnosticMission" in name:
                        raise ValueError("previously instrumented source forbidden")
                    if stat.S_ISDIR(info.st_mode):
                        if depth + 1 > MAX_DEPTH:
                            raise ValueError("mission depth budget exceeded")
                        child = _open_child_dir(descriptor, name)
                        opened = os.fstat(child)
                        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                            os.close(child)
                            raise ValueError("source changed during staging")
                        directories.append(relative)
                        pending.append((child, relative, depth + 1))
                    elif stat.S_ISREG(info.st_mode):
                        total += info.st_size
                        if info.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                            raise ValueError("mission byte budget exceeded")
                        files.append((relative, info))
                    else:
                        raise ValueError("only regular files/directories allowed")
            finally:
                os.close(descriptor)
    finally:
        for descriptor, _directory, _depth in pending:
            os.close(descriptor)
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


def _reread_digest(path):
    """Digest of the bytes now on disk at ``path`` (re-read, never the bytes just written)."""
    digest = hashlib.sha256()
    with os.fdopen(open_file_at(path, os.O_RDONLY), "rb") as stream:     # a staged symlink is refused here
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"staged path is not a regular file: {Path(path).name}")
        for chunk in iter(lambda: stream.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_admitted(files, directories, admitted):
    """The inventory found now must equal the verified inventory: same names, sizes, directories."""
    expected = admitted["files"]
    found = {name.as_posix(): info.st_size for name, info in files}
    if set(found) != set(expected) or sorted(d.as_posix() for d in directories) != sorted(admitted["directories"]):
        raise ValueError("mission inventory differs from the admitted inventory")
    for name, size in found.items():
        if expected[name][1] != size:
            raise ValueError(f"mission file size differs from the admitted inventory: {name}")


def _open_admitted(path, info):
    """Open a source file for copying without following a symlink anywhere on its path; refuse identity drift."""
    try:
        descriptor = open_file_at(path, os.O_RDONLY)
    except OSError as error:
        raise ValueError("source changed or is a link during staging") from error
    stream = os.fdopen(descriptor, "rb")
    opened = os.fstat(stream.fileno())
    if not stat.S_ISREG(opened.st_mode) or _identity(opened) != _identity(info):
        stream.close()
        raise ValueError("source changed during staging")
    return stream


def prepare_diagnostic_mission(source, destination, *, purpose='selftests', hook=None, admitted=None,
                               entry_check=None):
    """Return/write provenance for a fresh isolated mission, without engine launch.

    Source must be an unmodified stock-shaped Chernarus mission in an isolated
    cache. Destination must not exist, including dangling symlinks. All static
    validation precedes creation. Runtime storage uses the server's fresh profile;
    epoch 900001 must be absent there (the existing native probe enforces this).
    This helper does not edit settings, feature flags, profiles or the addon PBO.

    ``admitted`` ({"files": {name: (sha256, size)}, "directories": [name]}) pins the
    inventory verified by the caller: files or directories that appeared, vanished or changed
    afterwards are refused, copied bytes are hashed against it and every written file is
    re-read. ``entry_check(relative, directory=bool)`` may refuse entries by policy. Both
    default to off so existing callers are unchanged.
    """
    if purpose not in _PURPOSES:
        raise ValueError('unsupported diagnostic purpose')
    hook = _hook_for(purpose, hook)
    require_fd_anchoring()
    source, destination = _safe_path(source), _safe_path(destination)
    if not source.is_dir():
        raise ValueError("source mission directory required")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source/destination overlap forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination must be fresh; no overwrite")
    files, directories, total = _inventory(source)
    if entry_check is not None:
        for relative in directories:
            entry_check(relative, directory=True)
        for relative, _info in files:
            entry_check(relative)
    if admitted is not None:
        _require_admitted(files, directories, admitted)
    initial = next((info for name, info in files if name.as_posix() == "init.c"), None)
    if initial is None or initial.st_size > MAX_INIT_BYTES:
        raise ValueError("bounded stock init.c required")
    init_path = source / "init.c"
    _unchanged(init_path, initial)
    with _open_admitted(init_path, initial) as stream:
        original = stream.read(MAX_INIT_BYTES + 1)
    _unchanged(init_path, initial)
    if admitted is not None and hashlib.sha256(original).hexdigest() != admitted["files"]["init.c"][0]:
        raise ValueError("init.c differs from the admitted hash")
    instrumented = _instrument(original, purpose=purpose, hook=None if _PURPOSES[purpose][1] is not None else hook)
    # Validate parents again immediately before mutation; never clean failed output.
    _safe_path(destination)
    mkdir_at(destination, parents=True)
    for relative in directories:
        mkdir_at(destination / relative)
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
            _create_staged(dst, instrumented)
            staged_hash = hashlib.sha256(instrumented).hexdigest()
            staged_bytes = len(instrumented)
        else:
            remaining = info.st_size
            with _open_admitted(src, info) as stream, _staged_output(dst) as output:
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
        if admitted is not None:
            if digest.hexdigest() != admitted["files"][relative.as_posix()][0]:
                raise ValueError(f"source differs from the admitted hash: {relative.as_posix()}")
            if _reread_digest(dst) != staged_hash:
                raise ValueError(f"written bytes differ from the verified bytes: {relative.as_posix()}")
        manifest["files"][relative.as_posix()] = {
            "source_sha256": digest.hexdigest(), "staged_sha256": staged_hash,
            "source_bytes": info.st_size, "staged_bytes": staged_bytes}
    create_exclusive(destination / MARKER_NAME, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _require_staged_tree(destination, manifest)
    return manifest


def _staged_output(path):
    """New file (O_EXCL, no-follow walk) opened for writing the copied bytes."""
    return os.fdopen(open_file_at(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb")


def _create_staged(path, data):
    create_exclusive(path, data)


def _require_staged_tree(destination, manifest):
    """Final backstop: the staged tree holds exactly the manifest's regular files, with no link or special file."""
    found = walk_plain(destination)
    expected = {name: entry["staged_bytes"] for name, entry in manifest["files"].items()}
    marker = found.pop(MARKER_NAME, None)
    if marker is None or found != expected:
        raise ValueError("staged mission tree differs from the manifest")
