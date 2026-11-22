"""Every authored mission source must be on the reviewed bundle list (pbo.MISSION_FILES).

Run ``python3 -B -m tools.validate.mission_sources``. Exit 0 when the tree under
mission/hollow-country and pbo.MISSION_FILES agree, 1 otherwise. friend_bundle refuses an
unreviewed mission source at build time; this check finds the gap before landing, not at
friendcycle time (build 160 refused ce/hc-site-measurements.json).
"""
from pathlib import Path

from tools.package import pbo

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mission/hollow-country'


def findings(source=SOURCE, reviewed=pbo.MISSION_FILES):
    files = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    return ([('unreviewed', rel) for rel in sorted(files - reviewed)]
            + [('missing', rel) for rel in sorted(reviewed - files)])


def main():
    rows = findings()
    for code, rel in rows:
        print(f'mission_sources: {code} {rel}')
    print('mission_sources: ' + ('FAIL %d finding(s); update pbo.MISSION_FILES or the tree' % len(rows)
                                 if rows else 'PASS %d reviewed mission files' % len(pbo.MISSION_FILES)))
    return 1 if rows else 0


if __name__ == '__main__':
    raise SystemExit(main())
