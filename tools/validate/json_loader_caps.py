"""Fail when a shipped JSON file approaches the size cap of the native reader that loads it.

Every cap is read from the native source that enforces it, so a changed cap moves the gate.
A shipped file fails at LIMIT_PERCENT of its cap, leaving growth headroom before the loader
would refuse the file (a refusal turns a feature off silently on a server that cannot be
wiped). Rules, all derived from the source tree:

* addon profile defaults and the settings template are copied or read through the one-shot
  bounded reader (HCProfileDefaults / HCWorldStore): the smaller of their MAX_BYTES applies;
* a mission file named by a native source (its mission-relative path, or an ancestor
  directory literal) is read through HCWorldStore: same one-shot cap;
* HCReadBounded("$mission:...", <literal>, ...) declares a per-file cap, which wins;
* STREAMED_LOADERS names loaders that read in windows and enforce their own running byte
  cap in source; the cap is parsed from that source and the gate fails if the pattern is gone;
* a mission file that no native source names is not a runtime loader input (installer or
  generator data) and has no loader cap to compare with.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LIMIT_PERCENT = 85
WORLD_STORE = 'mods/HollowCountry/scripts/4_World/World/HCWorldStore.c'
PROFILE_DEFAULTS = 'mods/HollowCountry/scripts/4_World/Core/HCProfileDefaults.c'
MISSION = 'mission/hollow-country/'
SETTINGS_TEMPLATE = 'config/hollow-country-settings.json'
# path -> (native source, regex whose group 1 is the loader's running byte cap)
STREAMED_LOADERS = {
    MISSION + 'ai/road-graph.compact.json': (
        'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICaravanAdapter.c',
        r'm_CompactBytes\s*>\s*(\d+)'),
}
BOUNDED_READ = re.compile(r'HCReadBounded\(\s*"\$mission:hollow-country/([^"]+\.json)"\s*,\s*(\d+)\s*,')


def within_budget(size, cap):
    """True while size stays at or below LIMIT_PERCENT of cap (integer arithmetic)."""
    return size * 100 <= cap * LIMIT_PERCENT


def class_constant(text, class_name, constant):
    """Value of `static const int <constant> = N;` declared inside class <class_name>."""
    start = re.search(r'\bclass\s+' + re.escape(class_name) + r'\b', text)
    if not start:
        raise ValueError('class not found: ' + class_name)
    match = re.search(r'static\s+const\s+int\s+' + re.escape(constant) + r'\s*=\s*(\d+)\s*;', text[start.end():])
    if not match:
        raise ValueError('constant not found: %s.%s' % (class_name, constant))
    return int(match.group(1))


def one_shot_cap(root=ROOT):
    """Smallest byte cap of the one-shot readers shipped JSON passes through."""
    root = Path(root)
    store = class_constant((root / WORLD_STORE).read_text(), 'HCWorldStore', 'MAX_BYTES')
    defaults = class_constant((root / PROFILE_DEFAULTS).read_text(), 'HCProfileDefaults', 'MAX_BYTES')
    return min(store, defaults)


def native_texts(root):
    return {path.relative_to(root).as_posix(): path.read_text(errors='replace')
            for path in sorted((Path(root) / 'mods').glob('**/*.c'))}


def shipped_mission_files():
    from tools.package import pbo
    return sorted(name for name in pbo.MISSION_FILES if name.endswith('.json'))


def is_native_input(relative, texts):
    """Whether some native source names the mission-relative path or one of its directories."""
    needles = [relative]
    parts = relative.split('/')[:-1]
    needles.extend('hollow-country/' + '/'.join(parts[:count]) + '/' for count in range(1, len(parts) + 1))
    return any(needle in text for text in texts.values() for needle in needles)


def streamed_cap(path, texts):
    source, pattern = STREAMED_LOADERS[path]
    match = re.search(pattern, texts.get(source, ''))
    if not match:
        raise ValueError('streamed loader cap not found for %s in %s' % (path, source))
    return int(match.group(1))


def loader_caps(root=ROOT, mission_files=None):
    """Map every shipped JSON that a native reader loads to (cap, loader description)."""
    root = Path(root)
    texts = native_texts(root)
    default = one_shot_cap(root)
    declared = {MISSION + name: int(cap) for text in texts.values() for name, cap in BOUNDED_READ.findall(text)}
    caps = {}
    for name in (shipped_mission_files() if mission_files is None else sorted(mission_files)):
        path = MISSION + name
        if not (root / path).is_file():
            continue
        if path in STREAMED_LOADERS:
            caps[path] = (streamed_cap(path, texts), 'streamed window loader')
        elif path in declared:
            caps[path] = (declared[path], 'HCReadBounded literal')
        elif is_native_input(name, texts):
            caps[path] = (default, 'one-shot bounded read')
    for path in sorted((root / 'mods').glob('*/data/defaults/**/*.json')):
        caps.setdefault(path.relative_to(root).as_posix(), (default, 'profile default image'))
    if (root / SETTINGS_TEMPLATE).is_file():
        caps.setdefault(SETTINGS_TEMPLATE, (default, 'profile settings image'))
    return caps


def check(root=ROOT, mission_files=None):
    """Return (errors, checked) for every shipped JSON with a native loader cap."""
    root = Path(root)
    caps = loader_caps(root, mission_files)
    errors = []
    for path, (cap, loader) in sorted(caps.items()):
        size = (root / path).stat().st_size
        if not within_budget(size, cap):
            errors.append('json loader cap path=%s bytes=%d cap=%d limit_percent=%d loader="%s" reason=above_limit'
                          % (path, size, cap, LIMIT_PERCENT, loader))
    return errors, len(caps)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        errors, checked = check()
    except (OSError, ValueError) as exc:
        errors, checked = [str(exc)], 0
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors, 'checked': checked,
                      'limit_percent': LIMIT_PERCENT}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
