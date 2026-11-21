"""Build HollowCountryAnims.pbo (ships inside @HollowCountry next to HollowCountry.pbo). Stdlib only.

The PBO carries no vanilla graph content: no copied sheet, template, instance or clip. It holds:

* hc_infected.agr  our graph file: the vanilla infected template, sync table and sheets
                   referenced by their DZ/ paths, the ControlTemplate interface the vanilla sheets
                   and the engine bind to (variable/command declarations only), plus our
                   CMD_HC_POSE command and HCPose variable, our sheet and DefaultRunNode
                   HCMasterControl. The vanilla Debug panel is not carried.
* hc_infected.asi  a child instance: ParentTemplates names the vanilla infected_main.asi
                   (the engine's own inheritance, as player_main_1h_bandage.asi does with
                   player_main_1h.asi) and our file only adds the lines for our eight slots.
* hc_poses.agf, config.cpp, scripts/ and our authored clips.

There is no .ast: our clips use eight DEAD slots of the vanilla template (filled by the vanilla
instance, referenced by no vanilla sheet; checked at build time), so the vanilla template is used
as is. The vanilla files are read only at build time (from the installed game) to check that and
to take the ControlTemplate declarations and resource references.

    python3 tools/anim/build_infected_clips.py --addons <DayZ>/Addons --out build/anims
    python3 tools/anim/build_anims_addon.py   --addons <DayZ>/Addons --out build/anims

writes build/anims/addons/HollowCountryAnims.pbo (unsigned). Build outputs stay outside git.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

PREFIX = 'HollowCountryAnims'
BASE = PREFIX + '/anims/infected/'
VANILLA = 'infected\\infected_main\\'
VANILLA_SHEETS = ('Locomotion.agf', 'Combat.agf', 'Interaction.agf')
# (vanilla dead slot we fill, our clip). The slot names are the vanilla template's; the clips are ours.
CLIPS = (('Default.Normal.z_erc_idle_fight01', 'hc_sit_wall_idle'),
         ('Default.Normal.z_erc_attack_up_combo03', 'hc_sit_wall_getup'),
         ('Idles.VarA.Idle02', 'hc_prone_sleep_idle'),
         ('Idles.VarA.Idle03', 'hc_prone_sleep_getup'),
         ('Idles.VarA.Idle04', 'hc_lie_rise_idle'),
         ('Idles.VarB.Idle02', 'hc_lie_rise_getup'),
         ('Idles.VarB.Idle03', 'hc_feed_kneel_idle'),
         ('Idles.VarB.Idle04', 'hc_feed_kneel_getup'))
# Optional authored variant; not selected by CMD_HC_POSE, so it needs no template slot.
EXTRA_CLIPS = ('hc_lie_face_down_idle', 'hc_lie_face_down_getup')
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods' / PREFIX


def guid(path):
    return '{%s}' % hashlib.sha1(path.encode('ascii')).hexdigest()[:16].upper()


def _ref(path):
    return '"%s%s"' % (guid(path), path)


def _block(text, header):
    """(start, end) of the block whose header starts at ``header``; end is the closing brace index."""
    at = text.index(header)
    i = at
    depth = 0
    quoted = False
    while i < len(text):
        c = text[i]
        if c == '"':
            quoted = not quoted        # braces inside "{GUID}..." strings are not blocks
        elif quoted:
            pass
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return at, i
        i += 1
    raise ValueError('unbalanced braces after ' + header)


def _field(text, key):
    m = re.search(r'^\s*%s ("\{[0-9A-F]{16}\}[^"]+")' % key, text, re.M)
    if not m:
        raise ValueError('vanilla graph has no %s reference' % key)
    return m.group(1)


def vanilla_interface(agr):
    """The Variables and Commands blocks of the vanilla ControlTemplate (declarations only)."""
    return '\n'.join(_interface_blocks(agr))


def _interface_blocks(agr):
    start, end = _block(agr, 'ControlTemplate AnimSrcGCT')
    body = agr[agr.index('" {', start) + 3:end]      # skip the quoted "{id}" in the header
    parts = []
    for header in ('Variables {', 'Commands {'):
        s, e = _block(body, header)
        s = body.rindex('\n', 0, s) + 1                # keep the line's indentation
        parts.append(body[s:e + 1])
    rest = re.sub(r'\s', '', body.replace(parts[0], '').replace(parts[1], ''))
    if rest:
        raise ValueError('vanilla ControlTemplate has more than Variables/Commands; review the pose graph')
    return parts


def build_graph(agr, aw):
    """Return {pbo member: text} for our graph file and child instance."""
    if 'DefaultRunNode "MasterControl"' not in agr:
        raise ValueError('vanilla graph no longer starts at MasterControl; review the pose layer')
    template = _field(agr, 'AnimSetTemplate')
    sync = _field(agr, 'AnimSyncTable')
    s, e = _block(agr, 'GraphFilesResourceNames')
    sheets = re.findall(r'"\{[0-9A-F]{16}\}DZ/[^"]+\.agf"', agr[s:e])
    if not sheets:
        raise ValueError('vanilla graph lists no sheets')
    s, e = _block(aw, 'AnimSetInstances')
    parent = re.findall(r'"\{[0-9A-F]{16}\}DZ/[^"]+/infected_main\.asi"', aw[s:e])
    if len(parent) != 1:
        raise ValueError('vanilla workspace does not name exactly one infected_main.asi')
    variables, commands = _interface_blocks(agr)
    # ours go after the vanilla declarations, so every vanilla variable/command keeps its order
    interface = (variables[:variables.rindex('}')]
                 + ' AnimSrcGCTVarInt HCPose {\n    DefaultValue 0\n    MinValue 0\n    MaxValue 4\n   }\n   AnimSrcGCTVarInt HCPoseFrom {\n    DefaultValue 0\n    MinValue 0\n    MaxValue 4\n   }\n  }\n'
                 + commands[:commands.rindex('}')]
                 + ' AnimSrcGCTCmd CMD_HC_POSE {\n    Synchronized 1\n   }\n  }')
    gct = guid(BASE + 'hc_infected.agr#gct')
    agr_out = ('AnimSrcGraph {\n AnimSetTemplate %s\n AnimSyncTable %s\n ControlTemplate AnimSrcGCT "%s" {\n'
               '%s\n }\n Debug AnimSrcGD "%s" {\n }\n GraphFilesResourceNames {\n  %s\n }\n'
               ' DefaultRunNode "HCMasterControl"\n}\n') % (
        template, sync, gct, interface, gct, ' '.join(sheets + [_ref(BASE + 'hc_poses.agf')]))
    lines = ''.join('  AnimSetInstanceSource_Line "%s" {\n   Resource %s\n  }\n'
                    % (slot, _ref(BASE + 'clips/%s.anm' % clip)) for slot, clip in CLIPS)
    asi_out = ('AnimSetInstanceSource {\n Template %s\n ParentTemplates {\n  %s\n }\n Lines {\n%s }\n}\n'
               % (template, parent[0], lines))
    return {'anims/infected/hc_infected.agr': agr_out, 'anims/infected/hc_infected.asi': asi_out}


def _read(addons_dir, names):
    from tools.audit import pbo_config as pc
    path = os.path.join(addons_dir, 'anims_workspaces.pbo')
    index = pc.read_pbo_index(path)
    out = []
    for name in names:
        data = pc.read_member(path, index, VANILLA + name, max_bytes=4 << 20)
        if data is None:
            raise FileNotFoundError(VANILLA + name)
        out.append(data.decode('utf-8').replace('\r\n', '\n'))
    return out


def read_vanilla(addons_dir):
    """Installed vanilla infected.agr and infected.aw text (read only, never shipped as is)."""
    return _read(addons_dir, ('infected.agr', 'infected.aw'))


def read_vanilla_slot_sources(addons_dir):
    """(infected.ast, infected_main.asi, all vanilla sheets joined) for the dead-slot check."""
    ast, asi, *sheets = _read(addons_dir, ('infected.ast', 'infected_main.asi') + VANILLA_SHEETS)
    return ast, asi, '\n'.join(sheets)


def check_dead_slots(ast, asi, sheets):
    """Refuse unless every slot we fill is in the vanilla template and instance and unused by vanilla."""
    for slot, _ in CLIPS:
        group, column, anim = slot.split('.')
        m = re.search(r'Name "%s"\s*Animations \{([^}]*)\}\s*Columns \{([^}]*)\}' % re.escape(group), ast)
        if not m or '"%s"' % anim not in m.group(1) or '"%s"' % column not in m.group(2):
            raise ValueError('slot %s is not in the vanilla template' % slot)
        if '"%s"' % slot not in asi:
            raise ValueError('slot %s is not filled by the vanilla instance' % slot)
        if anim in sheets:
            raise ValueError('slot %s is used by a vanilla sheet; pick another dead slot' % slot)


def pack(files, prefix=PREFIX):
    """Stored (method 0) PBO with a prefix property and SHA-1 trailer, like tools/package/pbo.py."""
    names = sorted(files, key=lambda n: (n.casefold(), n))
    header = bytearray(b'\0' + struct.pack('<5I', 0x56657273, 0, 0, 0, 0))
    header += b'prefix\0' + prefix.encode('ascii') + b'\0\0'
    payload = bytearray()
    for name in names:
        data = files[name]
        header += name.replace('/', '\\').encode('ascii') + b'\0' + struct.pack('<5I', 0, 0, 0, 0, len(data))
        payload += data
    body = bytes(header + bytes(21) + payload)
    return body + b'\0' + hashlib.sha1(body).digest()


def check_expression_calls(ours, sheets):
    """Refuse graph expressions calling functions no vanilla sheet calls.

    The engine rejects an unknown call only when it first loads the graph for
    a spawned body, and the server then crashes (GetVariableInt, build 134).
    Variables are read by bare name, as in vanilla's "IdleState == 0".
    """
    def calls(text):
        found = set()
        for expr in re.findall(r'(?:Condition|Expression|Value)\s+"([^"]*)"', text):
            found.update(re.findall(r'([A-Za-z_]\w*)\s*\(', expr))
        return found
    unknown = sorted(calls(ours) - calls(sheets))
    if unknown:
        raise ValueError('graph expressions call functions vanilla sheets never use: ' + ', '.join(unknown))


def collect(addons_dir, clip_dir):
    ast, asi, sheets = read_vanilla_slot_sources(addons_dir)
    check_dead_slots(ast, asi, sheets)
    check_expression_calls((SOURCE / 'anims/infected/hc_poses.agf').read_text(encoding='utf-8'), sheets)
    files = {}
    for p in sorted(SOURCE.rglob('*')):
        if p.is_file() and not p.name.startswith('$'):
            files[p.relative_to(SOURCE).as_posix()] = p.read_bytes()
    for member, text in build_graph(*read_vanilla(addons_dir)).items():
        files[member] = text.replace('\n', '\r\n').encode('utf-8')
    for clip in tuple(clip for _, clip in CLIPS) + EXTRA_CLIPS:
        path = os.path.join(clip_dir, clip + '.anm')
        with open(path, 'rb') as h:
            files['anims/infected/clips/%s.anm' % clip] = h.read()
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--addons', required=True, help='installed DayZ (or DayZServer) Addons folder, read only')
    ap.add_argument('--out', default='build/anims', help='build folder with clips/ (outside git)')
    args = ap.parse_args(argv)
    files = collect(args.addons, os.path.join(args.out, 'clips'))
    os.makedirs(os.path.join(args.out, 'addons'), exist_ok=True)
    target = os.path.join(args.out, 'addons', PREFIX + '.pbo')
    with open(target, 'wb') as h:
        h.write(pack(files))
    for name in sorted(files):
        print('%8d %s' % (len(files[name]), name))
    print('wrote', target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
