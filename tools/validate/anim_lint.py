"""Lint our animation sources (BVH, SET6 .anm) and the built addon config. Stdlib only, offline.

    python3 -B -m tools.validate.anim_lint [--addons DIR] [--require-installed] [--in-place] [FILE ...]

Always checks mods/HollowCountryAnims (config.cpp, $PBOPREFIX$, graph file names) and the clip names
tools/anim/build_anims_addon.py binds; each FILE (.bvh or .anm) is checked in addition. Rules:

  HC-A001 file names and clip names carry our prefix (hc_), config classes carry HC_, paths stay in
          HollowCountryAnims; nothing of ours is published under a vanilla or dependency name
  HC-A010 frame rate and length limits (fps 10..120 for BVH, 15..60 for SET6; at most 20 s)
  HC-A020 skeleton bone set: BVH must map every required body bone onto the target rig; a SET6 clip must
          carry exactly the target rig's clip bones (needs --addons) or at least the required body and
          root-helper bones (offline); no duplicate or unknown names, keys in range and increasing,
          finite values, unit quaternions
  HC-A030 root motion sanity: no teleport frames, no impossible root speed, bounded vertical excursion;
          SET6 EntityPosition/Collision helpers stay at the origin unless --allow-root-motion; --in-place
          also bounds BVH horizontal travel
  HC-A040 joint angular speed within 1440 deg/s
  HC-A050 female skeleton parity: every posed female infected uses the same mesh skeleton and
          skeletonName as the male sitter, and (with --addons) the installed ZombieFemaleBase, ZombieMaleBase
          and ZombieBase enfanimsys agree with it. Same file means same rest bones. Whether female outfit
          meshes skin cleanly on that skeleton is not decidable offline; it stays a native check.

With --addons the stock comparison and the exact rig bone set run; without it the offline rules still run
and the output says the stock comparison did not run. --require-installed turns that into a failure.
Output carries repository-relative names only. Exit 0 pass, 1 findings.
"""
import argparse
import math
import os
from pathlib import Path
import re
import struct
import sys

from tools.anim import anm, rig

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'mods/HollowCountryAnims/config.cpp'
MOD = ROOT / 'mods/HollowCountryAnims'
PREFIX = 'HollowCountryAnims'
OWN_FILE = re.compile(r'^hc_[a-z0-9]+(?:_[a-z0-9]+)*$')
MAX_BYTES = 16 << 20
MAX_SECONDS = 20.0
BVH_FPS = (10, 120)
ANM_FPS = (15, 60)
JOINT_DPS = 1440.0
ROOT_SPEED_LEGS = 6.0           # root speed limit, leg lengths per second (about a sprint)
ROOT_STEP_LEGS = 0.5            # one frame must not move the root more than half a leg
ROOT_RISE_LEGS = 1.2            # peak-to-peak vertical excursion
IN_PLACE_LEGS = 0.1             # horizontal travel for --in-place
ANM_PELVIS_STEP = 0.35          # metres per frame
ANM_PELVIS_SPEED = 6.0          # metres per second
HELPER_TOLERANCE = 2e-3         # metres, above SET6 quantisation noise
QUAT_TOLERANCE = 0.02
POSE_CLASS = re.compile(r'^HC_Zmb[MF]_')
MESH_ALLOWED = 'dz\\characters\\zombies\\z_hermit_m.xob'   # vanilla file referenced read-only, never copied
SKELETON_NAME = 'hermit_newbindpose.xob'
START_NODE = 'HCMasterControl'
SAFE_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$')


class Findings:
    def __init__(self):
        self.rows = []

    def add(self, code, where, detail):
        self.rows.append('%s %s: %s' % (code, where, detail))


# ---------------------------------------------------------------- config.cpp

def _tokens(text):
    return [m.group() for m in re.finditer(
        r'"(?:[^"]|"")*"|//[^\n]*|/\*.*?\*/|[{};=\[\]:,]|[^\s{};=\[\]:,"]+', text, re.S)
        if not m.group().startswith(('//', '/*'))]


class Node:
    def __init__(self, name, parent):
        self.name, self.parent = name, parent
        self.fields, self.children, self.forward = {}, [], False

    def child(self, name):
        return next((c for c in self.children if c.name == name), None)


def parse_config(text):
    """Class tree (fields hold raw value text) of a config.cpp; ValueError on malformed input."""
    tokens = _tokens(text)
    if len(tokens) > 200000:
        raise ValueError('config.size')
    pos = 0

    def body(node, depth):
        nonlocal pos
        if depth > 16:
            raise ValueError('config.depth')
        while pos < len(tokens):
            token = tokens[pos]
            if token == '}':
                pos += 1
                return
            if token == 'class':
                name = tokens[pos + 1]
                pos += 2
                parent = None
                if tokens[pos] == ':':
                    parent = tokens[pos + 1]
                    pos += 2
                child = Node(name, parent)
                node.children.append(child)
                if tokens[pos] == ';':
                    child.forward = True
                    pos += 1
                    continue
                if tokens[pos] != '{':
                    raise ValueError('config.syntax')
                pos += 1
                body(child, depth + 1)
                if pos < len(tokens) and tokens[pos] == ';':
                    pos += 1
                continue
            key = token
            pos += 1
            if pos < len(tokens) and tokens[pos] == '[':
                key += '[]'
                pos += 2
            if pos >= len(tokens) or tokens[pos] != '=':
                raise ValueError('config.syntax')
            pos += 1
            raw, braces = [], 0
            while pos < len(tokens) and not (tokens[pos] == ';' and braces == 0):
                braces += tokens[pos] == '{'
                braces -= tokens[pos] == '}'
                raw.append(tokens[pos])
                pos += 1
            pos += 1
            node.fields[key] = ' '.join(raw)
        if depth:
            raise ValueError('config.unclosed')

    root = Node('', None)
    body(root, 0)
    return root


def _string(raw):
    if raw is None or len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return None
    return raw[1:-1]


def _strings(raw):
    return re.findall(r'"((?:[^"]|"")*)"', raw or '')


def lint_config(path, findings, rel):
    try:
        data = Path(path).read_bytes()
        if len(data) > MAX_BYTES:
            raise ValueError('config.size')
        tree = parse_config(data.decode('utf-8'))
    except (OSError, UnicodeDecodeError, ValueError, IndexError):
        findings.add('HC-A001', rel, 'config does not parse')
        return None
    patches = tree.child('CfgPatches')
    mods = tree.child('CfgMods')
    vehicles = tree.child('CfgVehicles')
    if patches is None or [c.name for c in patches.children if not c.forward] != [PREFIX]:
        findings.add('HC-A001', rel, 'CfgPatches must define exactly %s' % PREFIX)
    else:
        for unit in _strings(patches.child(PREFIX).fields.get('units[]')):
            if not unit.startswith('HC_'):
                findings.add('HC-A001', rel, 'CfgPatches unit %s lacks the HC_ prefix' % unit)
    if mods is None or [c.name for c in mods.children if not c.forward] != [PREFIX]:
        findings.add('HC-A001', rel, 'CfgMods must define exactly %s' % PREFIX)
    elif _string(mods.child(PREFIX).fields.get('dir')) != PREFIX:
        findings.add('HC-A001', rel, 'CfgMods dir must be %s' % PREFIX)
    if vehicles is None:
        findings.add('HC-A001', rel, 'CfgVehicles missing')
        return None
    blocks = {}
    for cls in vehicles.children:
        if cls.forward:
            continue
        if not cls.name.startswith('HC_'):
            findings.add('HC-A001', rel, 'class %s defined outside the HC_ prefix' % cls.name)
        anim = cls.child('enfanimsys')
        if anim is not None:
            blocks[cls.name] = {k: _string(v) for k, v in anim.fields.items()}
    for name, block in sorted(blocks.items()):
        for key in ('graphname', 'defaultinstance'):
            value = block.get(key) or ''
            if not value.startswith(PREFIX + '\\'):
                findings.add('HC-A001', rel, '%s %s is outside %s' % (name, key, PREFIX))
        if block.get('startnode') != START_NODE:
            findings.add('HC-A001', rel, '%s startnode must be %s' % (name, START_NODE))
    lint_female_parity(blocks, findings, rel)
    return blocks


def lint_female_parity(blocks, findings, rel):
    """HC-A050, config half: posed female classes use the male sitter's mesh skeleton."""
    male = blocks.get('HC_ZmbM_Sitter')
    if male is None:
        findings.add('HC-A050', rel, 'reference class HC_ZmbM_Sitter has no enfanimsys')
        return
    if male.get('meshObject') != MESH_ALLOWED or male.get('skeletonName') != SKELETON_NAME:
        findings.add('HC-A050', rel, 'HC_ZmbM_Sitter mesh/skeleton is not the stock infected skeleton')
    for name, block in sorted(blocks.items()):
        if name.startswith('HC_ZmbF_'):
            for key in ('meshObject', 'skeletonName'):
                if block.get(key) != male.get(key):
                    findings.add('HC-A050', rel, '%s %s differs from the male sitter' % (name, key))


def stock_enfanimsys(addons):
    """{class: {meshObject, skeletonName}} for the installed ZombieBase/MaleBase/FemaleBase."""
    from tools.audit import pbo_config as pc
    path = Path(addons) / 'characters_zombies.pbo'
    if not path.is_file():
        raise FileNotFoundError('characters_zombies.pbo')
    index = pc.read_pbo_index(path)
    data = pc.read_member(path, index, 'config.bin')
    classes = pc.parse_rap(data, ('CfgVehicles',))['CfgVehicles']
    rap = pc._Rap(data)
    offsets = {}
    for kind, name, offset in rap.entries(16)[1]:
        if kind == 'class' and name == 'CfgVehicles':
            offsets = {n: o for k, n, o in rap.entries(offset)[1] if k == 'class'}
    out = {}
    for cls in ('ZombieBase', 'ZombieMaleBase', 'ZombieFemaleBase'):
        for ancestor in pc.ancestry(classes, cls):
            hit = None
            for kind, field, value in rap.entries(offsets[ancestor])[1]:
                if kind == 'class' and field == 'enfanimsys':
                    hit = dict((n, v) for k, n, v in rap.entries(value)[1] if k == 'value')
            if hit is not None:
                out[cls] = {'meshObject': hit.get('meshObject'), 'skeletonName': hit.get('skeletonName')}
                break
    return out


def lint_stock_parity(blocks, stock, findings):
    male = (blocks or {}).get('HC_ZmbM_Sitter') or {}
    for cls in ('ZombieBase', 'ZombieMaleBase', 'ZombieFemaleBase'):
        row = stock.get(cls)
        if row is None:
            findings.add('HC-A050', 'stock', '%s has no installed enfanimsys' % cls)
        elif (row['meshObject'], row['skeletonName']) != (male.get('meshObject'), male.get('skeletonName')):
            findings.add('HC-A050', 'stock', '%s mesh/skeleton differs from our posed classes' % cls)


def lint_mod_tree(root, findings):
    prefix = root / '$PBOPREFIX$'
    try:
        if prefix.read_text(encoding='utf-8').strip() != PREFIX:
            findings.add('HC-A001', '$PBOPREFIX$', 'prefix must be %s' % PREFIX)
    except OSError:
        findings.add('HC-A001', '$PBOPREFIX$', 'missing')
    anims = root / 'anims'
    for path in sorted(anims.rglob('*')) if anims.is_dir() else ():
        if path.is_file() and not OWN_FILE.match(path.stem.lower().split('.')[0]):
            findings.add('HC-A001', path.relative_to(ROOT).as_posix(), 'file name lacks the hc_ prefix')


def lint_clip_names(findings):
    try:
        from tools.anim import build_anims_addon as build
    except ImportError:
        findings.add('HC-A001', 'tools/anim/build_anims_addon.py', 'cannot import clip list')
        return
    for _slot, clip in build.CLIPS:
        if not OWN_FILE.match(clip):
            findings.add('HC-A001', 'build_anims_addon.CLIPS', 'clip %s lacks the hc_ prefix' % clip)
    for clip in build.EXTRA_CLIPS:
        if not OWN_FILE.match(clip):
            findings.add('HC-A001', 'build_anims_addon.EXTRA_CLIPS', 'clip %s lacks the hc_ prefix' % clip)


# ---------------------------------------------------------------- BVH sources

def lint_bvh(path, rel, findings, rig_bones=None, in_place=False, name_rule=True):
    from tools.anim import retarget
    if name_rule and not OWN_FILE.match(Path(path).stem):
        findings.add('HC-A001', rel, 'source name lacks the hc_ prefix')
    try:
        raw = Path(path).read_bytes()[:MAX_BYTES + 1]
        if len(raw) > MAX_BYTES:
            raise ValueError('input.file_limit')
        source = retarget.parse_bvh(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r'[A-Za-z0-9_.:-]+', str(exc)) else 'input.invalid'
        findings.add('HC-A020', rel, 'does not parse (%s)' % reason)
        return
    fps = 1.0 / source.frame_time
    count = len(source.frames)
    if not BVH_FPS[0] <= fps <= BVH_FPS[1]:
        findings.add('HC-A010', rel, 'frame rate %.2f outside %d..%d' % (fps, *BVH_FPS))
    if count < 2:
        findings.add('HC-A010', rel, 'needs at least two frames')
    if (count - 1) * source.frame_time > MAX_SECONDS:
        findings.add('HC-A010', rel, 'longer than %g s' % MAX_SECONDS)
    bones = set(rig_bones) if rig_bones else set(retarget.REQUIRED_BONES) | set(retarget.DEFAULT_MAP.values())
    try:
        reverse = retarget._mapping(source, bones, None)
    except ValueError as exc:
        findings.add('HC-A020', rel, 'skeleton: %s' % exc)
        return
    if (count - 1) * source.frame_time > MAX_SECONDS or count > int(MAX_SECONDS * BVH_FPS[1]):
        return
    chain = [reverse[n] for n in ('LeftUpLeg', 'LeftLeg', 'LeftFoot')]
    length = retarget._leg_length(source.pose(), chain)
    root = reverse['Pelvis']
    rest = source.pose().pos(root)
    poses = [source.pose(values) for values in source.frames]
    track = [rig.vsub(pose.pos(root), rest) for pose in poses]
    steps = [rig.vlen(rig.vsub(b, a)) for a, b in zip(track, track[1:])]
    if length <= 1e-8:
        findings.add('HC-A030', rel, 'leg length is zero')
        return
    if steps and max(steps) > ROOT_STEP_LEGS * length:
        findings.add('HC-A030', rel, 'root jumps %.2f leg lengths in one frame' % (max(steps) / length))
    if steps and max(steps) / source.frame_time > ROOT_SPEED_LEGS * length:
        findings.add('HC-A030', rel, 'root speed above %g leg lengths per second' % ROOT_SPEED_LEGS)
    heights = [v[1] for v in track]
    if heights and max(heights) - min(heights) > ROOT_RISE_LEGS * length:
        findings.add('HC-A030', rel, 'root vertical excursion above %g leg lengths' % ROOT_RISE_LEGS)
    if in_place and track:
        span = max(rig.vlen((a[0] - b[0], 0.0, a[2] - b[2])) for a in track for b in track[::max(1, len(track) // 64)])
        if span > IN_PLACE_LEGS * length:
            findings.add('HC-A030', rel, 'in-place clip travels %.2f leg lengths' % (span / length))
    quats = {joint.name: [pose.local[joint.name][1] for pose in poses] for joint in source.joints}
    worst = _worst_speed(quats, source.frame_time)
    if worst is not None and worst[0] > JOINT_DPS:
        findings.add('HC-A040', rel, 'joint %s turns %.0f deg/s (limit %g)' % (worst[1], worst[0], JOINT_DPS))



def _worst_speed(by_bone, dt_of):
    """(deg/s, bone) of the fastest joint; dt_of is seconds per step (float) or {bone: [dt per step]}."""
    worst = None
    for name, values in by_bone.items():
        for i in range(1, len(values)):
            dt = dt_of if isinstance(dt_of, float) else dt_of[name][i - 1]
            if dt <= 0:
                continue
            a, b = values[i - 1], values[i]
            turn = 2 * math.acos(min(1.0, abs(sum(x * y for x, y in zip(a, b)))))
            speed = math.degrees(turn) / dt
            if worst is None or speed > worst[0]:
                worst = (speed, name)
    return worst


# ---------------------------------------------------------------- SET6 clips

def lint_anm(path, rel, findings, rig_bones=None, allow_root_motion=False, name_rule=True):
    if name_rule and not OWN_FILE.match(Path(path).stem):
        findings.add('HC-A001', rel, 'clip name lacks the hc_ prefix')
    try:
        raw = Path(path).read_bytes()[:MAX_BYTES + 1]
        if len(raw) > MAX_BYTES:
            raise ValueError('input.file_limit')
        clip = anm.read(raw)
    except (OSError, ValueError, struct.error, IndexError):
        findings.add('HC-A020', rel, 'does not parse as SET6')
        return
    if not ANM_FPS[0] <= clip.fps <= ANM_FPS[1]:
        findings.add('HC-A010', rel, 'frame rate %d outside %d..%d' % (clip.fps, *ANM_FPS))
    if clip.frames < 2:
        findings.add('HC-A010', rel, 'needs at least two frames')
    if clip.fps and clip.frames / clip.fps > MAX_SECONDS:
        findings.add('HC-A010', rel, 'longer than %g s' % MAX_SECONDS)
    names = [b.name for b in clip.bones]
    if len(set(names)) != len(names):
        findings.add('HC-A020', rel, 'duplicate bone names')
    for name in names:
        if not SAFE_NAME.match(name):
            findings.add('HC-A020', rel, 'unsafe bone name')
            return
    if rig_bones is not None:
        if set(names) != set(rig_bones):
            missing, extra = sorted(set(rig_bones) - set(names)), sorted(set(names) - set(rig_bones))
            findings.add('HC-A020', rel, 'bone set differs from the target rig (missing %s, extra %s)'
                         % (','.join(missing[:6]) or '-', ','.join(extra[:6]) or '-'))
    else:
        required = set(rig.ROOT_EXTRAS) | {'Pelvis', 'Spine', 'Spine2', 'Spine3', 'Neck', 'Head',
                                           'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'RightUpLeg', 'RightLeg',
                                           'RightFoot', 'LeftArm', 'LeftForeArm', 'LeftHand',
                                           'RightArm', 'RightForeArm', 'RightHand'}
        missing = sorted(required - set(names))
        if missing:
            findings.add('HC-A020', rel, 'missing bones %s' % ','.join(missing[:6]))
    for bone in clip.bones:
        for label, track in (('t', bone.t), ('q', bone.q), ('s', bone.s)):
            frames = list(track.frames)
            if any(b <= a for a, b in zip(frames, frames[1:])) or any(not 0 <= f < max(clip.frames, 1) for f in frames):
                findings.add('HC-A020', rel, '%s %s keys out of range or not increasing' % (bone.name, label))
            if any(not math.isfinite(c) for v in track.values for c in v):
                findings.add('HC-A020', rel, '%s %s has non-finite values' % (bone.name, label))
        if any(abs(math.sqrt(sum(c * c for c in v)) - 1.0) > QUAT_TOLERANCE for v in bone.q.values):
            findings.add('HC-A020', rel, '%s rotation is not a unit quaternion' % bone.name)
    if not allow_root_motion:
        for name in rig.ROOT_EXTRAS:
            bone = clip.bone(name)
            if bone is not None and any(abs(c) > HELPER_TOLERANCE for v in bone.t.values for c in v):
                findings.add('HC-A030', rel, '%s carries root motion' % name)
            if bone is not None and any(abs(abs(v[3]) - 1) > QUAT_TOLERANCE for v in bone.q.values):
                findings.add('HC-A030', rel, '%s carries root rotation' % name)
    pelvis = clip.bone('Pelvis')
    if pelvis is not None and len(pelvis.t.values) > 1:
        for (fa, a), (fb, b) in zip(zip(pelvis.t.frames, pelvis.t.values), zip(pelvis.t.frames[1:], pelvis.t.values[1:])):
            step = rig.vlen(rig.vsub(b, a))
            if step > ANM_PELVIS_STEP * (fb - fa) or (clip.fps and step * clip.fps / (fb - fa) > ANM_PELVIS_SPEED):
                findings.add('HC-A030', rel, 'pelvis moves %.2f m between frames %d and %d' % (step, fa, fb))
                break
    dts = {b.name: [(y - x) / clip.fps for x, y in zip(b.q.frames, b.q.frames[1:])] for b in clip.bones if clip.fps}
    worst = _worst_speed({b.name: [rig.qnorm(v) for v in b.q.values] for b in clip.bones}, dts) if clip.fps else None
    if worst is not None and worst[0] > JOINT_DPS:
        findings.add('HC-A040', rel, 'joint %s turns %.0f deg/s (limit %g)' % (worst[1], worst[0], JOINT_DPS))


# ---------------------------------------------------------------- driver and preland selection

def is_anim_path(path):
    path = path.replace('\\', '/')
    if path.startswith('tests/'):
        return False
    return (path.startswith(('tools/anim/', 'mods/HollowCountryAnims/')) or path == 'tools/validate/anim_lint.py'
            or path.endswith(('.bvh', '.anm')))


def changed_inputs(paths):
    """Source files to lint for a changed-file list, or None when no animation file changed."""
    if not any(is_anim_path(p) for p in paths):
        return None
    return [p for p in paths if p.endswith(('.bvh', '.anm')) and is_anim_path(p) and (ROOT / p).is_file()]


def run(files, *, config=CONFIG, mod=MOD, addons=None, require_installed=False, in_place=False,
        allow_root_motion=False, name_rule=True):
    findings = Findings()
    notes = []
    rig_bones = None
    stock = None
    if addons is not None and Path(addons).expanduser().is_dir():
        try:
            rig_bones = rig.load_skeleton(str(Path(addons).expanduser()))[2]
            stock = stock_enfanimsys(Path(addons).expanduser())
        except (OSError, ValueError, KeyError, struct.error):
            findings.add('HC-A050', 'stock', 'installed characters_zombies.pbo cannot be read')
    elif require_installed:
        findings.add('HC-A050', 'stock', 'installed Addons required (--require-installed) but not given')
    if rig_bones is None or stock is None:
        notes.append('NOTE female stock comparison and exact rig bone set not run (no installed Addons)')
    rel = os.path.relpath(config, ROOT) if str(config).startswith(str(ROOT)) else Path(config).name
    blocks = lint_config(config, findings, rel.replace(os.sep, '/'))
    if stock is not None:
        lint_stock_parity(blocks, stock, findings)
    if Path(mod).is_dir():
        lint_mod_tree(Path(mod), findings)
    lint_clip_names(findings)
    for file in files:
        path = Path(file)
        shown = os.path.relpath(path, ROOT).replace(os.sep, '/') if str(path.resolve()).startswith(str(ROOT)) else path.name
        if path.suffix.lower() == '.bvh':
            lint_bvh(path, shown, findings, rig_bones, in_place, name_rule)
        elif path.suffix.lower() == '.anm':
            lint_anm(path, shown, findings, rig_bones, allow_root_motion, name_rule)
        else:
            findings.add('HC-A001', shown, 'not a .bvh or .anm file')
    return findings.rows, notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('files', nargs='*', type=Path)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--addons', type=Path, default=None)
    parser.add_argument('--require-installed', action='store_true')
    parser.add_argument('--in-place', action='store_true', help='BVH sources must not travel')
    parser.add_argument('--allow-root-motion', action='store_true')
    args = parser.parse_args(argv)
    rows, notes = run(args.files, config=args.config, addons=args.addons,
                      require_installed=args.require_installed, in_place=args.in_place,
                      allow_root_motion=args.allow_root_motion)
    for line in notes + rows:
        print(line)
    print('anim_lint: %s files=%d findings=%d' % ('FAIL' if rows else 'pass', len(args.files), len(rows)))
    return 1 if rows else 0


if __name__ == '__main__':
    sys.exit(main())
