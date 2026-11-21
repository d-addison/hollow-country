"""Validated owner targets; never substitute defaults for missing release policy."""
import json
import math
from pathlib import Path

DEFAULT_TARGETS = Path(__file__).resolve().parents[2] / 'config/acceptance-targets.json'
_FIELDS = {
    'release_gate_doc': str,
    'soak_minutes': (int, float),
    'max_script_errors': int,
    'max_vme_server': int,
    'perf_r2_max_ms': (int, float),
    'client_max_vme': int,
    'client_max_missing_textures': int,
    'activity_requires_active_for_default_on': bool,
    'upgrade_from_previous_release_required': bool,
    'boot_check_doc': str,
    'settle_minutes': (int, float),
    'target_players_min': int,
    'target_players_max': int,
    'budgets_provisional': bool,
    'benchmark_doc': str,
}


class TargetsError(ValueError):
    """Safe diagnostic: never includes a local path or untrusted JSON values."""


def load_targets(path=None):
    """Load strict flat keys, exact types (bool is not int), and sane ranges."""
    try:
        data = json.loads(Path(DEFAULT_TARGETS if path is None else path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise TargetsError('acceptance targets file missing, unreadable or invalid JSON') from None
    if type(data) is not dict:
        raise TargetsError('acceptance targets must be an object')
    missing = _FIELDS.keys() - data.keys()
    if missing:
        raise TargetsError('acceptance targets missing keys: ' + ', '.join(sorted(missing)))
    if data.keys() - _FIELDS.keys():
        raise TargetsError('acceptance targets contain unknown keys')
    for key, kind in _FIELDS.items():
        types = kind if isinstance(kind, tuple) else (kind,)
        value = data[key]
        if type(value) not in types:
            raise TargetsError('acceptance targets invalid type: ' + key)
        if type(value) in (int, float) and (value < 0 or (type(value) is float and not math.isfinite(value))):
            raise TargetsError('acceptance targets require finite nonnegative value: ' + key)
        if kind is str and not value.strip():
            raise TargetsError('acceptance targets require documentation: ' + key)
    if data['soak_minutes'] <= 0 or data['perf_r2_max_ms'] <= 0:
        raise TargetsError('acceptance targets soak_minutes and perf_r2_max_ms must be positive')
    if not 0 < data['target_players_min'] <= data['target_players_max']:
        raise TargetsError('acceptance targets invalid player range')
    return data
