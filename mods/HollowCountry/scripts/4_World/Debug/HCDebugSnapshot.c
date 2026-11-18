// W5 #122. Native scripts-1.30.164289 evidence:
// 1_Core/proto/EnScript.c:380,394,399,407,470 array Count/Find/Get/Insert/RemoveOrdered;
// :866,926 map Get/Insert; EnString.c:137,199,212 SubstringUtf8/Length/LengthUtf8.
// Layers/routes are serialized by JsonFileLoader (3_Game/tools/JsonFileLoader.c:85).
// The envelope's literal "map" key cannot be an Enforce field: map is a type.
// Registry: 16 contributors; each Describe gets 64 points and 8 routes,
// each route <=64 vertices. Snapshot totals <=1024 points/128 routes.
// No entities, discovery, provider claims or inventory writes in this API.
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

class HCDebugDocument
{
    int version = 1;
    int time;
    ref map<string, ref array<ref HCDebugPoint>> layers = new map<string, ref array<ref HCDebugPoint>>;
    ref array<ref HCDebugRoute> routes = new array<ref HCDebugRoute>;
}

class HCDebugSnapshot
{
    protected static ref array<ref HCDebugContributor> s_Contributors;
    protected ref array<ref HCDebugContributor> m_Contributors;
    protected ref HCDebugDocument m_Document;
    protected int m_Cursor;
    protected int m_PointCount;
    protected int m_ContributorPoints;
    protected int m_ContributorRoutes;
    protected bool m_Describing;

    static void HCRegister(HCDebugContributor contributor)
    {
        if (!contributor) { return; }
        if (!s_Contributors) { s_Contributors = new array<ref HCDebugContributor>; }
        if (s_Contributors.Find(contributor) >= 0) { return; }
        if (s_Contributors.Count() >= 16) { return; }
        s_Contributors.Insert(contributor);
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
        m_Contributors = new array<ref HCDebugContributor>;
        if (!s_Contributors) { return; }
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
        // All caller limits <=256; binary search needs at most 9 slices.
        int low = 0;
        int high = value.LengthUtf8();
        if (high > limit) { high = limit; }
        string clipped;
        for (int attempt = 0; attempt < 9; attempt++)
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
        if (!m_Describing || m_PointCount >= 1024 || m_ContributorPoints >= 64) { return; }
        if (layer == "" || id == "" || !HCPositionValid(pos)) { return; }
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
        m_PointCount++;
        m_ContributorPoints++;
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

    HCDebugDocument HCDocument() { return m_Document; }
    int HCPointCount() { return m_PointCount; }
    int HCRouteCount() { return m_Document.routes.Count(); }
}
