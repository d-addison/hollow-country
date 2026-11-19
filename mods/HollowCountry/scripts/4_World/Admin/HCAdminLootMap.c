// #168 request 5: request-only, server-owned ground observations. runtime=PENDING.
// Installed scripts-1.30.164289 API evidence (not runtime qualification):
// 3_Game/Global/Game.c:923 GetObjectsAtPosition (circle output; NO cursor/cap),
// :931,934 GetWorld/GetWorldName, :612 ConfigIsExisting, :1120 IsServer;
// Global/World.c:82 GetWorldSize; Entities/Object.c:287,467 GetPosition/GetType;
// Entities/EntityAI.c:885,888 GetHierarchyParent/GetEconomyProfile;
// CE/CentralEconomy.c:746 GetCEApi, :754 CEItemProfile.GetNominal.
// CEApi :227-736 exposes no iterable live CE census or profile lookup by class.
// EconomyMap :527 is a DEVELOPER/DIAG ONLY TGA export, not a positions API.
// 1_Core/proto/EnString.c:113,171,199,240,286,448 Substring/ToLower/Length/IndexOf/Contains/Get;
// EnScript.c:94,380,385,394,407 Cast/Count/Clear/Find/Insert; EnMath.c:441,553 Ceil/Min;
// gameplay.c:636 GetGame. Shared budgets/store own their native citations.
// One native circle/tick; retained row cursor, hard job/cell/item/type/output
// caps. Native query allocation/time CANNOT be preempted; oversize output
// refuses without processing. Never scan inventories or imply a CE census.
class HCAdminLootMapLimits
{
    // One network-bubble / rifle-hearing scale (~1 km), not a new gameplay range.
    float QueryRadiusM = 1000;
    int MaxPositionsPerReply = 128;
    int MaxItemsPerStep = 32;
    int MaxObjectsPerCell = 4096;
    int MaxItemsScanned = 65536;
    int MaxMatches = 8192;
    int MaxTypes = 32;
    int MaxCells = 1024;
    int MaxJobSeconds = 300;
    // Client lead wiring: ingress + final server tick at the allowed 10 s core
    // interval, plus delivery slack. This is not an RPC retry interval.
    int ReplyGraceSeconds = 30;
    int CooldownSeconds = 30;
}

class HCAdminLootType
{
    string className;
    int count;
    int nominal = -1;
}

class HCAdminLootPoint
{
    string className;
    float x;
    float z;
}

class HCAdminLootDocument
{
    int version = 1;
    int time;
    string world;
    string filter;
    string mode;
    string state = "pending";
    string reason;
    string scope = "ground_world_observations";
    string census = "refused_ce_inventory_enumeration_unavailable";
    int scanned;
    int cells;
    int matched;
    int truncated;
    ref array<ref HCAdminLootType> types = new array<ref HCAdminLootType>;
    ref array<ref HCAdminLootPoint> points = new array<ref HCAdminLootPoint>;
}

class HCAdminLootMap
{
    static const string PATH = "$profile:HollowCountry/debug/lootmap.json";
    static const int MAX_BYTES = 65536;
    protected ref HCAdminLootMapLimits m_Limits = new HCAdminLootMapLimits;
    protected ref HCAdminLootDocument m_Document;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref array<Object> m_Candidates = new array<Object>;
    protected ref array<CargoBase> m_Cargos = new array<CargoBase>;
    protected ref array<Object> m_Seen = new array<Object>;
    protected int m_Cursor;
    protected int m_Cell;
    protected int m_Across;
    protected float m_Size;
    protected float m_MinX;
    protected float m_MinZ;
    protected float m_MaxX;
    protected float m_MaxZ;
    protected float m_Started;
    protected bool m_Loaded;

    static bool HCValidFilter(string value)
    {
        if (value.Length() < 1 || value.Length() > 96) { return false; }
        string alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_";
        for (int charIndex = 0; charIndex < value.Length(); charIndex++)
        {
            if (!alphabet.Contains(value.Get(charIndex))) { return false; }
        }
        return true;
    }

    bool HCStart(string filter)
    {
        m_Document = new HCAdminLootDocument;
        if (!GetGame() || !GetGame().IsServer()) { HCFinish("server_only"); return false; }
        m_Document.time = HCGroupClock.Utc();
        m_Document.world = GetGame().GetWorldName();
        m_Document.world.ToLower();
        bool forcePrefix = false;
        if (filter.Length() > 1 && filter.Get(filter.Length() - 1) == "*")
        {
            filter = filter.Substring(0, filter.Length() - 1);
            forcePrefix = true;
        }
        if (!HCAdminLootMap.HCValidFilter(filter)) { HCFinish("invalid_class_or_prefix"); return false; }
        m_Document.filter = filter;
        m_Document.mode = "prefix";
        bool exactClass = GetGame().ConfigIsExisting("CfgVehicles " + filter);
        exactClass = exactClass || GetGame().ConfigIsExisting("CfgWeapons " + filter);
        exactClass = exactClass || GetGame().ConfigIsExisting("CfgMagazines " + filter);
        if (!forcePrefix && exactClass) { m_Document.mode = "exact"; }
        if (!GetCEApi() || !GetGame().GetWorld()) { HCFinish("ce_world_enumeration_unavailable"); return false; }
        if (m_Document.world != "chernarusplus") { HCFinish("unsupported_map"); return false; }
        m_Size = GetGame().GetWorld().GetWorldSize();
        if (!(m_Size > 0)) { HCFinish("world_bounds_unavailable"); return false; }
        m_Across = Math.Ceil(m_Size / m_Limits.QueryRadiusM);
        if (m_Across < 1 || m_Across > m_Limits.MaxCells) { HCFinish("world_cell_cap"); return false; }
        if (m_Across * m_Across > m_Limits.MaxCells) { HCFinish("world_cell_cap"); return false; }
        m_Started = GetGame().GetTickTime();
        return true;
    }

    bool HCMatches(string className)
    {
        if (m_Document.mode == "exact") { return className == m_Document.filter; }
        return className.IndexOf(m_Document.filter) == 0;
    }

    protected void HCFinish(string reason)
    {
        m_Document.state = "refused";
        m_Document.reason = reason;
        if (reason == "")
        {
            m_Document.state = "observed";
            m_Document.reason = "ground_observations_only";
        }
        m_Candidates.Clear();
        m_Cargos.Clear();
        m_Seen.Clear();
    }

    protected bool HCQueryCell()
    {
        int column = m_Cell % m_Across;
        int row = m_Cell / m_Across;
        m_MinX = column * m_Limits.QueryRadiusM;
        m_MinZ = row * m_Limits.QueryRadiusM;
        m_MaxX = Math.Min(m_Size, m_MinX + m_Limits.QueryRadiusM);
        m_MaxZ = Math.Min(m_Size, m_MinZ + m_Limits.QueryRadiusM);
        vector center = Vector((m_MinX + m_MaxX) / 2, 0, (m_MinZ + m_MaxZ) / 2);
        m_Candidates.Clear();
        m_Cargos.Clear();
        GetGame().GetObjectsAtPosition(center, m_Limits.QueryRadiusM, m_Candidates, m_Cargos);
        m_Document.cells++;
        if (m_Candidates.Count() > m_Limits.MaxObjectsPerCell || m_Cargos.Count() > m_Limits.MaxObjectsPerCell)
        {
            HCFinish("objects_per_cell_cap");
            return false;
        }
        m_Cursor = 0;
        m_Loaded = true;
        return true;
    }

    protected void HCObserve(Object candidate)
    {
        EntityAI entity = EntityAI.Cast(candidate);
        if (!entity || entity.GetHierarchyParent()) { return; }
        string className = entity.GetType();
        if (!HCMatches(className)) { return; }
        if (className.Length() > 96) { HCFinish("class_name_cap"); return; }
        CEItemProfile profile = entity.GetEconomyProfile();
        if (!profile) { return; }
        vector pos = entity.GetPosition();
        if (!HCDebugSnapshot.HCPositionValid(pos)) { return; }
        // Half-open cells own their observations, so overlapping circles do not
        // count the same stationary entity twice. World-edge coordinates included.
        if (pos[0] < m_MinX || pos[2] < m_MinZ) { return; }
        if (pos[0] >= m_MaxX && m_MaxX < m_Size) { return; }
        if (pos[2] >= m_MaxZ && m_MaxZ < m_Size) { return; }
        if (m_Seen.Find(entity) >= 0) { return; }
        if (m_Seen.Count() >= m_Limits.MaxMatches) { HCFinish("matches_cap"); return; }
        HCAdminLootType typeRow;
        for (int typeIndex = 0; typeIndex < m_Document.types.Count(); typeIndex++)
        {
            if (m_Document.types[typeIndex].className == className) { typeRow = m_Document.types[typeIndex]; break; }
        }
        if (!typeRow)
        {
            if (m_Document.types.Count() >= m_Limits.MaxTypes) { HCFinish("types_cap"); return; }
            typeRow = new HCAdminLootType;
            typeRow.className = className;
            typeRow.nominal = profile.GetNominal();
            if (typeRow.nominal < 0) { typeRow.nominal = -1; }
            m_Document.types.Insert(typeRow);
        }
        m_Seen.Insert(entity);
        typeRow.count++;
        m_Document.matched++;
        if (m_Document.points.Count() >= m_Limits.MaxPositionsPerReply) { m_Document.truncated++; return; }
        HCAdminLootPoint point = new HCAdminLootPoint;
        point.className = className;
        point.x = pos[0];
        point.z = pos[2];
        m_Document.points.Insert(point);
    }

    // No idle tick, periodic refresh, loot mutation, inventory traversal or CE
    // debug export. One query at most, then <=MaxItemsPerStep candidate rows.
    bool HCStep()
    {
        if (!m_Document || m_Document.state != "pending") { return true; }
        if (!GetGame().IsServer() || !GetCEApi()) { HCFinish("ce_world_enumeration_unavailable"); return true; }
        if (GetGame().GetTickTime() - m_Started >= m_Limits.MaxJobSeconds) { HCFinish("job_time_cap"); return true; }
        m_Budget.HCReset(m_Limits.MaxItemsPerStep);
        m_Units.HCReset(m_Limits.MaxItemsPerStep);
        if (!m_Loaded && !HCQueryCell()) { return true; }
        int stepItems = 0;
        while (m_Cursor < m_Candidates.Count() && stepItems < m_Limits.MaxItemsPerStep)
        {
            if (!m_Units.HCTake(1) || !m_Budget.HCContinue()) { return false; }
            if (m_Document.scanned >= m_Limits.MaxItemsScanned) { HCFinish("items_scanned_cap"); return true; }
            Object candidate = m_Candidates[m_Cursor];
            m_Cursor++;
            stepItems++;
            m_Document.scanned++;
            HCObserve(candidate);
            if (m_Document.state != "pending") { return true; }
        }
        if (m_Cursor < m_Candidates.Count()) { return false; }
        m_Loaded = false;
        m_Cell++;
        m_Candidates.Clear();
        m_Cargos.Clear();
        if (m_Cell < m_Across * m_Across) { return false; }
        HCFinish("");
        return true;
    }

    HCAdminLootDocument HCDocument() { return m_Document; }

    HCAdminReply HCReply(int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Snapshot = true;
        string result = "refused";
        if (m_Document.state == "observed") { result = "ok"; }
        reply.Notice = "[HC Admin] cmd=lootmap result=" + result + " reason=" + m_Document.reason;
        reply.Notice += "; ground observations across ticks; CE census unavailable; runtime=PENDING";
        reply.Notice += "; scanned=" + m_Document.scanned.ToString() + " matched=" + m_Document.matched.ToString() + " truncated=" + m_Document.truncated.ToString();
        for (int typeIndex = 0; typeIndex < m_Document.types.Count(); typeIndex++)
        {
            HCAdminLootType row = m_Document.types[typeIndex];
            reply.Lines.Insert(row.className + " ground_observed=" + row.count.ToString() + " nominal=" + row.nominal.ToString());
        }
        if (m_Document.types.Count() == 0) { reply.Lines.Insert("No matching ground observations; nominal=unavailable (no per-class CE profile lookup API)."); }
        for (int pointIndex = 0; pointIndex < m_Document.points.Count(); pointIndex++)
        {
            HCAdminLootPoint point = m_Document.points[pointIndex];
            HCAdminMark mark = new HCAdminMark;
            mark.Layer = "lootmap";
            mark.Position = Vector(point.x, 0, point.z);
            mark.Label = point.className;
            mark.Detail = "Ground observation across ticks; not a CE inventory census; runtime=PENDING";
            reply.Marks.Insert(mark);
        }
        return reply;
    }
}
