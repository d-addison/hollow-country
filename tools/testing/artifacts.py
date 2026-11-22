"""Fresh evidence roots and immutable role/hash snapshots (spec 002 AV-T006).

An ArtifactStore owns one new evidence root per run. Every driver run is an attempt in
attempts/<task>/attempt-NNN/; a retry opens a new attempt directory and never overwrites an
earlier one. Each stored file is written once (exclusive create, read-only), carries a role,
its sha256 and size, and is listed in store.json with the producing driver, actor, client
count and method pin. The manifest is rewritten atomically after each finished attempt and
hash-chains the attempts of a task, so a removed or replaced failed retry is detectable.

Credential or private-key material is redacted from text artifacts and refused in any other
artifact; neither the match nor its position is ever printed. The checks live in
tools.validate.evidence (validate_store / validate_strict); this module only writes.
An autotest store never evaluates acceptance and never proves multiplayer.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path
import re

from tools.testing import discovery
from tools.validate import evidence

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")
EVIDENCE_LABEL = "offline-framework"


class CredentialRefused(ValueError):
    """A non-text artifact holds credential material. The message names rule kinds only."""


def _source(function):
    try:
        return inspect.getsource(function)
    except (OSError, TypeError):
        code = getattr(function, "__code__", None)
        return code.co_code.hex() if code is not None else repr(function)


def method_pin(driver):
    """sha256 pin of everything that defines how a driver runs and judges; changing it makes old pins stale."""
    cells = [cell.cell_contents for cell in (getattr(driver.judge, "__closure__", None) or ())
             if isinstance(cell.cell_contents, (str, int))]
    material = [driver.id, driver.kind, driver.layer, list(driver.needs), list(driver.inputs),
                driver.timeout, driver.memory, getattr(driver.judge, "__qualname__", ""),
                _source(driver.judge), _source(driver.argv), cells]
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def text_pin(text):
    """Pin for a pseudo-producer (for example a deferred task) defined by a fixed text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pins_for(registry, extra=None):
    pins = {driver_id: method_pin(driver) for driver_id, driver in registry.items()}
    pins.update(extra or {})
    return pins


def producer_for(driver):
    """(actor, presented_as) for a registry driver. Nothing the framework runs is a real client."""
    if driver.kind == "offline":
        return "offline", "offline_framework"
    return ("diagnostic" if "diag" in driver.id else "server"), "zero_client_native"


def task_slug(task_id):
    slug = SLUG_UNSAFE.sub("_", task_id)
    if not slug or not slug[0].isalnum():
        slug = "t" + slug
    return slug[:160]


def _atomic_write(path, data):
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)
    os.replace(temporary, path)
    if hasattr(os, "O_DIRECTORY"):
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


class Attempt:
    """One driver run. Files are write-once; finish() seals the attempt into the manifest."""

    def __init__(self, store, task, slug, number, producer):
        self.store = store
        self.task, self.slug, self.number = task, slug, number
        self.producer = producer
        self.dir = f"attempts/{slug}/attempt-{number:03d}"
        self.artifacts = []
        self.finished = False
        (store.root / self.dir).mkdir(parents=True, exist_ok=False)

    def add(self, name, data, role):
        """Snapshot bytes or text. Text is redacted; credential material in other bytes is refused."""
        if self.finished:
            raise ValueError("attempt is already sealed")
        if role not in evidence.STORE_ROLES:
            raise ValueError("unknown artifact role")
        if not isinstance(name, str) or not FILE_NAME.fullmatch(name) or name.lower().endswith(".biprivatekey") \
                or any(item["path"].endswith("/" + name) for item in self.artifacts):
            raise ValueError("invalid or duplicate artifact name")
        raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        redactions = []
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            kinds = evidence.credential_kinds(raw)
            if kinds:
                raise CredentialRefused("artifact refused: credential material (" + ",".join(kinds) + ")") from None
        else:
            text, redactions = evidence.redact_credentials(discovery.redact(text))
            raw = text.encode("utf-8")
        raw = raw[:MAX_ARTIFACT_BYTES]
        if not raw:
            raise ValueError("an empty artifact is not evidence")
        path = self.store.root / self.dir / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        relative = f"{self.dir}/{name}"
        self.artifacts.append({"path": relative, "role": role, "sha256": hashlib.sha256(raw).hexdigest(),
                               "size": len(raw), "redactions": redactions})
        return relative

    def path(self, name):
        return self.store.root / self.dir / name

    def finish(self, outcome, reason):
        """Seal the attempt: chain it to the task's previous attempt and rewrite the manifest atomically."""
        if self.finished:
            raise ValueError("attempt is already sealed")
        actor, presented, clients, pin, driver = self.producer
        previous = self.store.last_digest.get(self.slug)
        entry = {"task": self.task, "task_slug": self.slug, "attempt": self.number, "dir": self.dir,
                 "driver": driver, "actor": actor, "presented_as": presented, "client_count": clients,
                 "method_pin": pin, "outcome": outcome, "reason": reason, "previous": previous,
                 "artifacts": list(self.artifacts)}
        entry["entry_sha256"] = evidence.entry_digest(entry)
        self.finished = True
        self.store.entries.append(entry)
        self.store.last_digest[self.slug] = entry["entry_sha256"]
        self.store.open.discard(self.slug)
        self.store.flush()
        return entry


class ArtifactStore:
    def __init__(self, root, run_id):
        root = Path(root)
        if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
            raise ValueError("evidence root must be a new or empty directory")
        (root / "attempts").mkdir(parents=True, exist_ok=True)
        self.root = root
        self.run_id = run_id
        self.entries = []
        self.last_digest = {}
        self.slugs = {}
        self.open = set()
        self._sha256 = None
        self.flush()

    def begin(self, task_id, driver_id, *, actor, presented_as, client_count, pin):
        """Open the next attempt for a task. Earlier attempts, failed or not, stay untouched."""
        if actor not in evidence.ACTORS or presented_as not in evidence.PRESENTATIONS or type(client_count) is not int:
            raise ValueError("invalid producer")
        slug = task_slug(task_id)
        if self.slugs.setdefault(slug, task_id) != task_id:
            raise ValueError("two task IDs map to one attempt directory")
        if slug in self.open:
            raise ValueError("task already has an open attempt")
        number = 1 + sum(1 for entry in self.entries if entry["task_slug"] == slug)
        attempt = Attempt(self, task_id, slug, number, (actor, presented_as, client_count, pin, driver_id))
        self.open.add(slug)
        return attempt

    def manifest(self):
        return {"schema_version": evidence.STORE_SCHEMA, "run_id": self.run_id, "evidence_label": EVIDENCE_LABEL,
                "acceptance": "not_evaluated", "attempts": self.entries}

    def flush(self):
        data = json.dumps(self.manifest(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        _atomic_write(self.root / evidence.STORE_MANIFEST, data.encode("utf-8"))
        self._sha256 = hashlib.sha256(data.encode("utf-8")).hexdigest()

    def manifest_sha256(self):
        """Hash of the manifest as last written by this store; a later edit on disk no longer matches it."""
        return self._sha256

    def validate(self, pins, expected_tasks=None):
        """Strict check of the sealed store; an open attempt leaves unlisted files and fails it."""
        return evidence.validate_store(self.root, pins=pins, expected_tasks=expected_tasks,
                                       manifest_sha256=self.manifest_sha256())
