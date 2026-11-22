"""Validate version-1 evidence manifests using only the Python standard library.

Run ``python3 -m tools.validate.evidence PATH``. PATH is one UTF-8 JSON object;
its directory is the evidence root. All artifact paths are canonical POSIX
relative paths beneath that root (store the manifest at the repository root
when using repository-relative paths). No command, URL, or artifact is executed.

Schema (unknown keys and duplicate JSON keys are errors):
  version: 1; capability_id: CAP-01..CAP-99;
  status: documented | hypothesis | observed | prototyped | accepted | blocked.
  Optional sources: list of HTTP(S) URLs; pending_fields: list of field names.
  documented/hypothesis may omit optional fields or use null/empty pending values.
  Runtime statuses (observed/prototyped/accepted) require:
    game_build, observation, method: concrete non-placeholder strings;
    layer: T2..T5; client_count: integer >= 1;
    test_ids: unique PREFIX-NNN strings;
    artifacts: [{path: relative path, sha256: 64 hexadecimal characters}];
    observations: [{test_id: exact declared ID, text: concrete observation,
                    artifacts: [paths from the verified artifact table]}].
  Exactly one observation per test ID is required. Each observation binds at
  least one nonempty file to its method and result. A hash does not establish
  that its bytes were produced by DayZ, or that a reported result is true.
  blocked requires artifacts and obstacle: {description, steps: [concrete steps]}.
  requires_two_clients: optional bool; true adds a two-client acceptance gate.
  false cannot exempt CAP-18/CAP-21 or known multiplayer/audio test IDs.
  impacts: optional subset of [network, audio, visibility]; each forces two
  clients for accepted. T4 always requires two clients for runtime claims.
  accepted requires T3 or higher; T2 supports observed/prototyped only.
  accepted also requires performance: {report, baseline, candidate}, three
  distinct verified artifact paths. report must itself contain UTF-8 JSON:
    {version: 1, method: concrete string,
     baseline: {artifact: exact baseline path, sample_count: positive integer},
     candidate: {artifact: exact candidate path, sample_count: positive integer},
     measurements: [{metric: concrete name, unit: concrete unit,
                     baseline: finite number, candidate: finite number}]}.
  Report JSON is parsed from the exact bytes hashed, without reopening its path.
  Artifact identity uses device/inode as well as paths, rejecting hard-link reuse.
  Symlinks in artifact paths are rejected. POSIX reads anchor every component
  with directory descriptors and no-follow opens. On platforms lacking these
  APIs, before/after containment checks require an immutable evidence directory;
  they are not a sandbox against a concurrent hostile filesystem writer.
  Report references bind comparison measurements to actual hashed run files;
  arbitrary prose is insufficient. Budgets remain provisional: this validator
  does not approve thresholds, certify production gates, or promote capabilities.

Integration contract: validate(path) returns the same object printed as one
JSON line by the CLI. Keys are exactly report_version (1), path (absolute),
capability_id/status (strings or null), valid (bool), errors (list). Each error
has exactly code, field, message. Fields use dotted names and [index], with $
for the document root. Errors are deterministic in code/field/message order.
Codes: input_io, invalid_json, schema, required, duplicate, pending_runtime,
runtime_layer, runtime_clients, unsafe_path, artifact_io, empty_artifact,
hash_mismatch, artifact_reference, observation_tests, two_clients,
performance_reference. CLI exits 0 for valid, 1 for invalid (including IO/JSON
errors), 2 for command-line usage errors. Only usage errors go to stderr.

Strict store rules (spec 002 AV-T006, additive; validate(path) is unchanged):
validate_strict(path, store_root=..., pins=...) runs validate(path) and then
validate_store(), which checks the evidence store manifest written by
tools.testing.artifacts: every artifact present, nonempty, hash-exact, unaliased
(one role per hash, no hard links) and free of credential material; every method
pin current; every task's attempts numbered 1..n with a hash chain so a failed
retry cannot be overwritten; and actor rules (a bot, diagnostic or server actor,
or a zero-client native run, is never a real client and never accepted runtime
evidence; raw zero-client reports are a separate role). Strict codes: store_manifest,
artifact_missing, aliased_artifact, stale_pin, unknown_producer, retry_overwritten,
unlisted_artifact, credential_material, actor_mismatch, zero_client_accepted,
raw_zero_client_in_runtime, multiplayer_claim, task_missing, attempt_record.
Messages never contain credential bytes, only the rule kind and a path.

All unit-test artifacts are explicitly synthetic T0 inputs, never runtime proof.
"""

import argparse
from contextlib import contextmanager
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit


_STATUSES = {"documented", "hypothesis", "observed", "prototyped", "accepted", "blocked"}
_RUNTIME = {"observed", "prototyped", "accepted"}
_FIELDS = {
    "version", "capability_id", "status", "game_build", "sources", "test_ids",
    "artifacts", "observation", "observations", "method", "layer", "client_count",
    "requires_two_clients", "impacts", "performance", "obstacle", "pending_fields",
}
_PLACEHOLDERS = {"tbd", "todo", "pending", "unknown", "n/a", "none", "not run", "not tested"}
_TEST_ID = re.compile(r"[A-Z][A-Z0-9]*-[0-9]{3}")
# Explicit multiplayer tests from the handoff test catalog. Prefixes AUD/NET
# independently require two-client acceptance even when impacts is omitted.
_MULTIPLAYER_TESTS = {"INT-006", "INT-007", "CRF-004", "AI-012", "HOR-006"}


STORE_MANIFEST = "store.json"
STORE_SCHEMA = 1
CREDENTIAL_SCAN_BYTES = 8 * 1024 * 1024
STORE_ROLES = ("driver_log", "evidence_record", "zero_client_report", "runtime_client_log", "server_log")
# Raw zero-client reports are kept apart: a runtime record may never cite one.
RUNTIME_FORBIDDEN_ROLES = ("zero_client_report",)
ACTORS = ("offline", "server", "diagnostic", "bot", "real_client")
PRESENTATIONS = ("offline_framework", "zero_client_native", "real_client")
STORE_OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOTRUN")
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}")
_HEX64 = re.compile(r"[a-f0-9]{64}")
_PRIVATE_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S)
_KEY_FILE = re.compile(r"[^\s\"'<>|]*\.biprivatekey\b", re.I)
_PASSWORD = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*(?:password|passwd|secret|token|api[_-]?key))(\s*[=:]\s*)"
    r"(?!\[REDACTED)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)")


def credential_kinds(data):
    """Names of the credential rules that match; never the matched material."""
    text = data.decode("latin-1") if isinstance(data, (bytes, bytearray)) else str(data)
    kinds = []
    for kind, pattern in (("private_key", _PRIVATE_BLOCK), ("biprivatekey", _KEY_FILE), ("password", _PASSWORD)):
        if pattern.search(text):
            kinds.append(kind)
    return kinds


def redact_credentials(text):
    """Return (redacted text, sorted rule kinds hit). The material is replaced, never reported."""
    kinds = set()

    def mark(kind, replacement):
        def swap(match):
            kinds.add(kind)
            return replacement(match)
        return swap

    text = _PRIVATE_BLOCK.sub(mark("private_key", lambda m: "[REDACTED:private_key]"), text)
    text = _KEY_FILE.sub(mark("biprivatekey", lambda m: "[REDACTED:biprivatekey]"), text)
    text = _PASSWORD.sub(mark("password", lambda m: m.group(1) + m.group(2) + "[REDACTED:password]"), text)
    return text, sorted(kinds)


class _UnsafeArtifact(ValueError):
    pass


@contextmanager
def _regular_stream(path):
    """Open without blocking on a substituted FIFO; validate the opened handle."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("Not a regular file")
        stream = os.fdopen(fd, "rb")
        fd = None
        with stream:
            yield stream
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def _artifact_stream(root, name):
    """Anchor POSIX traversal so replacing a checked parent cannot redirect IO."""
    components = name.split("/")
    if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"):
        directory = None
        fd = None
        try:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
            directory = os.open(root, flags)
            for component in components[:-1]:
                child = os.open(component, flags, dir_fd=directory)
                os.close(directory)
                directory = child
            fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=directory)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("Not a regular file")
            stream = os.fdopen(fd, "rb")
            fd = None
            with stream:
                yield stream
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise _UnsafeArtifact("Artifact path contains a symlink or invalid directory.") from exc
            raise
        finally:
            if fd is not None:
                os.close(fd)
            if directory is not None:
                os.close(directory)
    else:
        # Portable fallback: never trust lexical paths alone. A read-only source
        # directory is required here when the OS lacks descriptor-relative IO.
        path = root.joinpath(*components)
        cursor = root
        for component in components:
            cursor = cursor / component
            if cursor.is_symlink():
                raise _UnsafeArtifact("Symlink artifact paths are not accepted.")
        if not path.resolve().is_relative_to(root):
            raise _UnsafeArtifact("Artifact resolves outside the evidence root.")
        with _regular_stream(path) as stream:
            yield stream
            if not path.resolve().is_relative_to(root) or not os.path.samestat(os.fstat(stream.fileno()), path.stat()):
                raise _UnsafeArtifact("Artifact path changed while reading.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number: " + value)


def _json_bytes(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def _load_json(path):
    with _regular_stream(path) as stream:
        return _json_bytes(stream.read())


class _Validator:
    def __init__(self, root):
        self.root = root
        self.errors = []
        self.verified = {}
        self.performance_name = None
        self.performance_bytes = None

    def error(self, code, field, message):
        self.errors.append({"code": code, "field": field, "message": message})

    def obj(self, value, field, allowed, required=()):
        if not isinstance(value, dict):
            self.error("schema", field, "Expected an object.")
            return False
        for key in sorted(value.keys() - allowed):
            self.error("schema", key if field == "$" else field + "." + key, "Unknown field.")
        for key in required:
            if key not in value:
                self.error("required", key if field == "$" else field + "." + key, "Required field is missing.")
        return True

    def text(self, value, field, concrete=True):
        if not isinstance(value, str) or (concrete and
                (not value.strip() or value.strip().casefold() in _PLACEHOLDERS)):
            self.error("schema", field, "Expected concrete non-placeholder text." if concrete
                       else "Expected a string.")
            return False
        return True

    def array(self, value, field, nonempty=False):
        if not isinstance(value, list) or (nonempty and not value):
            self.error("schema", field, "Expected a nonempty array." if nonempty else "Expected an array.")
            return False
        return True

    def strings(self, value, field, nonempty=False, pattern=None, choices=None):
        if not self.array(value, field, nonempty):
            return []
        result = []
        for i, item in enumerate(value):
            item_field = f"{field}[{i}]"
            if not self.text(item, item_field):
                continue
            if pattern is not None and pattern.fullmatch(item) is None:
                self.error("schema", item_field, "Invalid identifier format.")
                continue
            if choices is not None and item not in choices:
                self.error("schema", item_field, "Unknown value.")
                continue
            if item in result:
                self.error("duplicate", item_field, "Duplicate value.")
            result.append(item)
        return result

    def artifact_table(self, value, required):
        if not self.array(value, "artifacts", required):
            return
        seen = set()
        targets = set()
        for i, item in enumerate(value):
            field = f"artifacts[{i}]"
            if not self.obj(item, field, {"path", "sha256"}, ("path", "sha256")):
                continue
            name = item.get("path")
            digest = item.get("sha256")
            valid_hash = isinstance(digest, str) and re.fullmatch(r"[a-fA-F0-9]{64}", digest)
            if not valid_hash:
                self.error("schema", field + ".sha256", "Expected a SHA-256 hex digest.")
            if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                    or any(ord(char) < 32 for char in name)):
                self.error("unsafe_path", field + ".path", "Expected a canonical relative path beneath the evidence root.")
                continue
            if name in seen:
                self.error("duplicate", field + ".path", "Duplicate artifact path.")
                continue
            seen.add(name)
            try:
                path = (self.root / name).resolve()
                if not path.is_relative_to(self.root):
                    self.error("unsafe_path", field + ".path", "Artifact resolves outside the evidence root.")
                    continue
                computed = hashlib.sha256()
                size = 0
                report_blocks = [] if name == self.performance_name else None
                with _artifact_stream(self.root, name) as stream:
                    info = os.fstat(stream.fileno())
                    identity = (info.st_dev, info.st_ino) if info.st_ino else path
                    if identity in targets:
                        self.error("duplicate", field + ".path", "Artifact aliases another artifact file (including a hard link).")
                        continue
                    targets.add(identity)
                    # Read a finite snapshot rather than chasing an appended log.
                    remaining = info.st_size
                    while remaining:
                        block = stream.read(min(1024 * 1024, remaining))
                        if not block:
                            break
                        size += len(block)
                        remaining -= len(block)
                        computed.update(block)
                        if report_blocks is not None:
                            report_blocks.append(block)
                    final = os.fstat(stream.fileno())
                    if size != info.st_size or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (final.st_size, final.st_mtime_ns, final.st_ctime_ns):
                        raise OSError("Artifact changed while hashing")
            except _UnsafeArtifact:
                self.error("unsafe_path", field + ".path", "Artifact path contains a symlink or changed its target.")
                continue
            except (OSError, ValueError, RuntimeError):
                self.error("artifact_io", field + ".path", "Artifact is not a readable regular file.")
                continue
            if size == 0:
                self.error("empty_artifact", field + ".path", "Artifact must contain evidence bytes.")
            elif valid_hash:
                if computed.hexdigest() != digest.lower():
                    self.error("hash_mismatch", field + ".sha256", "Artifact SHA-256 does not match.")
                else:
                    self.verified[name] = path
                    if report_blocks is not None:
                        self.performance_bytes = b"".join(report_blocks)

    def references(self, value, field, required=True):
        names = self.strings(value, field, nonempty=required)
        for i, name in enumerate(names):
            if name not in self.verified:
                self.error("artifact_reference", f"{field}[{i}]", "Reference must name a verified artifact path exactly.")
        return names

    def observations(self, value, ids, runtime):
        if not self.array(value, "observations", runtime):
            return
        observed_ids = []
        for i, entry in enumerate(value):
            field = f"observations[{i}]"
            if not self.obj(entry, field, {"test_id", "text", "artifacts"}, ("test_id", "text", "artifacts")):
                continue
            test_id = entry.get("test_id")
            if self.text(test_id, field + ".test_id"):
                observed_ids.append(test_id)
            self.text(entry.get("text"), field + ".text", concrete=runtime)
            self.references(entry.get("artifacts"), field + ".artifacts", required=runtime)
        if runtime and (sorted(observed_ids) != sorted(ids) or len(set(observed_ids)) != len(observed_ids)):
            self.error("observation_tests", "observations", "Require exactly one observation for each declared test ID; no extras.")

    def performance(self, value):
        if not self.obj(value, "performance", {"report", "baseline", "candidate"},
                        ("report", "baseline", "candidate")):
            return
        refs = []
        for key in ("report", "baseline", "candidate"):
            name = value.get(key)
            if not self.text(name, "performance." + key):
                continue
            refs.append(name)
            if name not in self.verified:
                self.error("artifact_reference", "performance." + key, "Reference must name a verified artifact path exactly.")
        if len(refs) != 3 or len(set(refs)) != 3:
            self.error("performance_reference", "performance", "Report, baseline and candidate must be distinct verified artifacts.")
        report_path = self.verified.get(value.get("report")) if isinstance(value.get("report"), str) else None
        if report_path is None:
            return
        try:
            report = _json_bytes(self.performance_bytes)
        except (OSError, UnicodeError, ValueError, RecursionError):
            self.error("invalid_json", "performance.report", "Performance report must be strict UTF-8 JSON.")
            return
        field = "performance.report"
        if not self.obj(report, field, {"version", "method", "baseline", "candidate", "measurements"},
                        ("version", "method", "baseline", "candidate", "measurements")):
            return
        if type(report.get("version")) is not int or report["version"] != 1:
            self.error("schema", field + ".version", "Expected integer version 1.")
        self.text(report.get("method"), field + ".method")
        for key in ("baseline", "candidate"):
            run = report.get(key)
            run_field = field + "." + key
            if not self.obj(run, run_field, {"artifact", "sample_count"}, ("artifact", "sample_count")):
                continue
            if not isinstance(run.get("artifact"), str) or run["artifact"] != value.get(key):
                self.error("performance_reference", run_field + ".artifact", "Run reference must exactly match the manifest comparison.")
            if type(run.get("sample_count")) is not int or run["sample_count"] < 1:
                self.error("schema", run_field + ".sample_count", "Expected a positive integer sample count.")
        measurements = report.get("measurements")
        if not self.array(measurements, field + ".measurements", nonempty=True):
            return
        seen = set()
        for i, measurement in enumerate(measurements):
            metric_field = f"{field}.measurements[{i}]"
            if not self.obj(measurement, metric_field, {"metric", "unit", "baseline", "candidate"},
                            ("metric", "unit", "baseline", "candidate")):
                continue
            if self.text(measurement.get("metric"), metric_field + ".metric"):
                metric = measurement["metric"]
                if metric in seen:
                    self.error("duplicate", metric_field + ".metric", "Duplicate measured metric.")
                seen.add(metric)
            self.text(measurement.get("unit"), metric_field + ".unit")
            for key in ("baseline", "candidate"):
                number = measurement.get(key)
                if type(number) not in (int, float) or (isinstance(number, float) and not math.isfinite(number)):
                    self.error("schema", metric_field + "." + key, "Expected a finite measured number.")

    def record(self, data):
        if not self.obj(data, "$", _FIELDS, ("version", "capability_id", "status")):
            return
        if type(data.get("version")) is not int or data["version"] != 1:
            self.error("schema", "version", "Expected integer version 1.")
        capability = data.get("capability_id")
        if not isinstance(capability, str) or not re.fullmatch(r"CAP-(?:0[1-9]|[1-9][0-9])", capability):
            self.error("schema", "capability_id", "Expected CAP-01..CAP-99.")
        status = data.get("status")
        if not isinstance(status, str) or status not in _STATUSES:
            self.error("schema", "status", "Unknown evidence status.")
            status = None
        runtime = status in _RUNTIME
        performance = data.get("performance")
        if isinstance(performance, dict) and isinstance(performance.get("report"), str):
            self.performance_name = performance["report"]
        pending = status in {"documented", "hypothesis"}
        required = ["game_build", "test_ids", "artifacts", "observation", "observations", "method", "layer", "client_count"] if runtime else []
        if status == "blocked":
            required.extend(("obstacle", "artifacts"))
        if status == "accepted":
            required.append("performance")
        for key in required:
            if key not in data:
                self.error("required", key, "Required field is missing.")

        def present(key):
            return key in data and not (pending and data[key] is None)

        for key in ("game_build", "observation", "method"):
            if present(key):
                self.text(data[key], key, concrete=not pending)
        if present("layer"):
            layer = data["layer"]
            if not isinstance(layer, str) or layer not in {f"T{i}" for i in range(6)}:
                self.error("schema", "layer", "Expected T0..T5.")
            elif runtime and (layer in {"T0", "T1"} or (status == "accepted" and layer == "T2")):
                self.error("runtime_layer", "layer", "Runtime claims require T2 or higher; accepted requires normal server evidence at T3 or higher.")
        if present("client_count"):
            clients = data["client_count"]
            if type(clients) is not int or clients < 0:
                self.error("schema", "client_count", "Expected a nonnegative integer.")
            elif runtime and clients < 1:
                self.error("runtime_clients", "client_count", "Runtime claims require at least one client.")
        ids = self.strings(data["test_ids"], "test_ids", runtime, pattern=_TEST_ID) if present("test_ids") else []
        if present("pending_fields"):
            fields = self.strings(data["pending_fields"], "pending_fields", choices=_FIELDS - {"pending_fields"})
            if fields and not pending:
                self.error("pending_runtime", "pending_fields", "Only documented/hypothesis records may have pending fields.")
        if present("artifacts"):
            self.artifact_table(data["artifacts"], runtime or status == "blocked")
        if present("observations"):
            self.observations(data["observations"], ids, runtime)
        if present("sources") and self.array(data["sources"], "sources"):
            for i, source in enumerate(data["sources"]):
                field = f"sources[{i}]"
                if self.text(source, field):
                    try:
                        url = urlsplit(source)
                        valid = url.scheme in {"http", "https"} and bool(url.hostname) and not any(c.isspace() for c in source)
                    except ValueError:
                        valid = False
                    if not valid:
                        self.error("schema", field, "Expected an HTTP(S) URL with a host.")
        two_clients = capability in ("CAP-18", "CAP-21") or any(
            test_id.startswith(("AUD-", "NET-")) or test_id in _MULTIPLAYER_TESTS for test_id in ids)
        if present("requires_two_clients"):
            if type(data["requires_two_clients"]) is not bool:
                self.error("schema", "requires_two_clients", "Expected a boolean.")
            else:
                two_clients = two_clients or data["requires_two_clients"]
        if present("impacts"):
            impacts = self.strings(data["impacts"], "impacts", choices={"network", "audio", "visibility"})
            two_clients = two_clients or bool(impacts)
        if (status == "accepted" and two_clients) or (runtime and data.get("layer") == "T4"):
            clients = data.get("client_count")
            if type(clients) is not int or clients < 2:
                self.error("two_clients", "client_count", "Accepted network/audio/visibility evidence and runtime T4 claims require at least two clients.")
        if present("obstacle"):
            obstacle = data["obstacle"]
            if self.obj(obstacle, "obstacle", {"description", "steps"}, ("description", "steps")):
                self.text(obstacle.get("description"), "obstacle.description")
                self.strings(obstacle.get("steps"), "obstacle.steps", nonempty=True)
        if present("performance"):
            self.performance(data["performance"])


def validate(path):
    """Return the deterministic v1 report; invalid input is data, not an exception."""
    path = Path(path).absolute()
    checker = _Validator(path.parent)
    data = None
    try:
        path = path.resolve()
        checker.root = path.parent
        data = _load_json(path)
    except (OSError, RuntimeError):
        checker.error("input_io", "$", "Manifest is not a readable file.")
    except (UnicodeError, ValueError, RecursionError):
        checker.error("invalid_json", "$", "Manifest must be strict UTF-8 JSON without duplicate keys or non-finite constants.")
    else:
        checker.record(data)
    return {
        "report_version": 1, "path": str(path),
        "capability_id": data.get("capability_id") if isinstance(data, dict) and isinstance(data.get("capability_id"), str) else None,
        "status": data.get("status") if isinstance(data, dict) and isinstance(data.get("status"), str) else None,
        "valid": not checker.errors,
        "errors": sorted(checker.errors, key=lambda error: (error["code"], error["field"], error["message"])),
    }


def entry_digest(entry):
    """sha256 over the canonical entry without its own digest; chains attempts per task."""
    body = {key: value for key, value in entry.items() if key != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


class _StoreChecker:
    def __init__(self, root, pins):
        self.root = root
        self.pins = pins
        self.errors = []
        self.tasks = {}

    def error(self, code, field, message):
        self.errors.append({"code": code, "field": field, "message": message})

    def read(self, name):
        """(sha256, size, identity, head bytes for the credential scan) of one stored file."""
        digest = hashlib.sha256()
        size = 0
        head = b""
        with _artifact_stream(self.root, name) as stream:
            info = os.fstat(stream.fileno())
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                digest.update(block)
                if len(head) < CREDENTIAL_SCAN_BYTES:
                    head += block
        return digest.hexdigest(), size, (info.st_dev, info.st_ino), head[:CREDENTIAL_SCAN_BYTES]

    def attempt(self, index, entry, seen_hash, seen_identity, listed):
        field = f"attempts[{index}]"
        keys = {"task", "task_slug", "attempt", "dir", "driver", "actor", "presented_as", "client_count",
                "method_pin", "outcome", "reason", "previous", "artifacts", "entry_sha256"}
        if not isinstance(entry, dict) or set(entry) != keys:
            self.error("store_manifest", field, "Attempt entry fields do not match the store schema.")
            return
        task, slug, number = entry["task"], entry["task_slug"], entry["attempt"]
        if not isinstance(task, str) or not task or not isinstance(slug, str) or not _SLUG.fullmatch(slug) \
                or slug in {".", ".."} or type(number) is not int or number < 1:
            self.error("store_manifest", field, "Task, slug or attempt number is invalid.")
            return
        if self.tasks.setdefault(slug, task) != task:
            self.error("retry_overwritten", field + ".task", "Two task IDs share one attempt directory.")
        if entry["dir"] != f"attempts/{slug}/attempt-{number:03d}":
            self.error("store_manifest", field + ".dir", "Attempt directory does not follow the store layout.")
        if entry["entry_sha256"] != entry_digest(entry):
            self.error("store_manifest", field + ".entry_sha256", "Attempt entry digest does not match its content.")
        driver, pin = entry["driver"], entry["method_pin"]
        if entry["outcome"] not in STORE_OUTCOMES or not isinstance(entry["reason"], str) or not entry["reason"]:
            self.error("store_manifest", field + ".outcome", "Attempt is not finished with an outcome and reason.")
        if not isinstance(pin, str) or not _HEX64.fullmatch(pin):
            self.error("store_manifest", field + ".method_pin", "Expected a SHA-256 method pin.")
        elif self.pins is None or driver not in self.pins:
            self.error("unknown_producer", field + ".driver", "Producer driver is not in the trusted registry.")
        elif self.pins[driver] != pin:
            self.error("stale_pin", field + ".method_pin", "Method pin differs from the current driver method.")
        actor, presented, clients = entry["actor"], entry["presented_as"], entry["client_count"]
        if actor not in ACTORS or presented not in PRESENTATIONS or type(clients) is not int or clients < 0:
            self.error("store_manifest", field, "Actor, presentation or client count is invalid.")
            return
        real = presented == "real_client"
        if real and (actor != "real_client" or clients < 1):
            self.error("actor_mismatch", field + ".actor",
                       "A bot, diagnostic, server or zero-client actor cannot be presented as a real client.")
        if not real and (clients != 0 or actor == "real_client"):
            self.error("actor_mismatch", field + ".presented_as", "Client count or actor does not match the presentation.")
        artifacts = entry["artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            self.error("empty_artifact", field + ".artifacts", "Attempt has no artifacts.")
            return
        roles = set()
        for position, item in enumerate(artifacts):
            afield = f"{field}.artifacts[{position}]"
            if not isinstance(item, dict) or set(item) != {"path", "role", "sha256", "size", "redactions"}:
                self.error("store_manifest", afield, "Artifact entry fields do not match the store schema.")
                continue
            name, role, digest, size = item["path"], item["role"], item["sha256"], item["size"]
            if (not isinstance(name, str) or any(part in {"", ".", ".."} for part in name.split("/"))
                    or "\\" in name or not name.startswith(entry["dir"] + "/")
                    or any(ord(char) < 32 for char in name)):
                self.error("unsafe_path", afield + ".path", "Artifact is not a canonical path inside its attempt.")
                continue
            if role not in STORE_ROLES or not isinstance(digest, str) or not _HEX64.fullmatch(digest) or type(size) is not int:
                self.error("store_manifest", afield, "Artifact role, hash or size is invalid.")
                continue
            if name in listed:
                self.error("duplicate", afield + ".path", "Artifact path is listed twice.")
                continue
            listed[name] = (index, role, digest)
            roles.add(role)
            try:
                actual, length, identity, head = self.read(name)
            except _UnsafeArtifact:
                self.error("unsafe_path", afield + ".path", "Artifact path contains a symlink or changed its target.")
                continue
            except (OSError, ValueError, RuntimeError):
                self.error("artifact_missing", afield + ".path", "Artifact is missing or not a readable regular file.")
                continue
            if length == 0:
                self.error("empty_artifact", afield + ".path", "Artifact must contain evidence bytes.")
            elif actual != digest or length != size:
                self.error("hash_mismatch", afield + ".sha256", "Artifact bytes differ from the manifest snapshot.")
            if actual in seen_hash and seen_hash[actual] != role:
                self.error("aliased_artifact", afield + ".sha256", "The same bytes appear under two roles.")
            seen_hash.setdefault(actual, role)
            if identity in seen_identity and identity[1]:
                self.error("aliased_artifact", afield + ".path", "Artifact aliases another stored file (hard link).")
            seen_identity.add(identity)
            if credential_kinds(head):
                self.error("credential_material", afield + ".path", "Artifact holds credential or private-key material.")
        if real and "runtime_client_log" not in roles:
            self.error("actor_mismatch", field + ".artifacts", "A real-client attempt needs a runtime_client_log artifact.")
        if not real and "runtime_client_log" in roles:
            self.error("actor_mismatch", field + ".artifacts", "Only a real-client attempt may hold a runtime_client_log artifact.")

    def record(self, index, entry, listed):
        """Strict rules for the attempt's evidence-v1 record on top of validate()."""
        field = f"attempts[{index}]"
        names = [item["path"] for item in entry["artifacts"]
                 if isinstance(item, dict) and item.get("role") == "evidence_record"]
        if len(names) != 1:
            self.error("attempt_record", field, "Each attempt needs exactly one evidence_record artifact.")
            return
        base = validate(self.root / names[0])
        for error in base["errors"]:
            self.error(error["code"], field + ".record." + error["field"], error["message"])
        try:
            data = _load_json(self.root / names[0])
        except (OSError, ValueError, RuntimeError, RecursionError):
            return
        if not isinstance(data, dict):
            return
        prefix = names[0].rsplit("/", 1)[0] + "/"
        runtime = data.get("status") in _RUNTIME
        cited = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []
        for position, item in enumerate(cited):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            hit = listed.get(prefix + item["path"])
            if hit is None or hit[0] != index or str(item.get("sha256", "")).lower() != hit[2]:
                self.error("artifact_missing", f"{field}.record.artifacts[{position}]",
                           "Record artifact is not a snapshot of this attempt.")
            elif runtime and hit[1] in RUNTIME_FORBIDDEN_ROLES:
                self.error("raw_zero_client_in_runtime", f"{field}.record.artifacts[{position}]",
                           "A raw zero-client report cannot back a runtime claim.")
        if entry["presented_as"] != "real_client" or entry["actor"] != "real_client":
            if data.get("status") == "accepted":
                self.error("zero_client_accepted", field + ".record.status",
                           "A zero-client, bot, diagnostic or server run can never become accepted runtime evidence.")
            elif runtime:
                self.error("actor_mismatch", field + ".record.status",
                           "Runtime evidence needs a real-client attempt.")
        recorded = data.get("client_count")
        if runtime and type(recorded) is int and recorded > entry["client_count"]:
            self.error("two_clients", field + ".record.client_count",
                       "The record claims more clients than the attempt observed.")
        if entry["client_count"] < 2:
            text = " ".join(str(data.get(key, "")) for key in ("method", "observation"))
            text = re.sub(r"(?i)\b(?:never|not|no|non)[ -]multiplayer", "", text)
            if re.search(r"(?i)multiplayer", text):
                self.error("multiplayer_claim", field + ".record", "Autotest evidence never proves multiplayer.")


def validate_store(root, *, pins, expected_tasks=None, manifest_sha256=None):
    """Strict check of one evidence store; returns the same report shape as validate()."""
    root = Path(root).absolute()
    checker = _StoreChecker(root, pins)
    manifest_path = root / STORE_MANIFEST
    data = None
    try:
        with _regular_stream(manifest_path) as stream:
            raw = stream.read()
        if manifest_sha256 is not None and hashlib.sha256(raw).hexdigest() != manifest_sha256:
            checker.error("hash_mismatch", "$", "Store manifest differs from the hash recorded for the run.")
        data = _json_bytes(raw)
    except (OSError, RuntimeError):
        checker.error("store_manifest", "$", "Store manifest is missing or not a readable file.")
    except (UnicodeError, ValueError, RecursionError):
        checker.error("store_manifest", "$", "Store manifest must be strict UTF-8 JSON.")
    if isinstance(data, dict):
        _check_manifest(checker, data, expected_tasks)
    elif data is not None:
        checker.error("store_manifest", "$", "Store manifest must be an object.")
    return {
        "report_version": 1, "path": str(manifest_path), "capability_id": None, "status": None,
        "valid": not checker.errors,
        "errors": sorted(checker.errors, key=lambda error: (error["code"], error["field"], error["message"])),
    }


def _check_manifest(checker, data, expected_tasks):
    keys = {"schema_version", "run_id", "evidence_label", "acceptance", "attempts"}
    if set(data) != keys or type(data["schema_version"]) is not int or data["schema_version"] != STORE_SCHEMA \
            or not isinstance(data["run_id"], str) or not isinstance(data["attempts"], list):
        checker.error("store_manifest", "$", "Store manifest fields do not match the store schema.")
        return
    if data["acceptance"] != "not_evaluated" or "multiplayer" in str(data["evidence_label"]):
        checker.error("multiplayer_claim", "$", "A store never evaluates acceptance or labels evidence multiplayer.")
    listed, seen_hash, seen_identity, previous = {}, {}, set(), {}
    counts = {}
    for index, entry in enumerate(data["attempts"]):
        checker.attempt(index, entry, seen_hash, seen_identity, listed)
        if not isinstance(entry, dict) or not isinstance(entry.get("task_slug"), str):
            continue
        slug = entry["task_slug"]
        counts[slug] = counts.get(slug, 0) + 1
        if entry.get("attempt") != counts[slug] or entry.get("previous") != previous.get(slug):
            checker.error("retry_overwritten", f"attempts[{index}]",
                          "Attempts for a task must be numbered 1..n and hash-chained; none may be replaced or removed.")
        previous[slug] = entry.get("entry_sha256")
    for index, entry in enumerate(data["attempts"]):
        if isinstance(entry, dict) and isinstance(entry.get("artifacts"), list) and entry.get("dir"):
            if any(isinstance(item, dict) and item.get("role") == "evidence_record" for item in entry["artifacts"]):
                if set(entry) >= {"actor", "presented_as", "client_count", "artifacts"}:
                    checker.record(index, entry, listed)
            else:
                checker.error("attempt_record", f"attempts[{index}]", "Each attempt needs exactly one evidence_record artifact.")
    present = set(checker.tasks.values())
    for task in sorted(expected_tasks or ()):
        if task not in present:
            checker.error("task_missing", "attempts", "Expected task has no attempt in the store: " + task)
    try:
        for current, directories, files in os.walk(checker.root, followlinks=False):
            base = Path(current)
            for name in directories:
                if (base / name).is_symlink():
                    checker.error("unsafe_path", str((base / name).relative_to(checker.root)), "Symlink inside the evidence store.")
            for name in files:
                relative = (base / name).relative_to(checker.root).as_posix()
                if relative != STORE_MANIFEST and relative not in listed:
                    checker.error("unlisted_artifact", relative, "File is not part of the manifest snapshot.")
    except OSError:
        checker.error("store_manifest", "$", "Evidence store directory cannot be listed.")


def validate_strict(path, *, store_root, pins, manifest_sha256=None, expected_tasks=None):
    """validate(path) plus the strict store rules; the original report shape is preserved."""
    report = validate(path)
    errors = list(report["errors"])
    store = validate_store(store_root, pins=pins, expected_tasks=expected_tasks, manifest_sha256=manifest_sha256)
    errors.extend({"code": e["code"], "field": "store." + e["field"], "message": e["message"]} for e in store["errors"])
    try:
        relative = Path(report["path"]).relative_to(Path(store_root).resolve()).as_posix()
    except ValueError:
        relative = None
        errors.append({"code": "store_manifest", "field": "$", "message": "Record is outside the evidence store."})
    if relative is not None and not any(
            relative == item.get("path") and item.get("role") == "evidence_record"
            for entry in _manifest_attempts(store_root) for item in entry.get("artifacts", []) if isinstance(item, dict)):
        errors.append({"code": "artifact_missing", "field": "$", "message": "Record is not a manifest evidence_record."})
    report = dict(report, valid=not errors,
                  errors=sorted(errors, key=lambda error: (error["code"], error["field"], error["message"])))
    return report


def _manifest_attempts(store_root):
    try:
        data = _load_json(Path(store_root) / STORE_MANIFEST)
        return [e for e in data["attempts"] if isinstance(e, dict)]
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, RecursionError):
        return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="Version-1 evidence manifest JSON")
    args = parser.parse_args(argv)
    report = validate(args.path)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
