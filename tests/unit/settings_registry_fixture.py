"""Explicit synthetic registry/map port; all admission/scaling decisions are authored."""
import re
import math
from pathlib import Path
from types import SimpleNamespace as N
from tests.unit.test_event_runtime import translate

SETTINGS = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/3_Game/HCSettings.c'


def install_registry(env):
    source = SETTINGS.read_text().replace('HCOperatorSettingRule', 'HCEventSettingRule')
    rows = {}
    for key, kind, default, low, high, owner in re.findall(
            r'HCAdd\("([^"]+)", "([^"]+)", ([\d.]+), ([\d.]+), ([\d.]+), "([^"]+)"\);', source):
        rows[key] = N(ValueKind=kind, DefaultValue=float(default), Minimum=float(low),
                      Maximum=float(high), Owner=owner)
    # Map construction is a synthetic native container boundary, not a policy.
    api = N(HCFind=lambda key: rows.get(key))
    env['HCOperatorSettingsRegistry'] = api
    for name in ('HCValid', 'HCDefault', 'HCMinimum', 'HCMaximum'):
        setattr(api, name, translate(source, name, env, 'HCOperatorSettingsRegistry'))
    return api


def attach_density(settings, env=None):
    env = {} if env is None else env
    env.setdefault('Math', N(Floor=math.floor))
    env.setdefault('Print', lambda line: None)
    env.setdefault('str', str)
    install_registry(env)
    source = SETTINGS.read_text()
    # Only DTO fields and methods, never string literals, are member-bound.
    source = source.replace('return SearchDensityScale;', 'return this.SearchDensityScale;')
    source = source.replace('if (SearchDensityScale == 0)', 'if (this.SearchDensityScale == 0)')
    for name in ('HCEffectiveSearchDensity', 'HCSearchCap'):
        fn = translate(source, name, env, 'HCSettings', True)
        setattr(settings, name, lambda *args, fn=fn: fn(settings, *args))
    return settings
