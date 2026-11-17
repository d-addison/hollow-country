"""Synthetic closed navmesh rectangles; no filtered mesh inside the walled room."""
from tests.unit import test_interior_sampler as model


def room_without_filtered_mesh():
    building = model.storey_building()
    class ClosedZones(model.NavMesh):
        def zone_at(self, world, radius):
            local = self.building.CoordToLocal(world)
            found = [z for z in self.zones if z.x0 <= local[0] <= z.x1
                     and z.z0 <= local[2] <= z.z1 and abs(local[1] - z.y) <= radius]
            return min(found, key=lambda z: abs(local[1] - z.y)) if found else None
    nav = ClosedZones(building, [model.Zone('out', -30, -5, -30, 30, 0.0),
                                 model.Zone('g', -5, 7, -4, 0.5, 0.0)], links=[('out', 'g')])
    floor = building.to_world((-3.5, 0.0, 1.5))
    # Closest point on the connected closed rectangle is its z=0.5 boundary.
    nearest = building.to_world((-3.5, 0.0, 0.5))
    return building, nav, floor, nearest
