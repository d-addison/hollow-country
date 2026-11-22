"""Bounded repository hygiene; no network, secret excerpts or legal approval.

Run ``python3 -B -m tools.validate.hygiene`` from a Git checkout. Scan working
bytes of tracked and unignored files, including force-added ignored files. Ignored
local caches, game installs and Git history are outside this check. SHA-256 binds
the scanned bytes, not authorship or redistribution rights. Required governance
documents and the user's all-rights-reserved notice are linted; third-party
rights still need human review. A pass never authorizes publication or DayZ use.

Secret detection deliberately covers precise private-key headers and GitHub token
formats, not entropy or generic password guesses. Findings contain only rule,
sanitized path and line; rejected content is neither echoed nor hashed in output.
Local inline/image/full-reference Markdown file links are checked against admitted
repository candidates. Remote URLs, heading fragments, shortcut references and
complex CommonMark constructs require manual review; no URL is fetched.

Packaged roots (mods/, mission/, config/) are also scanned for the banned provider tokens
in tools.package.inventory_sources.BANNED, in file names and text lines. Findings carry
rule, path and line only. One narrow exemption exists: the keys of
config/generated-digests.json are repository file names and generator names that
legitimately contain a banned token (tools/package/snafu_allowlist.json and similar),
so only that file's string values are scanned. Renaming the keys would mean renaming
the tools that own them. Any other banned token in that file still fails.

POSIX reads use anchored no-follow directory descriptors. Other hosts use link/
reparse checks and before/after file identity checks and require an immutable
checkout during scanning; this utility is not a hostile-filesystem sandbox.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import threading
from urllib.parse import unquote, urlsplit

from tools.package.inventory_sources import safe_text

ROOT = Path(__file__).resolve().parents[2]
_SPEC_ALIAS = "docs/specs/001-survival-overhaul/spec.md"
MAX_FILES = 8192
MAX_DISCOVERY_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
REQUIRED_DOCUMENTS = (
    "README.md", "LICENSE.md", "docs/SOURCES.md", "docs/MODULE_STATUS.md",
    "docs/PROVENANCE_AND_LICENSES.md",
)
_PRIVATE_SUFFIXES = {
    ".biprivatekey", ".bikey", ".key", ".pem", ".pfx", ".p12", ".token", ".secret",
    ".pbo", ".bisign", ".p3d", ".paa", ".edds", ".rvmat", ".wrp", ".rap",
    ".exe", ".dll", ".so", ".dylib", ".zip", ".7z", ".rar", ".gz",
    ".mdmp", ".dmp", ".rpt", ".adm", ".log", ".sqlite", ".db",
}
_PRIVATE_DIRECTORIES = {
    "secrets", "profiles", "logs", "server_runtime", "client_runtime",
    "project_drive", "p_drive", "third_party", "workshop_mods", "steamapps",
    "dayz", "dayz_tools",
}
_DUMP_NAMES = {"mapgrouppos.xml", "mapgroupproto.xml", "cfgspawnabletypes.xml",
               "cfgrandompresets.xml", "cfgeventspawns.xml"}
BANNED_ROOTS = ("mods/", "mission/", "config/")
# Exemption (see module docstring): keys here are repository file names, not shipped data.
DIGEST_KEYS_FILE = "config/generated-digests.json"
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    r"|(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36}(?![A-Za-z0-9_])"
    r"|(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}(?![A-Za-z0-9_])"
)
# Personal absolute home paths (POSIX, macOS, Windows, WSL and Wine Z:). Portable
# placeholders (<user>, $HOME, {user}) and the hosted CI runner home are allowed.
_LOCAL_HOME = re.compile(
    r"(?:(?<![A-Za-z0-9_.])/(?:home|Users)/|/mnt/[A-Za-z]/Users/|[A-Za-z]:[\\/]+(?:Users|home)[\\/]+)"
    r"(?![<${]|runner[\\/])[A-Za-z0-9._-]+[\\/]",
    re.IGNORECASE,
)
_LICENSE_MARKERS = (
    "Copyright (c) 2026 David Addison", "All rights reserved.",
    "No open-source or public reuse license is granted.",
    "Third-party materials remain subject to their owners' terms.",
)


def _candidates(root):
    def git(*args):
        timed_out = threading.Event()
        with subprocess.Popen(["git", "-C", str(root), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
            def stop():
                try:
                    if child.poll() is None:
                        if os.name == 'nt':
                            # Git for Windows may launch a native child. Killing
                            # only its wrapper can leave that child holding -C.
                            try:
                                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                               stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL, timeout=5)
                            except (OSError, subprocess.SubprocessError):
                                pass  # Still terminate/reap the owned launcher.
                        child.kill()
                except OSError:
                    pass
            def watchdog():
                timed_out.set()
                stop()
            timer = threading.Timer(15, watchdog)
            timer.daemon = True
            timer.start()
            try:
                data = child.stdout.read(MAX_DISCOVERY_BYTES + 1)
                if len(data) > MAX_DISCOVERY_BYTES or child.wait(timeout=1) != 0:
                    raise ValueError("Git discovery limit or failure")
            finally:
                timer.cancel()
                # Close before terminating: an oversized writer can finish via
                # broken-pipe handling, allowing its wrapper to reap it normally.
                child.stdout.close()
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    stop()
                    child.wait(timeout=5)
                finally:
                    timer.join(timeout=6)
        if timed_out.is_set():
            raise ValueError('Git discovery timeout')
        return data.decode("utf-8", errors="strict")
    if Path(git("rev-parse", "--show-toplevel").strip()).resolve() != root.resolve():
        raise ValueError("not checkout root")
    return sorted(set(git("ls-files", "-z", "--cached", "--others",
                          "--exclude-standard").rstrip("\0").split("\0")) - {""})


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_nlink, info.st_mode, getattr(info, "st_file_attributes", 0))


def _inspect(root, relative):
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute() or "\\" in relative
            or any(p in (".", "..") or ":" in p for p in parts)
            or PurePosixPath(relative).as_posix() != relative):
        raise ValueError("unsafe path")
    current = root
    for part in (None, *parts):
        if part is not None:
            current = current / part
        info = current.lstat()
        if _linked(info):
            raise ValueError("linked path")
        if current != root / relative and not stat.S_ISDIR(info.st_mode):
            raise ValueError("non-directory ancestor")
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("non-private regular file")
    return info


def _read(root, relative, expected):
    """Read at most the per-file limit plus one byte, with identity validation."""
    descriptors = []
    try:
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptors.append(os.open(root, directory_flags))
            parts = PurePosixPath(relative).parts
            for part in parts[:-1]:
                descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
            descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=descriptors[-1])
        else:
            _inspect(root, relative)
            descriptor = os.open(root / relative, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        with os.fdopen(descriptor, "rb") as stream:
            if _identity(os.fstat(stream.fileno())) != _identity(expected):
                raise ValueError("changed before read")
            data = stream.read(min(MAX_FILE_BYTES, expected.st_size) + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("grew beyond limit")
            if (_identity(os.fstat(stream.fileno())) != _identity(expected)
                    or _identity(_inspect(root, relative)) != _identity(expected)
                    or len(data) != expected.st_size):
                raise ValueError("changed during read")
            return data
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


# Original generated GUI icons are the only admitted binaries: each path must sit in
# one of these two folders and match a SHA-256 pinned in the provenance manifest
# written by tools.package.gui_icons. Anything else binary stays refused.
_ICON_MANIFEST = "art/gui-icons/manifest.json"
_ICON_PATHS = re.compile(r"(?:art/gui-icons/[a-z_]+\.png|mods/HollowCountry/gui/icons/map/[a-z_]+\.paa)")


def _pinned_icons(root):
    """Return {relative: sha256} from the icon manifest, or {} if absent/invalid."""
    try:
        data = json.loads((Path(root) / _ICON_MANIFEST).read_text(encoding="utf-8"))
        pinned = {}
        for entry in data["icons"].values():
            for key in ("source", "paa"):
                path, digest = entry[key], entry[key + "_sha256"]
                if _ICON_PATHS.fullmatch(path) and re.fullmatch(r"[0-9a-f]{64}", digest):
                    pinned[path] = digest
        return pinned
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _restricted(relative):
    path = PurePosixPath(relative.lower())
    return (path.suffix in _PRIVATE_SUFFIXES
            or any(p in _PRIVATE_DIRECTORIES or p.startswith("storage_") for p in path.parts[:-1])
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc"})


def _json_strings(value):
    """Yield string values only; dict keys are skipped."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def banned_text_line(relative, text):
    """First 1-based line holding a banned token, 0 if clean, None if not applicable."""
    if not relative.startswith(BANNED_ROOTS):
        return None
    if relative == DIGEST_KEYS_FILE:
        try:
            values = list(_json_strings(json.loads(text)))
        except ValueError:
            values = None  # Unparseable: scan the raw text so nothing is exempt.
        if values is not None:
            return 0 if all(safe_text(v) for v in values) else 1
    for number, line in enumerate(text.splitlines(), 1):
        if not safe_text(line):
            return number
    return 0


def _target(token):
    match = re.match(r"\s*(?:<([^>]+)>|(\S+))", token)
    return (match[1] or match[2]) if match else ""


def _markdown_links(text):
    """Yield (line, target, error); intentionally a limited file-link grammar."""
    lines, definitions, fence = [], {}, None
    for number, raw in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", raw)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence is not None or raw.startswith("    ") or raw.startswith("\t"):
            continue
        line = re.sub(r"(`+).*?\1", "", raw)
        definition = re.match(r"^\s{0,3}\[([^]]+)\]:\s*(.+)$", line)
        if definition:
            definitions[definition[1].casefold()] = _target(definition[2])
            # Definitions themselves are links even without a full reference.
            lines.append((number, "definition", _target(definition[2]), ""))
            continue
        for match in re.finditer(r"!?\[[^]\n]*\]\((<[^>]*>|[^)\n]*)\)", line):
            lines.append((number, "inline", _target(match[1]), ""))
        for match in re.finditer(r"!?\[([^]\n]+)\]\[([^]\n]*)\]", line):
            lines.append((number, "reference", "", (match[2] or match[1]).casefold()))
    for number, kind, target, key in lines:
        if kind == "reference":
            target = definitions.get(key)
            if target is None:
                yield number, "", "documentation_reference"
                continue
        yield number, target, None


def _expected_mod_line(root):
    """The full -mod line the friend bundle writes (every manifest group, rank order)."""
    from tools.setup import workshop_sync as ws
    manifest = ws.load_manifest(Path(root) / "tools" / "setup" / "workshop_mods.json")
    lines = [line for line in ws.launch_lines(ws.select(manifest, ws.GROUPS)) if line.startswith("-mod=")]
    return lines[0] if lines else None


def stale_mod_lines(root, documents):
    """(path, line) for every documented full -mod list that differs from workshop_mods.json."""
    documented = []
    for relative, text in documents.items():
        for number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip().strip("`")
            if line.startswith("-mod=@CF;"):
                documented.append((relative, number, line))
    if not documented:
        return []
    expected = _expected_mod_line(root)  # a documented list needs a readable manifest
    return [(relative, number) for relative, number, line in documented if line != expected]


def check_repository(root=ROOT):
    root = Path(root).absolute()
    errors, inventory, documents, inspected, aliases = [], [], {}, {}, {}

    def error(code, path="", line=0):
        # Do not emit a token embedded in a malicious filename either.
        if _SECRET.search(path):
            path = "<redacted-path>"
        errors.append({"code": code, "path": path, "line": line})

    license_info = {"project": "missing", "third_party_rights": "pending-human-review",
                    "publication_authorized": False}

    def report():
        return {"report_version": 1, "valid": not errors,
                "scope": "working-tree hygiene; not authorship, rights or runtime acceptance",
                "license": license_info, "inventory": sorted(inventory, key=lambda x: x["path"]),
                "errors": sorted(errors, key=lambda e: (e["path"], e["code"], e["line"]))}

    try:
        if _linked(root.lstat()):
            raise ValueError("linked root")
        candidates = _candidates(root)
    except (OSError, ValueError, subprocess.SubprocessError):
        error("repository_discovery")
        return report()
    if len(candidates) > MAX_FILES:
        error("entry_limit")
        return report()
    total = 0
    pinned = _pinned_icons(root)
    for relative in candidates:
        if _SECRET.search(relative):
            error("credential_path", relative)
            continue
        if relative.startswith(BANNED_ROOTS) and not safe_text(relative):
            error("banned_text", relative)
            continue
        if _restricted(relative) and relative not in pinned:
            error("restricted_path", relative)
            continue
        if (PurePosixPath(relative.lower()).name in _DUMP_NAMES
                and not relative.startswith("tests/fixtures/ce/synthetic_")):
            error("vanilla_dump_path", relative)
            continue
        try:
            # Banso's one tracked convenience alias is admitted by its exact
            # relative link bytes, never opened through the link. Its target
            # must independently pass the ordinary reader below. Git on Windows
            # may check this out as a plain text file instead, already safe.
            if relative == "spec.md" and stat.S_ISLNK((root / relative).lstat().st_mode):
                target = os.readlink(root / relative)
                if target != _SPEC_ALIAS:
                    raise ValueError("redirected spec alias")
                aliases[relative] = target.encode("utf-8")
                continue
            info = _inspect(root, relative)
        except (OSError, ValueError):
            error("unsafe_file", relative)
            continue
        total += info.st_size
        if info.st_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            error("size_limit", relative)
            continue
        inspected[relative] = info
    # Complete metadata admission precedes opening any candidate content.
    if any(e["code"] == "size_limit" for e in errors):
        return report()
    for relative, info in inspected.items():
        try:
            data = _read(root, relative, info)
        except (OSError, ValueError):
            error("unsafe_file", relative)
            continue
        if relative in pinned:
            digest = hashlib.sha256(data).hexdigest()
            if digest != pinned[relative]:
                error("pinned_binary_mismatch", relative)
            else:
                inventory.append({"path": relative, "kind": "pinned-icon",
                                  "bytes": len(data), "sha256": digest})
            continue
        try:
            if data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                text = data.decode("utf-8-sig")
            if "\0" in text or data.startswith((b"MZ", b"PK\x03\x04", b"\x7fELF")):
                raise ValueError("binary input")
        except (UnicodeError, ValueError):
            error("binary_content", relative)
            continue
        match = _SECRET.search(text)
        if match:
            # Emit at most one finding per file; never include bytes or their hash.
            error("credential_content", relative, text.count("\n", 0, match.start()) + 1)
            continue
        banned = banned_text_line(relative, text)
        if banned:
            # Rule, path and line only; the token itself is never echoed.
            error("banned_text", relative, banned)
            continue
        home = _LOCAL_HOME.search(text)
        if home:
            # Same disclosure rule as credentials: rule, path and line only.
            error("local_absolute_path", relative, text.count("\n", 0, home.start()) + 1)
            continue
        inventory.append({"path": relative, "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
        if relative.lower().endswith(".md"):
            documents[relative] = text
    admitted = {item["path"] for item in inventory}
    for relative, data in aliases.items():
        if _SPEC_ALIAS in admitted:
            inventory.append({"path": relative, "kind": "repository-alias",
                              "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            admitted.add(relative)
        else:
            error("unsafe_file", relative)
    for required in REQUIRED_DOCUMENTS:
        if required not in admitted:
            error("required_document", required)
    if "LICENSE.md" in documents:
        if all(marker in documents["LICENSE.md"] for marker in _LICENSE_MARKERS):
            license_info["project"] = "all-rights-reserved"
        else:
            license_info["project"] = "policy-mismatch"
            error("license_policy", "LICENSE.md")
    for relative, text in documents.items():
        for line, target, problem in _markdown_links(text):
            if problem:
                error(problem, relative, line)
                continue
            try:
                url = urlsplit(target)
                if url.scheme in {"https", "http", "mailto"}:
                    continue
                if url.scheme or url.netloc:
                    raise ValueError("non-repository link")
                target_path = unquote(url.path)
                if not target_path:
                    continue  # Anchor-only links are explicitly outside file checks.
                if target_path.startswith("/") or "\\" in target_path or ":" in target_path:
                    raise ValueError("absolute path")
                parts = list(PurePosixPath(relative).parent.parts)
                for part in target_path.split("/"):
                    if part == "..":
                        if not parts:
                            raise ValueError("escaping path")
                        parts.pop()
                    elif part not in {"", "."}:
                        parts.append(part)
                resolved = "/".join(parts)
                if resolved not in admitted and not any(p.startswith(resolved + "/") for p in admitted):
                    error("documentation_target", relative, line)
            except ValueError:
                error("documentation_path", relative, line)
    try:
        for relative, line in stale_mod_lines(root, documents):
            error("stale_mod_line", relative, line)
    except Exception:  # an unreadable manifest is its own failure, never a silent pass
        error("mod_manifest", "tools/setup/workshop_mods.json")
    return report()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--summary", action="store_true",
                        help="print one line per finding and a verdict instead of the JSON report (used by preland)")
    args = parser.parse_args(argv)
    result = check_repository(args.root)
    if args.summary:
        for item in result["errors"]:
            print("hygiene: %s %s:%d" % (item["code"], item["path"], item["line"]))
        print("hygiene: %s files=%d errors=%d banned_text_roots=%s"
              % ("PASS" if result["valid"] else "FAIL", len(result["inventory"]), len(result["errors"]),
                 ",".join(r.rstrip("/") for r in BANNED_ROOTS)))
        return int(not result["valid"])
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return int(not result["valid"])


if __name__ == "__main__":
    raise SystemExit(main())
