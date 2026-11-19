// W5 #122. Native scripts-1.30.164289 evidence:
// 1_Core/proto/EnScript.c:380,394,399,407,470 array Count/Find/Get/Insert/RemoveOrdered;
// :866,926 map Get/Insert; EnString.c:137,199,212 SubstringUtf8/Length/LengthUtf8.
// Layers/routes are serialized by JsonFileLoader (3_Game/tools/JsonFileLoader.c:85).
// The envelope's literal "map" key cannot be an Enforce field: map is a type.
// Registry: 16 contributors; each Describe gets 64 points and 8 routes,
// each route <=64 vertices. Snapshot totals <=1024 points/128 routes.
// No entities, discovery, provider claims or inventory writes in this API.
// w27-debugmap: the 1024-point wire cap is split. Shared contributors (ai-units,
// players, ...) may fill MAX_POINTS - DEBUG_LAYER_POINTS; the hardened layers
// below (camps) draw on their own DEBUG_LAYER_POINTS share via HCAddLayerPoint,
// so neither side squeezes the other and the total never exceeds the wire cap.
// Each hardened layer also reports total/shown/truncated through HCNoteLayer.
// w28-debugmap #193: the lead-ledger and scenes layers read the new read-only
// owner getters (HCLeadModule.HCDebugLead*, HCScenesModule.HCDebugLease*) and draw
// on the same hardened share: camps 24 + lead-ledger 56 + scenes 8 = 88.
class HCDebugContributor
{
    void HCDescribe(HCDebugSnapshot snapshot) {}
}

class HCDebugPoint
{
    string id;
    float x;
    float z;
    string label;
    string detail;
}

class HCDebugRoute
{
    string layer;
    string id;
    string label;
    ref array<ref array<float>> points = new array<ref array<float>>;
}

class HCDebugLayerStat
{
    string layer;
    int total;
    int shown;
    int truncated;
}

class HCDebugDocument
{
    int version = 1;
    int time;
    ref map<string, ref array<ref HCDebugPoint>> layers = new map<string, ref array<ref HCDebugPoint>>;
    ref array<ref HCDebugRoute> routes = new array<ref HCDebugRoute>;
    ref array<ref HCDebugLayerStat> layerStats = new array<ref HCDebugLayerStat>;
    ref array<string> operational = new array<string>;
    int contributors;
    int truncated;
    int operationalTruncated;
}

class HCDebugSnapshot
{
    static const int MAX_POINTS = 1024;
    static const int MAX_CONTRIBUTOR_POINTS = 64;
    // Own share of the wire cap for hardened layers; carved out of MAX_POINTS.
    static const int DEBUG_LAYER_POINTS = 88;
    // Camps layer: one row per holdout; mirrors the holdouts layer bound.
    static const int CAMP_LAYER_CAP = 24;
    // Lead ledger rows (store ceiling is 64) and scene leases (owner lease cap is 2).
    static const int LEAD_LAYER_CAP = 56;
    static const int SCENE_LAYER_CAP = 8;
    static const int MAX_LAYER_STATS = 16;
    protected static ref array<ref HCDebugContributor> s_Contributors;
    protected ref array<ref HCDebugContributor> m_Contributors;
    protected ref HCDebugDocument m_Document;
    protected int m_Cursor;
    protected int m_PointCount;
    protected int m_LayerPoints;
    protected int m_ContributorPoints;
    protected int m_ContributorRoutes;
    protected bool m_Describing;
    protected static int s_RegistrationRefusals;

    static bool HCRegister(HCDebugContributor contributor)
    {
        if (!contributor) { return false; }
        if (!s_Contributors) { s_Contributors = new array<ref HCDebugContributor>; }
        if (s_Contributors.Find(contributor) >= 0) { return true; }
        if (s_Contributors.Count() >= 16)
        {
            if (s_RegistrationRefusals < 1000000) { s_RegistrationRefusals++; }
            return false;
        }
        s_Contributors.Insert(contributor);
        return true;
    }

    // HCServer starts a new operational lifecycle before module registration.
    static void HCResetRegistrationRefusals()
    {
        s_RegistrationRefusals = 0;
    }

    static int HCContributorCount()
    {
        if (!s_Contributors) { return 0; }
        return s_Contributors.Count();
    }

    static void HCUnregister(HCDebugContributor contributor)
    {
        if (!s_Contributors) { return; }
        int index = s_Contributors.Find(contributor);
        if (index >= 0) { s_Contributors.RemoveOrdered(index); }
        if (s_Contributors.Count() == 0) { s_Contributors = null; }
    }

    void HCDebugSnapshot(int worldTime)
    {
        m_Document = new HCDebugDocument;
        m_Document.time = worldTime;
        m_Document.truncated = s_RegistrationRefusals;
        m_Contributors = new array<ref HCDebugContributor>;
        if (!s_Contributors) { return; }
        m_Document.contributors = s_Contributors.Count();
        for (int copyIndex = 0; copyIndex < s_Contributors.Count(); copyIndex++)
        {
            m_Contributors.Insert(s_Contributors[copyIndex]);
        }
    }

    // Exactly one registered Describe per call, with a cursor across core ticks.
    // Return true after the final contributor. Unregistered rows are never called.
    bool HCCaptureNext()
    {
        if (m_Cursor >= m_Contributors.Count()) { return true; }
        HCDebugContributor contributor = m_Contributors[m_Cursor];
        m_Cursor++;
        m_ContributorPoints = 0;
        m_ContributorRoutes = 0;
        if (s_Contributors && s_Contributors.Find(contributor) >= 0)
        {
            m_Describing = true;
            contributor.HCDescribe(this);
            m_Describing = false;
        }
        return m_Cursor >= m_Contributors.Count();
    }

    static bool HCPositionValid(vector pos)
    {
        bool validX = pos[0] >= 0 && pos[0] <= 15360;
        bool validZ = pos[2] >= 0 && pos[2] <= 15360;
        return validX && validZ;
    }

    static string HCText(string value, int limit)
    {
        if (value.Length() <= limit) { return value; }
        // Preserve complete UTF8 characters while enforcing a BYTE bound.
        // All caller limits <=768; binary search needs at most 11 slices.
        int low = 0;
        int high = value.LengthUtf8();
        if (high > limit) { high = limit; }
        string clipped;
        for (int attempt = 0; attempt < 11; attempt++)
        {
            if (low > high) { break; }
            int middle = (low + high) / 2;
            string candidate = value.SubstringUtf8(0, middle);
            if (candidate.Length() <= limit)
            {
                clipped = candidate;
                low = middle + 1;
            }
            else
            {
                high = middle - 1;
            }
        }
        return clipped;
    }

    void AddPoint(string layer, string id, vector pos, string label, string detail)
    {
        int sharedCap = HCDebugSnapshot.MAX_POINTS - HCDebugSnapshot.DEBUG_LAYER_POINTS;
        if (!m_Describing || m_PointCount >= sharedCap || m_ContributorPoints >= HCDebugSnapshot.MAX_CONTRIBUTOR_POINTS) { return; }
        if (layer == "" || id == "" || !HCPositionValid(pos)) { return; }
        HCInsertPoint(layer, id, pos, label, detail);
        m_PointCount++;
        m_ContributorPoints++;
    }

    // Hardened layers: own share, so the shared pool above is never squeezed.
    // Returns true only when the row was kept (callers report shown vs total).
    bool HCAddLayerPoint(string layer, string id, vector pos, string label, string detail)
    {
        if (!m_Describing || m_LayerPoints >= HCDebugSnapshot.DEBUG_LAYER_POINTS) { return false; }
        if (m_ContributorPoints >= HCDebugSnapshot.MAX_CONTRIBUTOR_POINTS) { return false; }
        if (layer == "" || id == "" || !HCPositionValid(pos)) { return false; }
        HCInsertPoint(layer, id, pos, label, detail);
        m_LayerPoints++;
        m_ContributorPoints++;
        return true;
    }

    // One count/truncated row per hardened layer per capture (bounded).
    void HCNoteLayer(string layer, int total, int shown)
    {
        if (!m_Describing || m_Document.layerStats.Count() >= HCDebugSnapshot.MAX_LAYER_STATS) { return; }
        HCDebugLayerStat stat = new HCDebugLayerStat;
        stat.layer = HCText(layer, 48);
        stat.total = total;
        stat.shown = shown;
        stat.truncated = 0;
        if (shown < total) { stat.truncated = 1; }
        m_Document.layerStats.Insert(stat);
    }

    protected void HCInsertPoint(string layer, string id, vector pos, string label, string detail)
    {
        string layerName = HCText(layer, 48);
        array<ref HCDebugPoint> rows = m_Document.layers.Get(layerName);
        if (!rows)
        {
            rows = new array<ref HCDebugPoint>;
            m_Document.layers.Insert(layerName, rows);
        }
        HCDebugPoint point = new HCDebugPoint;
        point.id = HCText(id, 96);
        point.x = pos[0];
        point.z = pos[2];
        point.label = HCText(label, 128);
        point.detail = HCText(detail, 256);
        rows.Insert(point);
    }

    void AddRoute(string layer, string id, array<vector> points, string label)
    {
        if (!m_Describing || m_Document.routes.Count() >= 128 || m_ContributorRoutes >= 8) { return; }
        if (!points || layer == "" || id == "") { return; }
        if (points.Count() < 2 || points.Count() > 64) { return; }
        HCDebugRoute route = new HCDebugRoute;
        route.layer = HCText(layer, 48);
        route.id = HCText(id, 96);
        route.label = HCText(label, 128);
        for (int vertexIndex = 0; vertexIndex < points.Count(); vertexIndex++)
        {
            vector pos = points[vertexIndex];
            if (!HCPositionValid(pos)) { return; }
            array<float> pair = new array<float>;
            pair.Insert(pos[0]);
            pair.Insert(pos[2]);
            route.points.Insert(pair);
        }
        m_Document.routes.Insert(route);
        m_ContributorRoutes++;
    }

    // HC-25: one aggregate contributor, cached text only, no map coordinates.
    void HCAddOperational(string line)
    {
        if (!m_Describing) { return; }
        if (m_Document.operational.Count() >= 64)
        {
            m_Document.operationalTruncated++;
            return;
        }
        if (line.Length() > 768) { m_Document.operationalTruncated++; }
        m_Document.operational.Insert(HCText(line, 768));
    }

    HCDebugDocument HCDocument() { return m_Document; }
    int HCPointCount() { return m_PointCount + m_LayerPoints; }
    int HCRouteCount() { return m_Document.routes.Count(); }
}

// w27-debugmap: read-only Camps layer. Replaces the plain holdouts contributor
// in its registry slot (the registry cap stays 16). w28-debugmap #193: ONE
// HCHoldouts.Snapshot per row per capture (each is a JSON round trip) feeds both
// the existing `holdouts` layer (routine/occupants detail, shared pool) and the
// reduced `camps` layer (id/position/ledger state only, own share). The overlap
// is intentional: `camps` is the privacy-reduced operator view of the same rows.
// No player ids or names, no entity search. A ledger state is not a body claim.
class HCDebugCampSitesContributor : HCDebugHoldoutsContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts) { return; }
        int total = holdouts.Count();
        int work = total;
        if (work > HCDebugSnapshot.CAMP_LAYER_CAP) { work = HCDebugSnapshot.CAMP_LAYER_CAP; }
        int shown = 0;
        for (int index = 0; index < work; index++)
        {
            HCWorldHoldout row = holdouts.Snapshot(index);
            if (!row) { continue; }
            string holdoutDetail = row.State + " / " + row.Routine + " occupants=" + row.Occupants.ToString();
            snapshot.AddPoint("holdouts", row.Id, row.HousePos, row.PlaceId, holdoutDetail);
            string detail = "state=" + row.State + "; ledger state, not a body-presence claim";
            if (snapshot.HCAddLayerPoint("camps", row.Id, row.HousePos, row.PlaceId, detail)) { shown++; }
        }
        snapshot.HCNoteLayer("camps", total, shown);
    }
}

// w28-debugmap #193: read-only lead ledger layer (`lead-ledger`; the older `leads`
// layer shows only what online recipients received). Place-level rows from the
// owner's HCDebugLeadCount/HCDebugLead: kind and expiry only, no group id, no live
// position (targets are authored named places). Bounded by LEAD_LAYER_CAP.
class HCDebugLeadLedgerContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCLeadModule leads = HCLeadModule.Get();
        if (!leads) { return; }
        int total = leads.HCDebugLeadCount();
        int work = total;
        if (work > HCDebugSnapshot.LEAD_LAYER_CAP) { work = HCDebugSnapshot.LEAD_LAYER_CAP; }
        int shown = 0;
        for (int index = 0; index < work; index++)
        {
            HCWorldLead lead = leads.HCDebugLead(index);
            if (!lead) { continue; }
            HCWorldPlace place = HCLeadPolicy.Place(lead.TargetPlaceId);
            if (!place) { continue; }
            string detail = "kind=" + lead.Kind + "; expires=" + lead.Expires.ToString() + "; ledger row at place level; group id withheld";
            if (snapshot.HCAddLayerPoint("lead-ledger", lead.Id, place.Position, place.Name, detail)) { shown++; }
        }
        snapshot.HCNoteLayer("lead-ledger", total, shown);
    }
}

// w28-debugmap #193: read-only Scenes layer, one row per owned lease anchor from
// HCScenesModule.HCDebugLease. Lease/ledger state only: not an entity-presence
// claim, no object handles. Bounded by SCENE_LAYER_CAP.
class HCDebugScenesContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCScenesModule scenes = HCScenesModule.HCDebugGet();
        if (!scenes) { return; }
        int total = scenes.HCDebugLeaseCount();
        int work = total;
        if (work > HCDebugSnapshot.SCENE_LAYER_CAP) { work = HCDebugSnapshot.SCENE_LAYER_CAP; }
        int shown = 0;
        for (int index = 0; index < work; index++)
        {
            HCDebugSceneLeaseRow row = scenes.HCDebugLease(index);
            if (!row) { continue; }
            string state = "placing";
            if (row.Placed) { state = "placed"; }
            if (row.Closing) { state = "closing"; }
            string detail = "stage=" + row.Stage.ToString() + "; state=" + state + "; due=" + row.DueAt.ToString() + "; expires=" + row.ExpiresAt.ToString() + "; lease anchor, not an entity-presence claim";
            if (snapshot.HCAddLayerPoint("scenes", row.ChainId, row.Anchor, row.ChainId, detail)) { shown++; }
        }
        snapshot.HCNoteLayer("scenes", total, shown);
    }
}
