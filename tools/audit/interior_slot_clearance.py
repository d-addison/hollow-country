"""Interior template slot rules, taken from the world mesh audit (tools/audit/world_mesh_audit.py).

    python3 -B -m tools.audit.interior_slot_clearance build --census census.json ... --out <empty dir>

This is the entry point of the offline template generator (tools/package/interior_templates.py). The
generator cannot import the audit (it ships in the friend bundle, the audit does not), so the rules are
handed to it here. A candidate slot is refused when the audit would raise HOST_GEOMETRY_ENCROACHMENT,
DOOR_APRON_INTERSECTION, STAIR_PATH_INTERSECTION, PATH_LOD_INTERSECTION or PIECE_GEOMETRY_INTERSECTION
for it; the generator then tries its next wall cell, so a regenerated pack is audit-clean by construction.
Every test is the audit's own helper, called on the audit's own inputs; nothing is re-implemented here.
"""
import hashlib
import json
from pathlib import Path

from tools.audit import world_mesh_audit as audit
from tools.package import interior_templates as tpl
from tools.release.ship_inputs import ADDONS

REASONS = ("host_geometry", "door_apron", "stair_path", "path_lod", "piece_geometry")


class HostClearance:
    """clear(host, kind, position, yaw, placed) -> bool, refusals by reason, pin() for the pack identity."""

    def __init__(self, installed):
        self.installed = installed
        self.refusals = {}
        self._props, self._hosts = {}, {}

    def _prop(self, kind):
        if kind not in self._props:
            model = self.installed.model(kind)
            lod = None if model is None else audit.lod_for(model, audit.GEOMETRY)
            box = None if lod is None else audit.geometry(model)[0]
            if box is None:
                raise tpl.TemplateError("prop model or Geometry LOD unavailable for %s" % kind)
            self._props[kind] = (box, audit.convex_parts(model, lod))
        return self._props[kind]

    def _host(self, host):
        if host not in self._hosts:
            model = self.installed.model(host, host=True)
            box, triangles = audit.geometry(model) if model is not None else (None, [])
            if not box:
                raise tpl.TemplateError("host Geometry LOD unavailable for %s" % host)
            self._hosts[host] = (triangles, audit.doors(model)[0], audit.path_segments(model) or ())
        return self._hosts[host]

    @staticmethod
    def _row(host, kind, key, position, yaw):
        return audit.Placement("candidate", str(key), kind, tuple(position), (yaw, 0, 0), host=host)

    def _refuse(self, reason):
        self.refusals[reason] = self.refusals.get(reason, 0) + 1
        return False

    def clear(self, host, kind, position, yaw, placed):
        box, parts = self._prop(kind)
        triangles, door_rows, segments = self._host(host)
        row = self._row(host, kind, "candidate", position, yaw)
        placed_box = audit.placed_box(box, row)
        if any(audit.triangle_box(triangle, placed_box) for triangle in triangles):
            return self._refuse("host_geometry")
        if any(audit.door_intersects(placed_box, door) for _, door in door_rows):
            return self._refuse("door_apron")
        for reason, stair in (("stair_path", True), ("path_lod", False)):
            if any(audit.path_blocked(placed_box, segment) for segment in segments if segment[2] == stair):
                return self._refuse(reason)
        moved = None
        for index, other in enumerate(placed):
            other_row = self._row(host, other["Type"], index, other["Position"], other["Orientation"][0])
            other_box, other_parts = self._prop(other["Type"])
            if audit.overlaps(placed_box, audit.placed_box(other_box, other_row)):
                moved = moved or audit.place_parts(parts, row)
                if audit.pieces_penetration(moved, audit.place_parts(other_parts, other_row)):
                    return self._refuse("piece_geometry")
        return True

    def pin(self):
        """Identity of the rules: the audit thresholds and the code of both modules."""
        rules = {"policy": audit.POLICY,
                 "rules": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "audit": hashlib.sha256(Path(audit.__file__).read_bytes()).hexdigest()}
        return hashlib.sha256(json.dumps(rules, sort_keys=True).encode("ascii")).hexdigest()


def factory(args):
    addons = Path(args.addons) if args.addons else ADDONS
    if not addons.is_dir() or not any(addons.glob("*.pbo")):
        raise tpl.TemplateError("installed Addons not found; pass --addons")
    return HostClearance(audit.Installed(addons))


def main(argv=None):
    return tpl.main(argv, clearance_factory=factory)


if __name__ == "__main__":
    raise SystemExit(main())
