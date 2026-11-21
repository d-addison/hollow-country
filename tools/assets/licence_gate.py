"""Fail-closed asset admission. Run with a sealed candidate's provenance.json.

Only a parent-owned provenance file is accepted by this CLI. Call the worker
boundary verifier before consuming subprocess output. Results never establish
legal ownership; pinned evidence and reviewed policy remain prerequisites.
"""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from tools.assets.provenance import (
    ROOT, Refusal, SHA256, digest, load_json, read_regular, verified_attestation,
    verify_candidate, verify_provenance,
)

POLICY_PATH = ROOT / 'config/asset-licence-policy.json'
VERDICTS = ('blocked', 'internal_only', 'shippable')


def verdict(status, reasons=()):
    return {'verdict': status, 'shippable': status == 'shippable',
            'reasons': sorted(set(reasons))}


def load_policy():
    policy = load_json(POLICY_PATH.read_bytes())
    if (not isinstance(policy, dict) or policy.get('schema') != 'asset-licence-policy.v1'
            or policy.get('verdict_order') != list(VERDICTS)):
        raise Refusal('policy.invalid')
    for key in ('source_licences', 'attribution_required', 'external_process_only'):
        if (not isinstance(policy.get(key), list) or not policy[key]
                or any(not isinstance(v, str) or not v for v in policy[key])):
            raise Refusal('policy.invalid')
    if (not isinstance(policy.get('blocked_components'), list)
            or not policy['blocked_components']):
        raise Refusal('policy.invalid')
    for row in policy['blocked_components']:
        if (not isinstance(row, dict) or not isinstance(row.get('names'), list)
                or not row['names'] or any(not isinstance(v, str) or not v for v in row['names'])
                or not isinstance(row.get('reason'), str) or not row['reason']):
            raise Refusal('policy.invalid')
    ph = policy.get('poly_haven')
    if (not isinstance(ph, dict) or ph.get('licence_id') != 'CC0-1.0'
            or not isinstance(ph.get('preview_path'), str) or not ph['preview_path']):
        raise Refusal('policy.invalid')
    for key in ('archive_hosts', 'archive_suffixes'):
        if (not isinstance(ph.get(key), list) or not ph[key]
                or any(not isinstance(v, str) or not v for v in ph[key])):
            raise Refusal('policy.invalid')
    return policy


def _component(record, *, tool, root, policy):
    required = {'source', 'path', 'sha256', 'licence_id', 'licence_sha256',
                'licence_path', 'attribution'}
    optional = {'name', 'acquisition'}
    if tool:
        required |= {'name', 'version', 'external_process', 'shipped'}
    if not isinstance(record, dict) or not required <= record.keys() or record.keys() - required - optional:
        raise Refusal('component.fields')
    for key in required - {'external_process', 'shipped', 'attribution'}:
        if not isinstance(record[key], str) or not record[key].strip():
            raise Refusal('component.missing')
    if not isinstance(record['attribution'], str):
        raise Refusal('component.attribution_invalid')
    for key in ('sha256', 'licence_sha256'):
        if not SHA256.fullmatch(record[key]):
            raise Refusal('component.pin_invalid')
    for path_key, hash_key in (('path', 'sha256'), ('licence_path', 'licence_sha256')):
        payload = read_regular(root, record[path_key])
        if digest(payload) != record[hash_key]:
            raise Refusal('component.digest_mismatch')
        if path_key == 'licence_path':
            try:
                text = payload.decode('utf-8-sig')
            except UnicodeError as exc:
                raise Refusal('component.licence_unparseable') from exc
            if not text.strip() or '\x00' in text:
                raise Refusal('component.licence_unparseable')
    if tool and (type(record['external_process']) is not bool or type(record['shipped']) is not bool):
        raise Refusal('tool.boundary_invalid')
    name = record.get('name', '')
    if not isinstance(name, str):
        raise Refusal('component.name_invalid')
    if 'acquisition' in record and (not isinstance(record['acquisition'], str)
                                    or not record['acquisition'].strip()):
        raise Refusal('component.acquisition_invalid')
    source = unquote(record['source']).lower()
    tokens = set(re.split(r'[^a-z0-9-]+', source + '/' + name.lower()))
    for blocked in policy['blocked_components']:
        if any(alias in tokens or alias in source.split('?')[0].rstrip('/')
               for alias in blocked['names']):
            raise Refusal('component.explicitly_blocked')
    url = urlsplit(source)
    ph = policy['poly_haven']
    if 'polyhaven' in source or 'poly haven' in name.lower():
        if (ph['preview_path'] in url.path or url.scheme != 'https'
                or url.hostname not in ph['archive_hosts'] or url.username or url.password
                or not any(url.path.endswith(ext) for ext in ph['archive_suffixes'])
                or record.get('acquisition') != 'archive'
                or record['licence_id'] != ph['licence_id']):
            raise Refusal('component.polyhaven_not_pinned_archive')
    licence = record['licence_id']
    if licence in policy['source_licences']:
        if licence in policy['attribution_required'] and not record['attribution'].strip():
            raise Refusal('component.attribution_missing')
        return 'shippable'
    if (tool and licence in policy['external_process_only']
            and record['external_process'] and not record['shipped']):
        return 'internal_only'
    raise Refusal('component.licence_not_allowed')


def evaluate(document, *, root, repo_root=ROOT, check_authority=True):
    """Recompute from pinned bytes; worker claims/waivers never upgrade a verdict.

    check_authority=False is exclusively for the parent's construction step.
    It does not skip schema, digest, licence, attestation or waiver checks.
    """
    try:
        verify_provenance(document)
        policy = load_policy()
        status = 'shippable'
        reasons = []
        for field in ('inputs', 'toolchain'):
            for record in document[field]:
                component_status = _component(record, tool=field == 'toolchain', root=root, policy=policy)
                status = VERDICTS[min(VERDICTS.index(status), VERDICTS.index(component_status))]
                if component_status == 'internal_only':
                    reasons.append('tool.external_copyleft_internal_only')
        if document['waived']:
            status = 'blocked'
            reasons.append('provenance.waived')
        if document['origin'] == 'ops:raw_bpy':
            status = VERDICTS[min(VERDICTS.index(status), VERDICTS.index('internal_only'))]
            reasons.append('provenance.raw_worker_internal_only')
        for record in document['attestations']:
            if isinstance(record, dict) and record.get('value') is False:
                continue
            if not verified_attestation(record, repo_root):
                raise Refusal('attestation.unverified')
        result = verdict(status, reasons)
        if check_authority and (document['licence_gate'] != result
                                or document['shippable'] is not result['shippable']):
            raise Refusal('provenance.authority_mismatch')
        return result
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        # Errors expose stable codes only; paths and subprocess output stay private.
        return verdict('blocked', [str(exc) if isinstance(exc, Refusal) else 'provenance.invalid'])


def audit(path):
    try:
        path = Path(path)
        if path.name != 'provenance.json':
            raise Refusal('provenance.filename')
        files = verify_candidate(path.parent)
        raw = read_regular(path.parent, path.name)
        if digest(raw) != files['provenance.json']:
            raise Refusal('candidate.provenance_changed')
        return evaluate(load_json(raw), root=path.parent)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        return verdict('blocked', [str(exc) if isinstance(exc, Refusal) else 'candidate.invalid'])


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    result = audit(args[0]) if len(args) == 1 else verdict('blocked', ['cli.expected_provenance'])
    print(json.dumps(result, sort_keys=True))
    return 0 if result['shippable'] else 1


if __name__ == '__main__':
    sys.exit(main())
