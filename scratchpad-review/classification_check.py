"""Summarize config facts from a local capture; no runtime or provenance acceptance."""
import json
from pathlib import Path
from tools.audit.flashlight_matrix import build_matrix, classify_matrix

root = Path('/home/david/.cache/hollow-country/experiments/compile-035-four-root-audit/profiles/HollowCountry/ItemCompatibilityAudit/native-item-audit-all')
rows = [row for chunk in sorted(root.glob('*.json'))
        for row in json.loads(chunk.read_bytes()).get('Rows', [])]
classification = classify_matrix(build_matrix(rows, {'review_only': True}))
counts = classification['denominators']
print('local capture, not re-admitted: hosts={hosts} slot_host={slot_host} no_slot_host={no_slot_host} excluded={excluded}'.format(**counts))
print('helmet slot hosts:', ', '.join(h['name'] for h in classification['hosts']
                                     if 'helmetFlashlight' in h['native_light_slots']))
print('scope-2 hosts excluded for model_empty:', sum(h['scope'] == 2 and 'model_empty' in h['exclusion_reasons']
                                                   for h in classification['hosts']))
print('scope-2 hosts excluded for scope_below_2:', sum(h['scope'] == 2 and 'scope_below_2' in h['exclusion_reasons']
                                                     for h in classification['hosts']))
