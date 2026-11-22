"""Synthetic stand-ins for /proc, /proc/net and a launcher process, for the native adapter tests.

Nothing here observes DayZ, Wine or a real socket; every value is built by the test.
"""
import os
from pathlib import Path
import shutil

TICKS_FIELDS = 19   # stat fields between the state letter and the start ticks


def stat_line(pid, ppid, pgrp, start, state="S"):
    filler = " ".join(["0"] * (TICKS_FIELDS - 3))
    return "%d (synthetic) %s %d %d %s %d 0" % (pid, state, ppid, pgrp, filler, start)


def hex_address(ip):
    return "".join("%02X" % int(part) for part in reversed(ip.split(".")))


def net_line(index, ip, port, inode):
    return "%4d: %s:%04X 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 %d 2 0 0 0 0" % (
        index, hex_address(ip), port, inode)


class FakeHost:
    """A tmp directory laid out like /proc and /proc/net."""

    HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnmt   uid  timeout inode\n"

    def __init__(self, root):
        self.proc = Path(root) / "proc"
        self.net = Path(root) / "net"
        self.proc.mkdir(parents=True)
        self.net.mkdir(parents=True)
        self.rows = {"udp": [], "udp6": [], "tcp": [], "tcp6": []}
        self.flush()

    def process(self, pid, ppid, pgrp, start=100, state="S", sockets=()):
        directory = self.proc / str(pid)
        (directory / "fd").mkdir(parents=True, exist_ok=True)
        (directory / "stat").write_text(stat_line(pid, ppid, pgrp, start, state))
        for number, inode in enumerate(sockets):
            link = directory / "fd" / str(number + 3)
            if not os.path.lexists(link):
                os.symlink("socket:[%d]" % inode, link)

    def kill(self, pid):
        shutil.rmtree(self.proc / str(pid), ignore_errors=True)

    def bind(self, ip, port, inode, table="udp"):
        self.rows[table].append(net_line(len(self.rows[table]), ip, port, inode))
        self.flush()

    def unbind_all(self):
        for table in self.rows:
            self.rows[table] = []
        self.flush()

    def flush(self):
        for table, rows in self.rows.items():
            (self.net / table).write_text(self.HEADER + "".join(row + "\n" for row in rows))


class FakeProcess:
    """popen stand-in: running for a number of polls, then gone (or surviving) with a return code."""

    def __init__(self, host, pid, polls=1, returncode=0, survive=False, on_start=None, on_exit=None):
        self.host, self.pid, self.polls, self.returncode, self.survive = host, pid, polls, returncode, survive
        self.on_exit, self.count = on_exit, 0
        if on_start:
            on_start()

    def poll(self):
        if self.count < self.polls:
            self.count += 1
            return None
        if not self.survive:
            self.host.kill(self.pid)
            self.host.unbind_all()
        if self.on_exit:
            self.on_exit()
            self.on_exit = None
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode
