// Native 1.30.164289: Object.ClippingInfo/GetCollisionBox/ModelToWorld;
// DayZPhysics.RaycastRVProxy; EnDebug.c: NEARESTCONTACT returns only the nearest
// contact (not an ordering guarantee for an unsorted multi-hit query). Self ignored.
class HCGroundSnapStats
{
    int Snapped;
    int AlreadyOk;
    int NoSupport;
    int NoHit;
    int ContactAboveStart;
    int ContactBelowFinish;
    int CorrectionOutOfRange;
    int ReprobeLifted;
    float MaxCorrection;
    protected static int s_NoSupportSamples;

    void RecordNoSupport(Object placedObject, string reason)
    {
        if (reason == "no_hit") { NoHit++; }
        else if (reason == "contact_above_start") { ContactAboveStart++; }
        else if (reason == "contact_below_finish") { ContactBelowFinish++; }
        else { CorrectionOutOfRange++; }
        NoSupport = NoHit + ContactAboveStart + ContactBelowFinish + CorrectionOutOfRange;
        // Eight items total across CE, script placements and object-spawner stats.
        if (s_NoSupportSamples < 8)
        {
            s_NoSupportSamples++;
            Print("[HC Ground] no_support_sample type=" + placedObject.GetType() + " reason=" + reason + " runtime=PENDING");
        }
    }

    void Summary(string source)
    {
        string line = "[HC Ground] source=" + source + " snapped=" + Snapped.ToString();
        line += " already_ok=" + AlreadyOk.ToString() + " no_support=" + NoSupport.ToString();
        line += " no_hit=" + NoHit.ToString() + " contact_above_start=" + ContactAboveStart.ToString();
        line += " contact_below_finish=" + ContactBelowFinish.ToString() + " correction_out_of_range=" + CorrectionOutOfRange.ToString();
        line += " reprobe_lifted=" + ReprobeLifted.ToString();
        line += " max_correction_m=" + MaxCorrection.ToString();
        Print("" + line);
    }
}

// Sidecar objects/<layer>.ground.json, index-aligned with the spawner rows (tools.package.map_overlay):
// pivot = pivot height above the lowest footprint ground, embed = depth the model carries below its
// pivot, loot = 1 when the piece carries CE loot.
class HCGroundRowJson
{
    float pivot;
    float embed;
    int loot;
}

class HCGroundLayerJson
{
    ref array<ref HCGroundRowJson> Ground;
}

class HCGroundPlaceStats
{
    int Layers;
    int Placed;
    int Ok;
    int Resnapped;
    int Refused;
    int RefusedKept;
    int Legacy;
    float MaxCorrection;
    float MaxSpread;

    // ok + resnapped + refused = placed. refused_kept is the part of refused that carries CE loot and
    // stays (a missing building would leave its loot in the air); legacy counts props placed by the
    // plain snap because their layer has no ground sidecar.
    void Summary(string source)
    {
        string line = "[HC Ground] placement source=" + source + " layers=" + Layers.ToString();
        line += " placed=" + Placed.ToString() + " ok=" + Ok.ToString() + " resnapped=" + Resnapped.ToString();
        line += " refused=" + Refused.ToString() + " refused_kept=" + RefusedKept.ToString();
        line += " legacy=" + Legacy.ToString() + " max_correction_m=" + MaxCorrection.ToString();
        line += " max_spread_m=" + MaxSpread.ToString();
        Print("" + line);
    }
}

// Footprints of placed props that carry CE loot, with the height shift the placer applied. CE creates the
// loot at the authored group height, so an item inside a footprint moves by the same shift as its building.
class HCGroundPlaced
{
    static const float CELL = 64;
    protected static ref array<float> s_X = new array<float>;
    protected static ref array<float> s_Z = new array<float>;
    protected static ref array<float> s_Radius = new array<float>;
    protected static ref array<float> s_Y = new array<float>;
    protected static ref array<float> s_Shift = new array<float>;
    protected static ref map<int, ref array<int>> s_Cells = new map<int, ref array<int>>;

    static int CellKey(float x, float z)
    {
        int cellX = Math.Floor(x / CELL);
        int cellZ = Math.Floor(z / CELL);
        return cellX * 4096 + cellZ;
    }

    protected static int s_Dead;

    // Live footprints (entries forgotten for deleted pieces are not counted).
    static int Count()
    {
        return s_X.Count() - s_Dead;
    }

    // A piece that was deleted (a refused site's rollback) leaves no footprint: its index leaves the 64 m cell
    // list (bounded by that list) and its slot is neutralised, so CE loot is never shifted for a building that is
    // gone. Placement positions are exact floats, so the match tolerance is tight. Returns the entries forgotten.
    static int HCForget(vector pos)
    {
        array<int> cell = s_Cells.Get(CellKey(pos[0], pos[2]));
        if (!cell) { return 0; }
        int forgotten = 0;
        int slot = cell.Count() - 1;
        while (slot >= 0)
        {
            int index = cell[slot];
            if (Math.AbsFloat(s_X[index] - pos[0]) <= 0.02 && Math.AbsFloat(s_Z[index] - pos[2]) <= 0.02)
            {
                s_Radius.Set(index, 0.0001);
                s_Shift.Set(index, 0);
                cell.RemoveOrdered(slot);
                s_Dead++;
                forgotten++;
            }
            slot--;
        }
        return forgotten;
    }

    static void Add(vector pos, float radius, float shift)
    {
        if (radius > CELL * 0.5) { radius = CELL * 0.5; }
        int index = s_X.Count();
        s_X.Insert(pos[0]);
        s_Z.Insert(pos[2]);
        s_Radius.Insert(radius);
        s_Y.Insert(pos[1]);
        s_Shift.Insert(shift);
        int key = CellKey(pos[0], pos[2]);
        array<int> cell = s_Cells.Get(key);
        if (!cell)
        {
            cell = new array<int>;
            s_Cells.Set(key, cell);
        }
        cell.Insert(index);
    }

    // True inside a registered footprint; shift is the registered height shift when the position is
    // within the building's own height band (authored group height -1 m .. +15 m), otherwise 0.
    static bool Find(vector pos, out float shift)
    {
        shift = 0;
        bool found = false;
        float best = 1000000;
        int baseX = Math.Floor(pos[0] / CELL);
        int baseZ = Math.Floor(pos[2] / CELL);
        for (int dx = -1; dx <= 1; dx++)
        {
            for (int dz = -1; dz <= 1; dz++)
            {
                array<int> cell = s_Cells.Get((baseX + dx) * 4096 + baseZ + dz);
                if (!cell) { continue; }
                for (int slot = 0; slot < cell.Count(); slot++)
                {
                    int index = cell[slot];
                    float offX = pos[0] - s_X[index];
                    float offZ = pos[2] - s_Z[index];
                    float ratio = (offX * offX + offZ * offZ) / (s_Radius[index] * s_Radius[index]);
                    if (ratio > 1 || ratio >= best) { continue; }
                    found = true;
                    best = ratio;
                    shift = 0;
                    float above = pos[1] - s_Y[index];
                    if (above >= -1.0 && above <= 15.0) { shift = s_Shift[index]; }
                }
            }
        }
        return found;
    }
}

class HCGroundSnap
{
    static ref HCGroundSnapStats Placed = new HCGroundSnapStats;

    static const int PLACE_OK = 0;
    static const int PLACE_RESNAPPED = 1;
    static const int PLACE_REFUSED = 2;
    static const int PLACE_KEPT = 3;
    static const float PLACE_MAX_CORRECTION = 25;
    static const float PLACE_TOLERANCE = 0.02;

    // Slope the footprint may span before the prop is refused: the authored embed hides it on the
    // uphill side, plus a size-scaled allowance. The lowest footprint ground is always the contact.
    static float SlopeAllowance(float extent)
    {
        if (extent <= 6) { return 0.5; }
        if (extent <= 14) { return 0.8; }
        return 1.2;
    }

    // Terrain under the footprint: 3x3 points over the collision box plus the pivot, no world objects.
    static void Footprint(Object placedObject, out float lowGround, out float highGround, out float extent, out float radius)
    {
        vector lower;
        vector upper;
        float bottomY;
        vector origin = placedObject.GetPosition();
        lowGround = GetGame().SurfaceRoadY(origin[0], origin[2]);
        highGround = lowGround;
        extent = 0;
        radius = 3;
        if (!Bounds(placedObject, lower, upper, bottomY)) { return; }
        float sizeX = upper[0] - lower[0];
        float sizeZ = upper[2] - lower[2];
        extent = Math.Max(sizeX, sizeZ);
        radius = Math.Sqrt(sizeX * sizeX + sizeZ * sizeZ) * 0.5 + 1.0;
        vector modelPoint;
        vector worldPoint;
        float groundY;
        for (int gridX = 0; gridX < 3; gridX++)
        {
            for (int gridZ = 0; gridZ < 3; gridZ++)
            {
                modelPoint = Vector(lower[0] + sizeX * gridX * 0.5, 0, lower[2] + sizeZ * gridZ * 0.5);
                worldPoint = placedObject.ModelToWorld(modelPoint);
                groundY = GetGame().SurfaceRoadY(worldPoint[0], worldPoint[2]);
                if (groundY < lowGround) { lowGround = groundY; }
                if (groundY > highGround) { highGround = groundY; }
            }
        }
    }

    // Spawner prop: the pivot rests pivotRel above the lowest ground under the footprint, so nothing
    // hovers and the uphill side sinks by at most the slope (never beyond SlopeAllowance + embed).
    // Beyond that, or when the correction is out of range, a prop without CE loot is refused (deleted);
    // one with loot stays (PLACE_KEPT) at the lowest contact, because its loot is created at the authored group.
    static int Place(Object placedObject, float pivotRel, float embed, bool carriesLoot, HCGroundPlaceStats stats)
    {
        float lowGround;
        float highGround;
        float extent;
        float radius;
        vector origin = placedObject.GetPosition();
        Footprint(placedObject, lowGround, highGround, extent, radius);
        float spread = highGround - lowGround;
        if (spread > stats.MaxSpread) { stats.MaxSpread = spread; }
        float targetY = lowGround + pivotRel;
        float correction = targetY - origin[1];
        stats.Placed++;
        bool inRange = Math.AbsFloat(correction) <= PLACE_MAX_CORRECTION;
        bool kept = false;
        if (spread > SlopeAllowance(extent) + embed || !inRange)
        {
            stats.Refused++;
            if (!carriesLoot)
            {
                GetGame().ObjectDelete(placedObject);
                return PLACE_REFUSED;
            }
            stats.RefusedKept++;
            if (!inRange)
            {
                HCGroundPlaced.Add(origin, radius, 0);
                return PLACE_KEPT;
            }
            kept = true;
        }
        else if (Math.AbsFloat(correction) <= PLACE_TOLERANCE)
        {
            stats.Ok++;
            correction = 0;
        }
        else
        {
            stats.Resnapped++;
        }
        if (correction != 0)
        {
            placedObject.SetPosition(Vector(origin[0], targetY, origin[2]));
            float distance = Math.AbsFloat(correction);
            if (distance > stats.MaxCorrection) { stats.MaxCorrection = distance; }
        }
        if (carriesLoot) { HCGroundPlaced.Add(origin, radius, correction); }
        if (kept) { return PLACE_KEPT; }
        if (correction == 0) { return PLACE_OK; }
        return PLACE_RESNAPPED;
    }

    // Drop-only settle for an item that may hang in the air: finds the first surface below within
    // `drop` and rests the bottom on it. Never lifts, never moves an item that has no surface below.
    static bool Settle(Object item, float drop, float tolerance)
    {
        if (!GetGame() || !GetGame().IsServer() || !item || item.IsPendingDeletion()) { return false; }
        vector lower;
        vector upper;
        float bottomY;
        if (!Bounds(item, lower, upper, bottomY)) { return false; }
        vector origin = item.GetPosition();
        vector contact;
        bool terrain;
        string reason;
        if (!Probe(Vector(origin[0], bottomY, origin[2]), item, drop, 0.25, contact, terrain, reason)) { return false; }
        float correction = contact[1] - bottomY;
        if (correction >= -tolerance) { return false; }
        origin[1] = origin[1] + correction;
        item.SetPosition(origin);
        return true;
    }

    static bool Support(vector bottom, Object ignored, float drop, out vector contact, out bool terrain)
    {
        string reason;
        return Probe(bottom, ignored, drop, 0.25, contact, terrain, reason);
    }

    static bool Probe(vector bottom, Object ignored, float drop, float rise, out vector contact, out bool terrain, out string reason)
    {
        reason = "";
        terrain = false;
        vector start = bottom + Vector(0, rise, 0);
        vector finish = bottom - Vector(0, drop, 0);
        RaycastRVParams query = new RaycastRVParams(start, finish, ignored);
        query.type = ObjIntersectGeom;
        query.flags = CollisionFlags.NEARESTCONTACT;
        array<ref RaycastRVResult> hits = new array<ref RaycastRVResult>;
        if (!DayZPhysics.RaycastRVProxy(query, hits) || hits.Count() == 0) { reason = "no_hit"; return false; }
        RaycastRVResult hit = hits[0];
        contact = hit.pos;
        terrain = !hit.obj && !hit.parent;
        if (contact[1] > start[1]) { reason = "contact_above_start"; return false; }
        if (contact[1] < finish[1]) { reason = "contact_below_finish"; return false; }
        return true;
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
        string reason;
        bool reprobed;
        if (!Probe(bottom, placedObject, drop, 0.25, contact, terrain, reason))
        {
            if (reason != "no_hit" && reason != "contact_above_start")
            {
                stats.RecordNoSupport(placedObject, reason);
                return false;
            }
            // A buried bottom gets exactly one higher start, with the caller's
            // original finish. Never retry a valid floor hit against lower terrain.
            vector retryContact;
            bool retryTerrain;
            string retryReason;
            if (!Probe(bottom, placedObject, drop, 1.0, retryContact, retryTerrain, retryReason))
            {
                stats.RecordNoSupport(placedObject, retryReason);
                return false;
            }
            // Even an above-start floor contact must not be replaced by terrain.
            if (reason == "contact_above_start" && !terrain && retryTerrain)
            {
                stats.RecordNoSupport(placedObject, reason);
                return false;
            }
            contact = retryContact;
            terrain = retryTerrain;
            reprobed = true;
        }
        // Check the actual contact before any foundation footprint embedding.
        // A low model corner must not allow a shelf/roof over 1 m above the origin.
        if (contact[1] > origin[1] + 1.0)
        {
            stats.RecordNoSupport(placedObject, "correction_out_of_range");
            return false;
        }
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
        float maxRise = 0.25;
        if (reprobed) { maxRise = 1.0; }
        if (correction < -drop || correction > maxRise)
        {
            stats.RecordNoSupport(placedObject, "correction_out_of_range");
            return false;
        }
        if (correction >= 0 && correction <= 0.005) { stats.AlreadyOk++; return true; }
        if (correction <= 0 && -correction <= tolerance) { stats.AlreadyOk++; return true; }
        origin[1] = origin[1] + correction;
        placedObject.SetPosition(origin);
        stats.Snapped++;
        if (reprobed && correction > 0) { stats.ReprobeLifted++; }
        float distance = Math.AbsFloat(correction);
        if (distance > stats.MaxCorrection) { stats.MaxCorrection = distance; }
        return true;
    }
}
