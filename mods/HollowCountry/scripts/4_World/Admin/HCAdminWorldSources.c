// Read-only admin capture extends the shared contributor path without changing
// debug exports or their caps. Native references: HCDebugSnapshot.c, plus
// scripts-1.30.164289/1_Core/proto/EnScript.c:380/399/407 array operations.
class HCAdminWorldCapture : HCDebugSnapshot
{
    ref array<ref HCAdminMark> Rows = new array<ref HCAdminMark>;
    int Dropped;
    bool CatalogReserved;
    int CatalogReserveTicks;
    int PeakPutTicks;
    void HCReserveCatalog()
    {
        int start = TickCount(0);
        // Native scripts-1.30.164289/1_Core/proto/EnScript.c:482 Reserve;
        // EnSystem.c:106 TickCount. Capacity only: no null rows on the wire.
        Rows.Reserve(Math.Min(HCAdminWorldCatalog.COUNT, Limit));
        CatalogReserveTicks = TickCount(start);
        CatalogReserved = true;
    }
    int Limit = 8192;
    protected ref map<string, bool> m_AdminLayers = new map<string, bool>;
    void HCAdminWorldCapture(int worldTime) {}
    int LayerCount() { return m_AdminLayers.Count(); }
    void Put(string layer, vector position, string label, string detail)
    {
        int start = TickCount(0);
        if (!HCPositionValid(position)) { return; }
        if (Rows.Count() >= Limit) { Dropped++; return; }
        string layerName = HCText(layer, 48);
        if (!m_AdminLayers.Contains(layerName) && m_AdminLayers.Count() >= 48) { Dropped++; return; }
        HCAdminMark mark = new HCAdminMark;
        mark.Layer = layerName;
        mark.Position = position;
        mark.Label = HCText(label, 128);
        mark.Detail = HCText(detail, 256);
        Rows.Insert(mark);
        m_AdminLayers.Set(mark.Layer, true);
        int cost = TickCount(start);
        if (cost > PeakPutTicks) { PeakPutTicks = cost; }
    }
    override void AddPoint(string layer, string id, vector pos, string label, string detail)
    {
        // The M-map operator view deliberately has no player roster layer.
        if (layer == "players" || layer == "ai-units") { return; }
        Put(layer, pos, label, detail);
    }
    override bool HCAddLayerPoint(string layer, string id, vector pos, string label, string detail)
    {
        Put(layer, pos, label, detail);
        return Rows.Count() < Limit;
    }
    override void AddRoute(string layer, string id, array<vector> points, string label)
    {
        // Anchor only: straight debug objective lines are not surveyed routes.
        if (points && points.Count() > 0) { Put(layer, points[0], label, "Route anchor; see owner runtime for route state"); }
    }
}

// Native animal cohort is already maintained by Ecology. This small read-only
// accessor lives in Admin scope; no duplicate hooks/registry or gameplay writes.
modded class HCEcologyRuntime
{
    int HCAdminAnimalCount() { if (!m_Running) { return 0; } return m_Actors.Count(); }
    AnimalBase HCAdminAnimal(int index)
    {
        if (!m_Running || index < 0 || index >= m_Actors.Count()) { return null; }
        HCEcologyLiveBinding binding = m_Actors[index];
        if (!binding) { return null; }
        return AnimalBase.Cast(binding.Live);
    }
}

// Provider-neutral seam: HCX supplies its existing tracked eAI list, never scans.
class HCAdminWorldSources
{
    bool StepAI(HCAdminWorldCapture capture, int rows) { return true; }
}

modded class HCInfectedModule
{
    // Detached public read seam; no claim, stimulus, routing or state mutations.
    int HCAdminHordeCount() { if (!m_Healthy || !m_State || !m_State.Groups) { return 0; } return m_State.Groups.Count(); }
    void HCAdminHorde(HCAdminWorldCapture capture, int index)
    {
        if (index < 0 || index >= HCAdminHordeCount()) { return; }
        HCHordeRecord row = m_State.Groups[index];
        if (!row) { return; }
        string detail = "living=" + row.Living.ToString() + "; state=" + row.State.ToString();
        detail += "; route=" + row.HasRoute.ToString() + "; ledger anchor, not a live-body census";
        capture.Put("hordes", row.Anchor, "Horde " + row.Id.ToString(), detail);
    }
}
modded class HCBuildingClaim
{
    // Existing owner store, position/age only. Group and owner identities withheld.
    int HCAdminClaimCount() { if (!m_Healthy || !m_Data || !m_Data.Claims) { return 0; } return m_Data.Claims.Count(); }
    void HCAdminClaim(HCAdminWorldCapture capture, int index)
    {
        if (index < 0 || index >= HCAdminClaimCount()) { return; }
        HCBuildingClaimRecord row = m_Data.Claims[index];
        if (row) { capture.Put("claimed-bases", row.Position, "Claimed building", "absence_seconds=" + row.AbsentSeconds.ToString() + "; ledger claim; group identity withheld"); }
    }
}

modded class HCNativeInfectedPack
{
    bool HCAdminAnchor(out vector position, out int living)
    {
        position = vector.Zero;
        living = 0;
        // Pack centroid sample: at most 64 existing owned handles, never a scan.
        int count = Math.Min(m_Members.Count(), 64);
        for (int index = 0; index < count; index++)
        {
            ZombieBase body = m_Members[index];
            if (!body || !body.IsAlive() || body.IsPendingDeletion()) { continue; }
            position += body.GetPosition();
            living++;
        }
        if (living == 0) { return false; }
        // Enforce refuses vector / int; scale by a float reciprocal.
        float share = 1.0 / living;
        position = position * share;
        return true;
    }
}
modded class HCInfectedModule
{
    int HCAdminPackCount() { if (!m_Healthy) { return 0; } return m_Packs.Count(); }
    void HCAdminPack(HCAdminWorldCapture capture, int index)
    {
        if (index < 0 || index >= HCAdminPackCount() || !m_Packs[index]) { return; }
        vector position;
        int living;
        if (m_Packs[index].HCAdminAnchor(position, living))
        {
            capture.Put("infected-packs", position, "Infected pack", "living_sample=" + living.ToString() + "; centroid of at most 64 owned members");
        }
    }
}
