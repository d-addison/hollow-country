"""Every authored mission source must be on the reviewed bundle list (pbo.MISSION_FILES).

Run ``python3 -B -m tools.validate.mission_sources``. Exit 0 when the tree under
mission/hollow-country and pbo.MISSION_FILES agree, 1 otherwise. friend_bundle refuses an
unreviewed mission source at build time; this check finds the gap before landing, not at
friendcycle time (build 160 refused ce/hc-site-measurements.json).

Two more offline mission invariants share this entry point so preland can print one
summary line each (the producers emit a 10-20 KB JSON line):

``--events``        hc_events authored-policy validation, including the measured-y
                    anchor invariants (finite y on every anchor, no zero CE zone).
``--ce-slots MISSION``
                    CE slot pressure on a staged mission (stock files plus the
                    installed overlays). Preland gates on the joint Military/Police/Prison
                    weapon reservation with LIMIT headroom. ``friend_install --check``
                    uses the separate legacy route pressure estimate from ``problems()``.
                    The all-categories static bound is informational because unmodified
                    vanilla also fails it (docs/tools/CE_FILL_PROBE.md). Exit 0 pass,
                    1 fail, 2 unreadable inputs. Native placement requires a live check.
"""
import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from tools.package import pbo

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mission/hollow-country'


def findings(source=SOURCE, reviewed=pbo.MISSION_FILES):
    files = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    return ([('unreviewed', rel) for rel in sorted(files - reviewed)]
            + [('missing', rel) for rel in sorted(reviewed - files)])


def events_main(source=SOURCE):
    from tools.package import hc_events
    try:
        report = hc_events.validate(source)[3]
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        # Refusal reasons name authored events and sites, never local paths.
        print('mission_sources: events FAIL ' + (str(error) if isinstance(error, ValueError) else type(error).__name__))
        return 1
    print('mission_sources: events PASS event_types=%d positions=%d groups=%d (offline policy; runtime PENDING)'
          % (report['event_types'], report['positions'], report['groups']))
    return 0


def ce_slots_main(mission):
    from tools.package import ce_slot_pressure
    mission = Path(mission)
    if not all((mission / name).is_file() for name in ce_slot_pressure.INPUTS):
        print('mission_sources: ce_slots FAIL mission lacks the CE proxy map inputs')
        return 2
    try:
        gate = ce_slot_pressure.feasibility(mission, True, ce_slot_pressure.LIMIT)
        info = ce_slot_pressure.feasibility(mission, False, 1)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, struct.error, ET.ParseError):
        print('mission_sources: ce_slots FAIL CE inputs unreadable or invalid')
        return 2
    print('mission_sources: ce_slots info all-categories demand=%d bound=%d deficit=%d '
          '(not gated: vanilla fails this static bound too)'
          % (info['demand'], info['placeable_upper_bound'], info['deficit']))
    print('mission_sources: ce_slots %s military-weapons demand=%d required=%d deficit=%d limit=%.2f '
          '(offline estimate; not native placement acceptance)'
          % (gate['status'].upper(), gate['demand'], gate['required_with_headroom'],
             max(0, gate['headroom_deficit']), ce_slot_pressure.LIMIT))
    caps = gate.get('engine_caps')
    if caps and caps['status'] != 'pass':
        # A cap violation fails the gate even with deficit=0; name it so the FAIL line is not a mystery.
        print('mission_sources: ce_slots engine_caps FAIL ' + ' '.join(
            '%s.%s=%d>%d' % (v['class'], v['field'], v['actual'], v['cap']) for v in caps['violations'][:12]))
    return 1 if gate['status'] == 'fail' else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--events', action='store_true', help='hc_events invariant summary')
    modes.add_argument('--ce-slots', type=Path, metavar='MISSION', help='CE slot pressure on a staged mission')
    args = parser.parse_args(argv)
    if args.events:
        return events_main()
    if args.ce_slots is not None:
        return ce_slots_main(args.ce_slots)
    rows = findings()
    for code, rel in rows:
        print(f'mission_sources: {code} {rel}')
    print('mission_sources: ' + ('FAIL %d finding(s); update pbo.MISSION_FILES or the tree' % len(rows)
                                 if rows else 'PASS %d reviewed mission files' % len(pbo.MISSION_FILES)))
    return 1 if rows else 0


if __name__ == '__main__':
    raise SystemExit(main())
