"""Quaternion/FK helpers and build-time readers for the installed infected skeleton. Stdlib only.

Nothing from the game is stored in the repository. The clips are built from the skeleton of the
mesh HC_ZmbM_Sitter uses (``z_hermit_m.xob``: bone hierarchy and rest transforms, read at build
time) plus our own pose code; no vanilla animation frame is used. ``load_reference`` reads one
vanilla idle clip for tests only (seam distance, bone list), never for building.

Engine axes: Y up, +Z forward, -X is the character's left. Quaternions are (x, y, z, w).
"""
import math
import struct

from tools.anim import anm

IDENTITY = (0.0, 0.0, 0.0, 1.0)

# Members of the installed DayZ addons read at build time (never copied).
SKELETON_PBO = 'characters_zombies.pbo'      # prefix dz\characters\zombies
SKELETON_MODEL = 'z_hermit_m.xob'            # the HC_ZmbM_Sitter enfanimsys meshObject
# Tests only (codec round trip, seam distance, bone list):
CLIP_PBO = 'anims_anm_infected.pbo'          # prefix DZ\anims\anm\infected
WORKSPACE_PBO = 'anims_workspaces.pbo'       # prefix DZ\anims\workspaces
REFERENCE_CLIP = 'moves\\erected\\zA_erc_idle01.anm'
HIERARCHY_MODEL = 'infected\\models\\z_hermit_m_editorpreview.xob'

# Clip bone list. Infected clips carry these root/helper bones, which the mesh skeleton lacks;
# ours hold them at the origin with no rotation (no root motion, IK helpers unused by infected).
ROOT_EXTRAS = ('EntityPosition', 'Collision')
TAIL_EXTRAS = ('RightHandIK_Helper', 'RightHandIK', 'LeftHandIK')
# Mesh bones that infected clips carry no track for (look-at and hip helpers, right finger tips).
NOT_ANIMATED = ('LookAt', 'LeftHip_Helper', 'RightHip_Helper', 'RightHandRing4', 'RightHandThumb4',
                'RightHandMiddle4', 'RightHandIndex4')
# The mesh rest pose faces -Z; clips face +Z (forward). The pelvis is turned half round about Y.
FACING = (0.0, 1.0, 0.0, 0.0)


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qinv(q):
    return (-q[0], -q[1], -q[2], q[3])


def qnorm(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return tuple(c / n for c in q)


def qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx)


def qaxis(axis, degrees):
    ax = vnorm(axis)
    h = math.radians(degrees) / 2
    s = math.sin(h)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(h))


def qslerp(a, b, t):
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0:
        b, dot = tuple(-c for c in b), -dot
    if dot > 0.9995:
        return qnorm(tuple(x + (y - x) * t for x, y in zip(a, b)))
    th = math.acos(dot)
    s = math.sin(th)
    wa, wb = math.sin((1 - t) * th) / s, math.sin(t * th) / s
    return tuple(wa * x + wb * y for x, y in zip(a, b))


def qbetween(u, v):
    """Shortest rotation taking direction u onto direction v."""
    u, v = vnorm(u), vnorm(v)
    d = sum(a * b for a, b in zip(u, v))
    if d < -0.99999:
        perp = vcross(u, (1, 0, 0)) if abs(u[0]) < 0.9 else vcross(u, (0, 1, 0))
        return qaxis(perp, 180)
    c = vcross(u, v)
    return qnorm((c[0], c[1], c[2], 1 + d))


def vadd(a, b):
    return tuple(x + y for x, y in zip(a, b))


def vsub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def vscale(a, s):
    return tuple(x * s for x in a)


def vlerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def vnorm(a):
    n = math.sqrt(sum(c * c for c in a)) or 1.0
    return tuple(c / n for c in a)


def vlen(a):
    return math.sqrt(sum(c * c for c in a))


class Pose:
    """Parent-local transforms keyed by bone name, plus the hierarchy; FK on demand."""

    def __init__(self, parents, local):
        self.parents = parents            # name -> parent name (None for the root)
        self.local = dict(local)          # name -> (t, q)
        self.order = []                   # parents before children
        seen = set()

        def add(n):
            if n in seen:
                return
            p = parents.get(n)
            if p is not None and p in parents:
                add(p)
            seen.add(n)
            self.order.append(n)
        for n in self.local:
            add(n)
        self._world = None
        self.hinges = {}                  # upper limb bone -> mesh hinge axis in its frame (two-bone IK)

    def copy(self):
        p = Pose(self.parents, self.local)
        p.hinges = self.hinges
        return p

    def world(self):
        if self._world is None:
            w = {}
            for n in self.order:
                t, q = self.local.get(n, ((0.0, 0.0, 0.0), IDENTITY))
                p = self.parents.get(n)
                if p is None or p not in w:
                    w[n] = (t, q)
                else:
                    pt, pq = w[p]
                    w[n] = (vadd(pt, qrot(pq, t)), qmul(pq, q))
            self._world = w
        return self._world

    def pos(self, name):
        return self.world()[name][0]

    def set_world_rot(self, name, wq):
        p = self.parents.get(name)
        pq = self.world()[p][1] if p in self.world() else IDENTITY
        t, _ = self.local[name]
        self.local[name] = (t, qnorm(qmul(qinv(pq), wq)))
        self._world = None

    def rotate_world(self, name, dq):
        """Pre-multiply the bone's world rotation by dq (children follow)."""
        self.set_world_rot(name, qmul(dq, self.world()[name][1]))

    def aim(self, name, child, direction, weight=1.0):
        """Swing ``name`` so the segment name->child points along ``direction``."""
        cur = vsub(self.pos(child), self.pos(name))
        dq = qbetween(cur, direction)
        if weight < 1.0:
            dq = qslerp(IDENTITY, dq, weight)
        self.rotate_world(name, dq)

    def set_root_pos(self, name, world_pos):
        p = self.parents.get(name)
        if p in self.world():
            pt, pq = self.world()[p]
            local_t = qrot(qinv(pq), vsub(world_pos, pt))
        else:
            local_t = world_pos
        self.local[name] = (local_t, self.local[name][1])
        self._world = None


def parse_xob_hierarchy(data):
    """Bone parent map from an XOB6 model's HEAD (names, then 36-byte bone records)."""
    return parse_xob_skeleton(data)[1]


def parse_xob_skeleton(data):
    """(bone names, parent map, rest {name: (t, q)}) from an XOB6 model's HEAD.

    Each 36-byte bone record is the parent-local rest translation (3 floats), rotation
    quaternion (x, y, z, w; 4 floats), then the next-sibling and first-child indices (2 shorts)
    and 2 more shorts.
    """
    if data[:4] != b'FORM' or data[8:12] != b'XOB6':
        raise ValueError('not an XOB6 model')
    start = data.find(b'Scene_Root\0')
    if start < 0:
        raise ValueError('no Scene_Root bone')
    names, pos = [], start
    while True:
        end = data.index(b'\0', pos)
        name = data[pos:end].decode('latin-1')
        pos = end + 1
        if not name or name.endswith('_lod1') or name.endswith('_lod0'):
            break
        names.append(name)
    pos += 6
    recs = []
    rest = {}
    for name in names:
        f = struct.unpack_from('<7f', data, pos)
        rest[name] = (f[:3], qnorm(f[3:]))
        nxt, first = struct.unpack_from('<2h', data, pos + 28)
        recs.append((nxt, first))
        pos += 36
    parents = {}

    def visit(i, parent, depth):
        while 0 <= i < len(names) and depth < 256:
            parents[names[i]] = parent
            if recs[i][1] >= 0:
                visit(recs[i][1], names[i], depth + 1)
            i = recs[i][0]
    visit(0, None, 0)
    if len(parents) != len(names):
        raise ValueError('xob hierarchy walk reached %d of %d bones' % (len(parents), len(names)))
    return names, parents, rest


def skeleton_from_xob(data):
    """(parents, rest, clip bone order) for clips on this mesh skeleton."""
    names, parents, rest = parse_xob_skeleton(data)
    for n in ROOT_EXTRAS + TAIL_EXTRAS:
        if n in parents:
            raise ValueError('mesh skeleton now has %s; review ROOT_EXTRAS/TAIL_EXTRAS' % n)
        parents[n] = 'Scene_Root'
        rest[n] = ((0.0, 0.0, 0.0), IDENTITY)
    missing = [n for n in NOT_ANIMATED if n not in names]
    if missing or names[0] != 'Scene_Root':
        raise ValueError('mesh skeleton changed (missing %s); review the clip bone list' % missing)
    bones = [names[0]] + list(ROOT_EXTRAS) + [n for n in names[1:] if n not in NOT_ANIMATED] + list(TAIL_EXTRAS)
    return parents, rest, bones


def load_skeleton(addons_dir):
    """(parents, rest, bones) from the installed mesh skeleton. Raises FileNotFoundError when absent."""
    import os
    from tools.audit import pbo_config as pc
    path = os.path.join(addons_dir, SKELETON_PBO)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    data = pc.read_member(path, pc.read_pbo_index(path), SKELETON_MODEL, max_bytes=32 << 20)
    if data is None:
        raise FileNotFoundError(SKELETON_MODEL + ' missing from ' + SKELETON_PBO)
    return skeleton_from_xob(data)


def rest_pose(parents, rest, bones):
    """The mesh rest pose as a clip pose: rest transforms, pelvis turned to face +Z."""
    local = {n: rest[n] for n in bones}
    t, q = local['Pelvis']
    local['Pelvis'] = (qrot(FACING, t), qnorm(qmul(FACING, q)))
    return Pose(parents, local)


def load_reference(addons_dir):
    """Tests only: (parents, vanilla idle Anim). Raises FileNotFoundError when absent."""
    import os
    from tools.audit import pbo_config as pc
    clip_pbo = os.path.join(addons_dir, CLIP_PBO)
    ws_pbo = os.path.join(addons_dir, WORKSPACE_PBO)
    for p in (clip_pbo, ws_pbo):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
    clip = pc.read_member(clip_pbo, pc.read_pbo_index(clip_pbo), REFERENCE_CLIP, max_bytes=8 << 20)
    model = pc.read_member(ws_pbo, pc.read_pbo_index(ws_pbo), HIERARCHY_MODEL, max_bytes=32 << 20)
    if clip is None or model is None:
        raise FileNotFoundError('reference clip or preview model missing from the installed addons')
    parents = parse_xob_hierarchy(model)
    ref = anm.read(clip)
    for b in ref.bones:                 # helpers/IK bones absent from the preview model hang off the root
        parents.setdefault(b.name, 'Scene_Root' if b.name != 'Scene_Root' else None)
    return parents, ref


def pose_from_clip(parents, clip, frame=0):
    local = {}
    for b in clip.bones:
        t = _sample(b.t, frame, (0.0, 0.0, 0.0))
        q = _sample(b.q, frame, IDENTITY)
        local[b.name] = (t, qnorm(q))
    return Pose(parents, local)


def _sample(track, frame, default):
    if not track.values:
        return default
    best = 0
    for i, f in enumerate(track.frames):
        if f <= frame:
            best = i
    return tuple(track.values[best])
