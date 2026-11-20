// Native 1.30.164289: Object.ClippingInfo/GetCollisionBox/ModelToWorld;
// DayZPhysics.RaycastRVProxy (nearest contact, self ignored); Game.SurfaceRoadY.
class HCGroundSnapStats
{
    int Snapped;
    int AlreadyOk;
    int NoSupport;
    float MaxCorrection;

    void Summary(string source)
    {
        string line = "[HC Ground] source=" + source + " snapped=" + Snapped.ToString();
        line += " already_ok=" + AlreadyOk.ToString() + " no_support=" + NoSupport.ToString();
        line += " max_correction_m=" + MaxCorrection.ToString();
        Print("" + line);
    }
}

class HCGroundSnap
{
    static ref HCGroundSnapStats Placed = new HCGroundSnapStats;

    static bool Support(vector bottom, Object ignored, float drop, out vector contact, out bool terrain)
    {
        vector start = bottom + Vector(0, 0.25, 0);
        vector finish = bottom - Vector(0, drop, 0);
        RaycastRVParams query = new RaycastRVParams(start, finish, ignored);
        query.type = ObjIntersectGeom;
        query.flags = CollisionFlags.NEARESTCONTACT;
        array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
        if (!DayZPhysics.RaycastRVProxy(query, hits) || hits.Count() == 0) { return false; }
        RaycastRVResult hit = hits[0];
        contact = hit.pos;
        terrain = !hit.obj && !hit.parent;
        return contact[1] <= start[1] && contact[1] >= finish[1];
    }

    // Eight transformed corners account for orientation and scale, including tilted props.
    static bool Bounds(Object placedObject, out vector lower, out vector upper, out float bottomY)
    {
        vector box[2];
        bool valid = placedObject.GetCollisionBox(box);
        if (!valid) { valid = placedObject.ClippingInfo(box) > 0; }
        lower = box[0];
        upper = box[1];
        bottomY = placedObject.GetPosition()[1];
        if (!valid) { return false; }
        bottomY = 1000000;
        for (int corner = 0; corner < 8; corner++)
        {
            vector cornerPoint = lower;
            if (corner & 1) { cornerPoint[0] = upper[0]; }
            if (corner & 2) { cornerPoint[1] = upper[1]; }
            if (corner & 4) { cornerPoint[2] = upper[2]; }
            vector world = placedObject.ModelToWorld(cornerPoint);
            if (world[1] < bottomY) { bottomY = world[1]; }
        }
        return true;
    }

    static bool Snap(Object placedObject, float drop = 3, float tolerance = 0.01, HCGroundSnapStats stats = null)
    {
        if (!GetGame() || !GetGame().IsServer() || !placedObject || placedObject.IsPendingDeletion()) { return false; }
        if (!stats) { stats = Placed; }
        vector lower;
        vector upper;
        float bottomY;
        bool bounds = Bounds(placedObject, lower, upper, bottomY);
        vector origin = placedObject.GetPosition();
        vector bottom = Vector(origin[0], bottomY, origin[2]);
        vector contact;
        bool terrain;
        if (!Support(bottom, placedObject, drop, contact, terrain)) { stats.NoSupport++; return false; }
        float targetY = contact[1];
        string kind = placedObject.GetType();
        // Only terrain-supported structures embed foundations. Never replace a floor hit
        // with terrain below it. Four footprint samples, no world object enumeration.
        if (terrain && bounds && (kind.IndexOf("Land_") == 0 || kind.IndexOf("StaticObj_") == 0))
        {
            for (int corner = 0; corner < 4; corner++)
            {
                vector cornerPoint = lower;
                if (corner & 1) { cornerPoint[0] = upper[0]; }
                if (corner & 2) { cornerPoint[2] = upper[2]; }
                vector world = placedObject.ModelToWorld(cornerPoint);
                float roadY = GetGame().SurfaceRoadY(world[0], world[2]);
                if (roadY < targetY) { targetY = roadY; }
            }
        }
        float correction = targetY - bottomY;
        // Footprint embedding must obey the same bounded correction as the ray.
        if (correction < -drop || correction > 0.25) { stats.NoSupport++; return false; }
        if (correction >= 0 && correction <= 0.005) { stats.AlreadyOk++; return true; }
        if (correction <= 0 && -correction <= tolerance) { stats.AlreadyOk++; return true; }
        origin[1] = origin[1] + correction;
        placedObject.SetPosition(origin);
        stats.Snapped++;
        float distance = Math.AbsFloat(correction);
        if (distance > stats.MaxCorrection) { stats.MaxCorrection = distance; }
        return true;
    }
}
