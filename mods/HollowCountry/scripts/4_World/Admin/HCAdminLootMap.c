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
// EnScript.c:94,380,385,394,407 Cast/Count/Clear/Find/Insert; EnMath.c:305,441,553,566
// Sqrt/Ceil/Min/Max; gameplay.c:636 GetGame. Shared budgets/store own their native citations.
// One native circle/tick over one SubCellM square; retained row cursor, hard
// tick/cell/item/type/output caps. Native query allocation/time CANNOT be
// preempted; oversize output refuses without processing. The query COST IS
// UNMEASURED (named in every start line). Never scan inventories or imply a CE census.
// Job arithmetic (HCJobTickCap): a tick runs at most one native query, then rows
// until the row-unit budget is spent, so ticks <= cells + ceil(worst-case row units /
// rows per step) + 1. The row loop has its own wall-clock deadline (RowDeadlineMs)
// that STARTS AFTER the query, so a slow native query (not preemptible) never
// consumes the deadline of its own rows and costs no extra tick. Progress is
// deterministic: every tick spends at least MinRowUnitsPerTick row units before the
// wall-clock deadline may stop the loop (the deadline is only an upper bound beyond
// that floor), so a slow row loop cannot add unbounded ticks. job_tick_cap is sized
// from the guaranteed floor plus TickCapHeadroomPercent and still caps total ticks.
// Wave 12 (#193). Unmeasured.
class HCAdminLootMapLimits
{
    // Square sub-cell edge for one query. The query circle is its half diagonal,
    // so each tick's native circle (354 m radius) is about an eighth of the former 1000 m one.
    // Named config, not a gameplay range. 15360 m / 500 = 31 -> 961 cells <= MaxCells.
    int SubCellM = 500;
    int MaxPositionsPerReply = 128;
    // Row-unit budget per tick. A rejected class costs 1 unit (type string compare
    // only); a matched class costs MatchRowUnits (cast, profile, type row, point).
    int MaxRowsPerStep = 256;
    int MatchRowUnits = 4;
    // Progress floor: row units every tick spends BEFORE the wall-clock row deadline
    // is consulted (clamped to MaxRowsPerStep). The tick cap is sized from it.
    int MinRowUnitsPerTick = 128;
    // Slack added to the row-tick term of the tick cap (percent of that term), so a
    // slow machine finishes the job instead of refusing at job_tick_cap.
    int TickCapHeadroomPercent = 25;
    // Wall-clock guard for the row loop only, started after the native query so the
    // query's own time never spends it (the 4 ms HCWorkBudget default, now named).
    // An upper bound only: it cannot stop a tick before MinRowUnitsPerTick units.
    int RowDeadlineMs = 4;
    int MaxObjectsPerCell = 4096;
    int MaxItemsScanned = 65536;
    int MaxMatches = 8192;
    int MaxTypes = 32;
    int MaxCells = 1024;
    // The tick cap is converted to seconds at this core tick interval. A slower
    // HCSettings.TickIntervalMs refuses the job instead of silently missing it.
    int MaxTickIntervalMs = 1000;
    // Client wait = job tick cap in seconds plus this slack for ingress, the
    // final write and delivery. Not an RPC retry interval.
    int ReplyGraceSeconds = 30;
    // Floor of the client's job window sized from the ack (a tiny job still gets
    // time for ingress, the final write and delivery). The ceiling is the largest
    // admitted job, HCClientWaitSeconds().
    int MinClientWaitSeconds = 60;
    // How long the client keeps lootmap marks on its map after the reply.
    int ViewSeconds = 300;
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
    protected int m_Cursor;
    protected int m_Cell;
    protected int m_Across;
    protected float m_Size;
    protected float m_MinX;
    protected float m_MinZ;
    protected float m_MaxX;
    protected float m_MaxZ;
    protected int m_Ticks;
    protected int m_MaxTicks;
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

    static int HCCellsAcross(float worldSize, int subCellM)
    {
        if (!(worldSize > 0) || subCellM < 1) { return 0; }
        int across = Math.Ceil(worldSize / subCellM);
        return across;
    }

    // Worst case row units: every scanned row costs 1, each match costs MatchRowUnits.
    // One query plus its rows fit one tick (RowDeadlineMs starts after the query), so the
    // cells term is one tick per cell. The row term uses the GUARANTEED row units per tick
    // (MinRowUnitsPerTick, clamped to MaxRowsPerStep), which the wall-clock deadline cannot
    // undercut, plus TickCapHeadroomPercent. Total ticks stay capped.
    static int HCJobTickCap(HCAdminLootMapLimits limits, int cells)
    {
        int floorUnits = Math.Min(limits.MinRowUnitsPerTick, limits.MaxRowsPerStep);
        floorUnits = Math.Max(floorUnits, 1);
        int units = limits.MaxItemsScanned + (limits.MatchRowUnits - 1) * limits.MaxMatches;
        int rowTicks = (units + floorUnits - 1) / floorUnits;
        rowTicks = rowTicks + rowTicks * limits.TickCapHeadroomPercent / 100;
        return cells + rowTicks + 1;
    }

    // Ceiling of the client job window for the final marks reply (the request itself is
    // acked at once): the largest possible job (MaxCells) at the budgeted core tick, plus
    // ReplyGraceSeconds. The client sizes its real window from the ack
    // (HCClientWindowSeconds) and never exceeds this. Not a request timeout.
    static int HCClientWaitSeconds()
    {
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        int ticks = HCAdminLootMap.HCJobTickCap(limits, limits.MaxCells);
        return (ticks * limits.MaxTickIntervalMs + 999) / 1000 + limits.ReplyGraceSeconds;
    }

    // First unsigned integer after `key` in an ack/notice text (at most 9 digits), or -1
    // when the key or its digits are missing. Bounded, no Substring past Length().
    static int HCAckInt(string notice, string key)
    {
        int at = notice.IndexOf(key);
        if (at < 0) { return -1; }
        int start = at + key.Length();
        string digitSet = "0123456789";
        int value = 0;
        int digits = 0;
        while (start + digits < notice.Length() && digits < 9)
        {
            string one = notice.Get(start + digits);
            int found = digitSet.IndexOf(one);
            if (found < 0) { break; }
            value = value * 10 + found;
            digits++;
        }
        if (digits == 0) { return -1; }
        return value;
    }

    // Server-side expected job deadline in ms for the ack: the job's tick cap times the
    // slower of the configured core tick and the cadence the server last delivered
    // (observedMs <= 0 means none yet). Bounded: observed cadence is at most 300 s.
    static int HCBudgetMs(int ticks, int configuredMs, int observedMs)
    {
        int cadence = Math.Max(configuredMs, 1);
        if (observedMs > cadence) { cadence = observedMs; }
        return ticks * cadence;
    }

    // Client job window from the server's own deadline (ack budget_ms) plus
    // ReplyGraceSeconds, between MinClientWaitSeconds and HCClientWaitSeconds().
    // An unreadable or out-of-range ack falls back to the ceiling, never a short wait.
    static int HCClientWindowSeconds(int budgetMs)
    {
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        int ceiling = HCAdminLootMap.HCClientWaitSeconds();
        if (budgetMs < 1) { return ceiling; }
        int seconds = (budgetMs + 999) / 1000 + limits.ReplyGraceSeconds;
        seconds = Math.Max(seconds, limits.MinClientWaitSeconds);
        seconds = Math.Min(seconds, ceiling);
        return seconds;
    }

    int HCTotalCells() { return m_Across * m_Across; }
    int HCMaxTicks() { return m_MaxTicks; }

    bool HCStart(string filter, int tickMs)
    {
        m_Document = new HCAdminLootDocument;
        if (!GetGame() || !GetGame().IsServer()) { HCFinish("server_only"); return false; }
        if (tickMs < 1 || tickMs > m_Limits.MaxTickIntervalMs) { HCFinish("tick_interval_exceeds_job_budget"); return false; }
        m_Document.time = HCGroupClock.Utc();
        if (m_Document.time < 0) { HCFinish("clock_unavailable"); return false; }
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
        m_Across = HCAdminLootMap.HCCellsAcross(m_Size, m_Limits.SubCellM);
        if (m_Across < 1 || m_Across > m_Limits.MaxCells) { HCFinish("world_cell_cap"); return false; }
        if (m_Across * m_Across > m_Limits.MaxCells) { HCFinish("world_cell_cap"); return false; }
        m_MaxTicks = HCAdminLootMap.HCJobTickCap(m_Limits, m_Across * m_Across);
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
    }

    protected bool HCQueryCell()
    {
        int column = m_Cell % m_Across;
        int row = m_Cell / m_Across;
        m_MinX = column * m_Limits.SubCellM;
        m_MinZ = row * m_Limits.SubCellM;
        m_MaxX = Math.Min(m_Size, m_MinX + m_Limits.SubCellM);
        m_MaxZ = Math.Min(m_Size, m_MinZ + m_Limits.SubCellM);
        vector center = Vector((m_MinX + m_MaxX) / 2, 0, (m_MinZ + m_MaxZ) / 2);
        // Circle through the cell corners (half diagonal), rounded up, so the
        // circle covers the whole square; edge cells are clipped by the world.
        float halfX = (m_MaxX - m_MinX) / 2;
        float halfZ = (m_MaxZ - m_MinZ) / 2;
        float radius = Math.Ceil(Math.Sqrt(halfX * halfX + halfZ * halfZ));
        m_Candidates.Clear();
        m_Cargos.Clear();
        GetGame().GetObjectsAtPosition(center, radius, m_Candidates, m_Cargos);
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

    // Class prefilter first: one Object.GetType string compare (Object.c:467), no cast,
    // profile or position work for a rejected row. True only for a matched class, so
    // the caller can charge MatchRowUnits for the extra work done.
    protected bool HCObserve(Object candidate)
    {
        string className = candidate.GetType();
        if (!HCMatches(className)) { return false; }
        EntityAI entity = EntityAI.Cast(candidate);
        if (!entity || entity.GetHierarchyParent()) { return true; }
        if (className.Length() > 96) { HCFinish("class_name_cap"); return true; }
        CEItemProfile profile = entity.GetEconomyProfile();
        if (!profile) { return true; }
        vector pos = entity.GetPosition();
        if (!HCDebugSnapshot.HCPositionValid(pos)) { return true; }
        // Half-open sub-cells own their observations, so overlapping circles do not
        // count the same stationary entity twice (cell ownership is the dedupe; no
        // seen list). An entity that moves into a cell not yet visited after it was
        // counted can be counted again: the job is not an atomic world snapshot.
        if (pos[0] < m_MinX || pos[2] < m_MinZ) { return true; }
        if (pos[0] >= m_MaxX && m_MaxX < m_Size) { return true; }
        if (pos[2] >= m_MaxZ && m_MaxZ < m_Size) { return true; }
        if (m_Document.matched >= m_Limits.MaxMatches) { HCFinish("matches_cap"); return true; }
        HCAdminLootType typeRow;
        for (int typeIndex = 0; typeIndex < m_Document.types.Count(); typeIndex++)
        {
            if (m_Document.types[typeIndex].className == className) { typeRow = m_Document.types[typeIndex]; break; }
        }
        if (!typeRow)
        {
            if (m_Document.types.Count() >= m_Limits.MaxTypes) { HCFinish("types_cap"); return true; }
            typeRow = new HCAdminLootType;
            typeRow.className = className;
            typeRow.nominal = profile.GetNominal();
            if (typeRow.nominal < 0) { typeRow.nominal = -1; }
            m_Document.types.Insert(typeRow);
        }
        typeRow.count++;
        m_Document.matched++;
        if (m_Document.points.Count() >= m_Limits.MaxPositionsPerReply) { m_Document.truncated++; return true; }
        HCAdminLootPoint point = new HCAdminLootPoint;
        point.className = className;
        point.x = pos[0];
        point.z = pos[2];
        m_Document.points.Insert(point);
        return true;
    }

    // No idle tick, periodic refresh, loot mutation, inventory traversal or CE
    // debug export. One query at most, then rows until MaxRowsPerStep units are spent
    // (the wall clock may stop the loop only after MinRowUnitsPerTick units).
    bool HCStep()
    {
        if (!m_Document || m_Document.state != "pending") { return true; }
        if (!GetGame().IsServer() || !GetCEApi()) { HCFinish("ce_world_enumeration_unavailable"); return true; }
        m_Ticks++;
        if (m_Ticks > m_MaxTicks) { HCFinish("job_tick_cap"); return true; }
        m_Units.HCReset(m_Limits.MaxRowsPerStep);
        if (!m_Loaded && !HCQueryCell()) { return true; }
        // Start the row clock after the query: a query slower than the row deadline
        // must not leave its rows for a second tick.
        m_Budget.HCReset(m_Limits.MaxRowsPerStep, m_Limits.RowDeadlineMs);
        int floorUnits = Math.Min(m_Limits.MinRowUnitsPerTick, m_Limits.MaxRowsPerStep);
        while (m_Cursor < m_Candidates.Count())
        {
            if (!m_Units.HCTake(1)) { return false; }
            // The wall clock is an upper bound only once the guaranteed floor is spent.
            if (m_Units.HCUsed() > floorUnits && !m_Budget.HCContinue()) { return false; }
            if (m_Document.scanned >= m_Limits.MaxItemsScanned) { HCFinish("items_scanned_cap"); return true; }
            Object candidate = m_Candidates[m_Cursor];
            m_Cursor++;
            m_Document.scanned++;
            if (HCObserve(candidate)) { m_Units.HCCharge(m_Limits.MatchRowUnits - 1); }
            if (m_Document.state != "pending") { return true; }
        }
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
        reply.Notice += "; ground observations across ticks; CE census unavailable; query_cost=unmeasured; runtime=PENDING";
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
