"""Shared bounded observation helpers for the native adapters (spec 002 AV-T007 and AV-T008).

Everything here is read-only observation or confinement arithmetic: procfs and log reads, socket
table parsing, file guards and staging confinement. Nothing here launches a process, takes the host
lock or writes outside a root the caller names. Missing data is reported as unavailable, never zero.
Ownership is asserted by the caller (a launched child), and is observed here by parent links and
process groups with kernel start ticks, so a reused pid is not mistaken for an owned process.
"""
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import stat

MAX_PIDS = 32768
MAX_FDS = 4096
MAX_NET_BYTES = 4 * 1024 * 1024
MAX_NET_ROWS = 20000
MAX_LOG_FILES = 64
MAX_LOG_FILE = 16 * 1024 * 1024
MAX_LOG_TOTAL = 32 * 1024 * 1024
MAX_DISCOVERY = 512
MAX_GUARD_ENTRIES = 4096
LOG_SUFFIXES = frozenset({".log", ".rpt", ".adm"})
NET_TABLES = (("udp", "udp"), ("udp6", "udp6"), ("tcp", "tcp"), ("tcp6", "tcp6"))
WILDCARDS = frozenset({"0.0.0.0", "::"})
DEAD_STATES = frozenset({"Z", "X"})
SOCKET_LINK = re.compile(r"socket:\[(\d+)\]\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, limit=1 << 31):
    """Stream one regular file; a file larger than limit is refused, never truncated."""
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("bounded regular file required")
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


# --- Logs -------------------------------------------------------------------------------------

def read_logs(root):
    """Bounded snapshot of log files under root: ({name: {data, mtime_ns}}, {name: reason})."""
    files, skipped = {}, {}
    root = Path(root)
    if not root.is_dir():
        return files, skipped
    total, seen, count = 0, 0, 0
    for directory, names, filenames in os.walk(root, followlinks=False):
        names.sort()
        for filename in sorted(filenames):
            seen += 1
            if seen > MAX_DISCOVERY:
                skipped["*"] = "discovery budget exceeded"
                return files, skipped
            path = Path(directory) / filename
            if path.suffix.lower() not in LOG_SUFFIXES:
                continue
            name = path.relative_to(root).as_posix()
            count += 1
            try:
                info = os.lstat(path)
            except OSError:
                skipped[name] = "unreadable"
                continue
            if not stat.S_ISREG(info.st_mode):
                skipped[name] = "not a regular log"
                continue
            if count > MAX_LOG_FILES or info.st_size > min(MAX_LOG_FILE, MAX_LOG_TOTAL - total):
                skipped[name] = "log count or byte budget exceeded"
                continue
            try:
                with open(path, "rb") as stream:
                    data = stream.read(info.st_size + 1)
            except OSError:
                skipped[name] = "unreadable"
                continue
            if len(data) != info.st_size:
                skipped[name] = "log changed during bounded snapshot"
                continue
            total += len(data)
            files[name] = {"data": data, "mtime_ns": info.st_mtime_ns}
    return files, skipped


def logs_baseline(files):
    """Watermark of what a log directory already held: {name: (length, sha256)}."""
    return {name: (len(item["data"]), sha256_bytes(item["data"])) for name, item in files.items()}


def fresh_logs(files, baseline, started_ns):
    """Only text written after the watermark or after launch. Returns (text per file, rejected).

    A log absent from the baseline must have been written at or after started_ns. A log present in
    the baseline contributes only the bytes appended past its watermark, and only if its watermarked
    prefix is unchanged. Anything else is rejected by name with a reason, never silently counted.
    """
    texts, rejected = {}, {}
    for name, item in sorted(files.items()):
        data = item["data"]
        mark = baseline.get(name)
        if mark is None:
            if item["mtime_ns"] < started_ns:
                rejected[name] = "stale_older_than_launch"
                continue
            texts[name] = data.decode("utf-8", errors="replace")
            continue
        length, digest = mark
        if len(data) < length or sha256_bytes(data[:length]) != digest:
            rejected[name] = "rewritten_since_baseline"
            continue
        texts[name] = data[length:].decode("utf-8", errors="replace")
    return texts, rejected


# --- Processes and sockets --------------------------------------------------------------------

def read_stat(proc_root, pid):
    """(state, ppid, pgrp, start ticks) of one process, or None when it is gone or unreadable."""
    try:
        raw = (Path(proc_root) / str(pid) / "stat").read_text(errors="replace")[:4096]
    except OSError:
        return None
    fields = raw.rpartition(")")[2].split()
    if len(fields) < 20:
        return None
    try:
        return {"pid": pid, "state": fields[0], "ppid": int(fields[1]), "pgrp": int(fields[2]),
                "start": int(fields[19])}
    except ValueError:
        return None


def scan(proc_root="/proc"):
    """{pid: stat} for the numeric entries under proc_root, bounded by MAX_PIDS."""
    table = {}
    try:
        names = os.listdir(proc_root)
    except OSError:
        return table
    for name in names:
        if not name.isdigit():
            continue
        if len(table) >= MAX_PIDS:
            break
        entry = read_stat(proc_root, int(name))
        if entry is not None:
            table[entry["pid"]] = entry
    return table


def descendants(table, root_pid):
    """root_pid and every process reachable from it by parent links in the table."""
    children = {}
    for entry in table.values():
        children.setdefault(entry["ppid"], []).append(entry["pid"])
    found, queue = [], [root_pid]
    while queue and len(found) < MAX_PIDS:
        pid = queue.pop()
        if pid in found or pid not in table:
            continue
        found.append(pid)
        queue.extend(children.get(pid, ()))
    return found


class Ledger:
    """Processes the adapter's own child ever owned: (pid, start ticks) pairs plus their groups."""

    def __init__(self, own_group=None):
        self.own_group = os.getpgrp() if own_group is None else own_group
        self.members = {}
        self.groups = set()

    def update(self, table, root_pid):
        for pid in descendants(table, root_pid):
            self.members[(pid, table[pid]["start"])] = table[pid]["pgrp"]
            if table[pid]["pgrp"] != self.own_group:
                self.groups.add(table[pid]["pgrp"])
        for entry in table.values():
            if entry["pgrp"] in self.groups and entry["pgrp"] != self.own_group:
                self.members[(entry["pid"], entry["start"])] = entry["pgrp"]
        return self.pids(table)

    def pids(self, table):
        return sorted(pid for (pid, start) in self.members if pid in table and table[pid]["start"] == start)

    def survivors(self, table):
        """Owned processes still alive: same pid and start ticks, or any process in an owned group."""
        alive = {}
        for (pid, start) in self.members:
            entry = table.get(pid)
            if entry and entry["start"] == start and entry["state"] not in DEAD_STATES:
                alive[pid] = entry["pgrp"]
        for entry in table.values():
            if entry["pgrp"] in self.groups and entry["state"] not in DEAD_STATES:
                alive.setdefault(entry["pid"], entry["pgrp"])
        return [{"pid": pid, "pgrp": group} for pid, group in sorted(alive.items())]


def socket_inodes(proc_root, pids):
    """{inode: pid} of the sockets the given processes hold open."""
    inodes = {}
    for pid in pids:
        directory = Path(proc_root) / str(pid) / "fd"
        try:
            names = os.listdir(directory)[:MAX_FDS]
        except OSError:
            continue
        for name in names:
            try:
                target = os.readlink(directory / name)
            except OSError:
                continue
            match = SOCKET_LINK.match(target)
            if match:
                inodes.setdefault(int(match.group(1)), pid)
    return inodes


def _address(text):
    try:
        raw = bytes.fromhex(text)
    except ValueError:
        return None
    if len(raw) == 4:
        return str(ipaddress.IPv4Address(raw[::-1]))
    if len(raw) == 16:
        value = ipaddress.IPv6Address(b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4)))
        return str(value.ipv4_mapped) if value.ipv4_mapped is not None else str(value)
    return None


def parse_net(text, proto):
    """Local endpoints from one /proc/net table: [{proto, ip, port, inode}]."""
    rows = []
    for line in text.splitlines()[1:MAX_NET_ROWS]:
        fields = line.split()
        if len(fields) < 10 or ":" not in fields[1]:
            continue
        address, _, port = fields[1].partition(":")
        ip = _address(address)
        try:
            rows.append({"proto": proto, "ip": ip, "port": int(port, 16), "inode": int(fields[9])})
        except ValueError:
            continue
    return [row for row in rows if row["ip"] is not None]


def net_rows(net_root="/proc/net"):
    rows = []
    for name, proto in NET_TABLES:
        try:
            with open(Path(net_root) / name, "rb") as stream:
                text = stream.read(MAX_NET_BYTES).decode("ascii", errors="replace")
        except OSError:
            continue
        rows.extend(parse_net(text, proto))
    return rows


def observe_sockets(proc_root, net_root, pids):
    """Every local endpoint, each marked with the owning pid when one of the given pids holds it."""
    inodes = socket_inodes(proc_root, pids)
    return [dict(row, owner=inodes.get(row["inode"])) for row in net_rows(net_root)]


def claim_socket(rows, ip, port):
    """Does an owned process hold exactly ip:port? A wildcard bind never satisfies the claim."""
    if ip in WILDCARDS:
        return {"claimed": False, "reason": "wildcard_not_a_claim", "ip": ip, "port": port}
    exact = [row for row in rows if row["port"] == port and row["ip"] == ip]
    owned = [row for row in exact if row["owner"] is not None]
    if owned:
        return {"claimed": True, "reason": "owned_exact_bind", "ip": ip, "port": port,
                "proto": owned[0]["proto"]}
    if exact:
        return {"claimed": False, "reason": "port_held_by_other_process", "ip": ip, "port": port}
    if any(row["port"] == port and row["ip"] in WILDCARDS for row in rows):
        return {"claimed": False, "reason": "wildcard_not_a_claim", "ip": ip, "port": port}
    return {"claimed": False, "reason": "not_bound", "ip": ip, "port": port}


def wildcard_owned(rows):
    """Wildcard endpoints held by owned processes, reported as exposure and never as a claim."""
    return sorted({(row["proto"], row["port"]) for row in rows
                   if row["ip"] in WILDCARDS and row["owner"] is not None})


def port_free(rows, ip, port):
    return not any(row["port"] == port and (row["ip"] == ip or row["ip"] in WILDCARDS) for row in rows)


# --- Confinement and guards -------------------------------------------------------------------

def require_owned(root, path):
    """Return the normalised path when it lies inside root with no symlink component, else refuse."""
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    if path != root and root not in path.parents:
        raise ValueError("path outside owned staging")
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        try:
            if stat.S_ISLNK(os.lstat(current).st_mode):
                raise ValueError("symlink inside owned staging")
        except FileNotFoundError:
            break
    return path


def write_owned(root, relative, data):
    """Create one new file under root; an existing file is never overwritten."""
    target = require_owned(root, Path(root) / relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return target


def snapshot_guard(files=None, directories=None):
    """Identity of files that must not change: {label: [size, mtime_ns, sha256]} or None if absent.

    files and directories map a label to a path. A directory contributes name, size and mtime of
    every entry, bounded by MAX_GUARD_ENTRIES (exceeding the bound is refused, not truncated).
    """
    record = {}
    for label, path in sorted((files or {}).items()):
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            record[label] = None
            continue
        record[label] = [info.st_size, info.st_mtime_ns, sha256_file(path)]
    budget = MAX_GUARD_ENTRIES
    for label, root in sorted((directories or {}).items()):
        if not os.path.isdir(root):
            record[label] = None
            continue
        for directory, names, filenames in os.walk(root, followlinks=False):
            names.sort()
            for filename in sorted(filenames):
                budget -= 1
                if budget < 0:
                    raise ValueError("guard directory exceeds the entry bound")
                path = Path(directory) / filename
                info = os.lstat(path)
                record[label + "/" + path.relative_to(root).as_posix()] = [info.st_size, info.st_mtime_ns, None]
    return record


def diff_guard(before, after):
    """Labels whose identity differs between two snapshots, including added and removed entries."""
    return sorted(label for label in set(before) | set(after) if before.get(label) != after.get(label))
