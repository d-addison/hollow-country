"""provenance.v2 contract and sealed candidate verification (stdlib only).

A parent supplies reviewed inputs/toolchain and origin to build_provenance;
worker JSON is never a policy source. verify_provenance(from_worker=True) is
mandatory at a subprocess boundary. A JSON 'writer' claim cannot authenticate a
process. The CLI audits a parent-owned, immutable directory; this module is not
an OS sandbox or a signature system.

Schema: {schema: 'provenance.v2', asset: str, inputs: [component, ...],
 toolchain: [tool, ...], attestations: [attestation, ...], shippable: bool,
 origin: str, licence_gate: {verdict, shippable, reasons}, waived: [str, ...]}.
Component: {source: URL/id, path: bundle-relative str, sha256: hex,
 licence_id: SPDX id, licence_path: bundle-relative str, licence_sha256: hex,
 attribution: str}.
Tool: component plus {name: str, version: str, external_process: bool,
 shipped: bool}. Optional component fields: name, acquisition ('archive' for
Poly Haven). Licence hashes pin reviewed licence text, content hashes pin bytes;
neither alone proves rights. Attestation: {value: bool, note: repo-relative .md,
 note_sha256: hex}. True counts only against committed HEAD bytes AND disk bytes.

Seal format: candidate.sha256 contains the SHA-256 of manifest.json; manifest
is {"files": {"bundle/relative/path": "sha256", ...}}. Every regular payload
file, including provenance.json, must be listed; manifest and seal cannot list
themselves. There are no mutable/excluded payload directories in this port.
"""
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

SCHEMA = 'provenance.v2'
AUTHORITATIVE = frozenset(('shippable', 'origin', 'licence_gate', 'waived'))
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_FILES = 4096
ROOT = Path(__file__).resolve().parents[2]


class Refusal(ValueError):
    """A stable reason code, never untrusted paths or content."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '\x00' in value or value != PurePosixPath(value).as_posix()
            or PurePosixPath(value).is_absolute()
            or any(p in ('.', '..') for p in value.split('/'))):
        raise Refusal('path.invalid')
    return PurePosixPath(value)


def read_regular(root, name):
    """Reject links, escapes, special files and oversized inputs.

    Caller must keep the candidate tree immutable while verification/packing
    runs. No-follow final opens complement checks on each parent directory.
    """
    rel = relative_path(name)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise Refusal('path.root_invalid')
    current = root
    for part in rel.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise Refusal('path.parent_invalid')
    path = root / rel
    if path.is_symlink():
        raise Refusal('path.link')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                 | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Refusal('path.not_regular')
        data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise Refusal('file.limit')
        return data


def load_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refusal('json.duplicate_key')
            result[key] = value
        return result

    def invalid_constant(value):
        raise Refusal('json.nonfinite')

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Refusal('json.invalid') from exc


def reject_worker_authority(value):
    if isinstance(value, dict):
        if AUTHORITATIVE.intersection(value):
            raise Refusal('provenance.worker_authority')
        for child in value.values():
            reject_worker_authority(child)
    elif isinstance(value, list):
        for child in value:
            reject_worker_authority(child)


def verify_provenance(document, *, from_worker=False):
    if from_worker:
        reject_worker_authority(document)
    fields = {'schema', 'asset', 'inputs', 'toolchain', 'attestations'}
    if not from_worker:
        fields |= AUTHORITATIVE
    if not isinstance(document, dict) or set(document) != fields:
        raise Refusal('provenance.fields')
    if document['schema'] != SCHEMA:
        raise Refusal('provenance.schema')
    if not isinstance(document['asset'], str) or not document['asset'].strip():
        raise Refusal('provenance.asset')
    for field in ('inputs', 'toolchain', 'attestations'):
        if not isinstance(document[field], list):
            raise Refusal('provenance.list')
    if not document['inputs']:
        raise Refusal('provenance.inputs_missing')
    if not from_worker:
        if (type(document['shippable']) is not bool
                or not isinstance(document['origin'], str) or not document['origin'].strip()
                or not isinstance(document['licence_gate'], dict)
                or not isinstance(document['waived'], list)
                or any(not isinstance(v, str) or not v.strip() for v in document['waived'])):
            raise Refusal('provenance.authority_invalid')
    return document


def verified_attestation(record, repo_root=ROOT):
    if not isinstance(record, dict) or record.get('value') is not True:
        return False
    try:
        note = str(relative_path(record.get('note')))
        expected = record.get('note_sha256')
        if not note.endswith('.md') or not isinstance(expected, str) or not SHA256.fullmatch(expected):
            return False
        data = read_regular(repo_root, note)
        committed = subprocess.run(['git', 'show', 'HEAD:' + note], cwd=repo_root,
                                   capture_output=True, timeout=10, check=False)
        return (committed.returncode == 0 and digest(committed.stdout) == expected
                and digest(data) == expected)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def verify_candidate(root):
    root = Path(root)
    seal = read_regular(root, 'candidate.sha256').decode('ascii').strip()
    manifest_bytes = read_regular(root, 'manifest.json')
    if not SHA256.fullmatch(seal) or digest(manifest_bytes) != seal:
        raise Refusal('candidate.seal_mismatch')
    manifest = load_json(manifest_bytes)
    if not isinstance(manifest, dict) or set(manifest) != {'files'}:
        raise Refusal('candidate.manifest_invalid')
    files = manifest['files']
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise Refusal('candidate.files_invalid')
    reserved = {'manifest.json', 'candidate.sha256'}
    if reserved.intersection(files) or 'provenance.json' not in files:
        raise Refusal('candidate.files_invalid')
    for name, expected in files.items():
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            raise Refusal('candidate.digest_invalid')
        if digest(read_regular(root, name)) != expected:
            raise Refusal('candidate.digest_mismatch')
    actual = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise Refusal('candidate.link')
        for name in names:
            actual.add((Path(directory) / name).relative_to(root).as_posix())
            if len(actual) > MAX_FILES + len(reserved):
                raise Refusal('candidate.file_limit')
    if actual != set(files) | reserved:
        raise Refusal('candidate.inventory_mismatch')
    return files


def build_provenance(*, asset, inputs, toolchain, origin, worker_output=None,
                     waived=(), attestations=(), root, repo_root=ROOT):
    """Trusted parent API; all keyword arguments except worker_output are trusted.

    Worker output is checked for policy injection and otherwise ignored. Parent
    metadata must come from reviewed manifests, never copied out of worker JSON.
    Build before sealing, then audit the sealed directory before packing.
    """
    from tools.assets.licence_gate import evaluate

    reject_worker_authority(worker_output)
    document = copy.deepcopy(dict(schema=SCHEMA, asset=asset, inputs=inputs,
                                  toolchain=toolchain, attestations=list(attestations),
                                  origin=origin, waived=list(waived), shippable=False,
                                  licence_gate={}))
    verify_provenance(document)
    result = evaluate(document, root=root, repo_root=repo_root, check_authority=False)
    document['licence_gate'] = result
    document['shippable'] = result['shippable']
    return document
