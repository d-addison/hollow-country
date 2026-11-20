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

class HCGroundSnap
{
    static ref HCGroundSnapStats Placed = new HCGroundSnapStats;

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
