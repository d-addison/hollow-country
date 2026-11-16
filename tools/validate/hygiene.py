"""Bounded private-repository hygiene; no network, secret excerpts or legal approval.

Run ``python3 -B -m tools.validate.hygiene`` from a Git checkout. Scan working
bytes of tracked and unignored files, including force-added ignored files. Ignored
local caches, game installs and Git history are outside this check. SHA-256 binds
the scanned bytes, not authorship or redistribution rights. Required governance
documents and the user's private/all-rights-reserved notice are linted; third-party
rights still need human review. A pass never authorizes publication or DayZ use.

Secret detection deliberately covers precise private-key headers and GitHub token
formats, not entropy or generic password guesses. Findings contain only rule,
sanitized path and line; rejected content is neither echoed nor hashed in output.
Local inline/image/full-reference Markdown file links are checked against admitted
repository candidates. Remote URLs, heading fragments, shortcut references and
complex CommonMark constructs require manual review; no URL is fetched.

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
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    r"|(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36}(?![A-Za-z0-9_])"
    r"|(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}(?![A-Za-z0-9_])"
)
_LICENSE_MARKERS = (
    "Copyright (c) 2026 David Addison", "All rights reserved.",
    "No open-source or public reuse license is granted.",
    "Third-party materials remain subject to their owners' terms.",
)


def _candidates(root):
    def git(*args):
        with subprocess.Popen(["git", "-C", str(root), *args],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
            def stop():
                try:
                    child.kill()
                except OSError:
                    pass
            timer = threading.Timer(15, stop)
            timer.daemon = True
            timer.start()
            try:
                data = child.stdout.read(MAX_DISCOVERY_BYTES + 1)
                if len(data) > MAX_DISCOVERY_BYTES or child.wait(timeout=1) != 0:
                    raise ValueError("Git discovery limit or failure")
            finally:
                timer.cancel()
                stop()
                child.wait(timeout=5)
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


def _restricted(relative):
    path = PurePosixPath(relative.lower())
    return (path.suffix in _PRIVATE_SUFFIXES
            or any(p in _PRIVATE_DIRECTORIES or p.startswith("storage_") for p in path.parts[:-1])
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc"})


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
    for relative in candidates:
        if _SECRET.search(relative):
            error("credential_path", relative)
            continue
        if _restricted(relative):
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
            license_info["project"] = "private-all-rights-reserved"
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
    return report()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = check_repository(args.root)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return int(not result["valid"])


if __name__ == "__main__":
    raise SystemExit(main())
