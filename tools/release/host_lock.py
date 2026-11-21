"""Nonblocking, crash-released native host lease, with descendant reentrancy."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re

ENV = 'HC_HOST_LOCK'


class LockRefused(ValueError):
    """Another native tool owns the host."""


def _ancestor(pid):
    current = os.getpid()
    while current > 1:
        if current == pid:
            return True
        try:
            current = int(Path(f'/proc/{current}/stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return False


def _holder(value):
    # Only tool labels may leave this module; never arbitrary metadata text.
    return value if isinstance(value, str) and re.fullmatch(r'[a-z_]{1,40}', value) else 'native_tool'


@contextmanager
def host_lock(holder, path=None):
    """Hold across the entire run; children inherit HC_HOST_LOCK automatically.

    Reentry requires matching metadata AND a live ancestor, so stale environment
    values never bypass an unrelated holder. Do not unlink the lock inode.
    """
    path = Path(path) if path is not None else Path('~/.cache/hollow-country/host.lock').expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+', encoding='utf-8') as stream:
        stream.seek(0)
        try:
            record = json.load(stream)
        except (ValueError, TypeError):
            record = {}
        inherited = os.environ.get(ENV)
        if (isinstance(record, dict) and inherited == json.dumps(record, sort_keys=True)
                and isinstance(record.get('pid'), int) and _ancestor(record['pid'])):
            yield
            return
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Reread after refusal, in case publication raced our initial read.
            stream.seek(0)
            try:
                record = json.load(stream)
            except ValueError:
                record = {}
            label = _holder(record.get('holder')) if isinstance(record, dict) else 'native_tool'
            raise LockRefused('native host busy: holder=' + label) from None
        previous = os.environ.get(ENV)
        record = dict(holder=_holder(holder), pid=os.getpid(), started=datetime.now(timezone.utc).isoformat())
        try:
            stream.seek(0)
            stream.truncate()
            json.dump(record, stream, sort_keys=True)
            stream.flush()
            os.environ[ENV] = json.dumps(record, sort_keys=True)
            yield
        finally:
            if previous is None:
                os.environ.pop(ENV, None)
            else:
                os.environ[ENV] = previous
            fcntl.flock(stream, fcntl.LOCK_UN)
