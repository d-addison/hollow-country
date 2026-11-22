// Police: borrow real stock first; otherwise own one HC container (Barrel_Green) per site.
// Native persistence owns the container and its cargo after creation. Container
// lifecycle (owner 2026-11-22): an emptied container is refilled in place after
// RefillCooldownSeconds, an aged (ContainerLifetimeSeconds) or ruined or missing one is
// drained, deleted and replaced, never while a player is within RefillClearRadius.
// A durable generation receipt precedes every native mutation, including failures.
// Native scripts-1.30.164289: Global/Game.c:703/705 CreateObjectEx/ObjectDelete;
// CE/CentralEconomy.c:9/17/28 ECE_SETUP/CREATEPHYSICS/KEEPHEIGHT;
// Systems/Inventory/Inventory.c:876 CreateInInventory; Entities/Object.c:287 GetPosition.
class HCEventPoliceRewardIO : HCEventRewardIO
{
    void HCEventPoliceRewardIO()
    {
        m_Root = "$profile:HollowCountry/Events/police-cache-stock";
    }
}
// In-memory view of one site's generation receipts. Ok: highest completed generation;
// Gen: highest readable receipt (Gen > Ok = generation started and not completed);
// Num: highest receipt number on disk, readable or torn (numbering only); Id: persistent id of
// the barrel recorded with the completed generation ("" = unknown, never deleted).
class HCPoliceGeneration
{
    int Num;
    string Id;
    // Open generation only: its kind and the id of the barrel it is working on ("" = unknown).
    string GenKind;
    string GenId;
    int Ok;
    int OkUtc;
    int Gen;
    int GenUtc;
    int GenItems;
}
// Unlike the legacy per-boot allowance, these immutable site grants survive restart.
// One orphan repair ever: spent .txt, no .pos/.repair and no ground barrel in the
// completed capped scan. The scan only marks the site eligible in process memory;
// Commit writes the immutable .repair when it grants, so a refused SpawnPosition or a
// restart before the grant leaves the repair available for the next boot.
// Existing HCEventJournalIO provides bounded write/readback; no other replay or refund.
// Generation receipts (immutable WriteNew files, same pattern as .repair):
//   <site>.gen-N  written BEFORE any native create/delete/item: generation N, utc, kind, items.
//   <site>.ok-N   written after the items exist: N, the generation utc (cooldown/lifetime anchor)
//                 and the barrel's persistent id (only that barrel may ever be drained or deleted).
//   <site>.bar-N  replace/recreate only: the new barrel's id, written before its items (crash recovery).
// No receipt = legacy record, migrated in place by writing ok-1 (utc now, id of the barrel found).
// A missing or future-dated anchor is re-armed durably (ok-(max+1), utc now). The highest N wins;
// lower files are pruned best effort. Cooldown and lifetime read the durable utc, never memory.
class HCEventPoliceStockLedger : HCEventRewardLedger
{
    protected ref array<string> m_RepairChecked = new array<string>;
    protected ref array<string> m_RepairPending = new array<string>;
    protected ref map<string, ref HCPoliceGeneration> m_Generations = new map<string, ref HCPoliceGeneration>;
    protected bool m_PruneLogged;

    // A positive barrel observation may refuse early; absence requires a completed scan.
    void HCRepairOrphan(string siteId, bool barrelPresent)
    {
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return; }
        // A barrel seen by any later scan revokes eligibility granted by an earlier empty scan.
        int pending = m_RepairPending.Find(siteId);
        if (barrelPresent && pending >= 0) { m_RepairPending.Remove(pending); }
        if (m_RepairChecked.Find(siteId) >= 0 || !m_IO || m_Fault || !m_IO.Ensure()) { return; }
        m_RepairChecked.Insert(siteId);
        if (m_Granted.Find(siteId) >= 0 || !m_IO.Exists(siteId + ".txt") || m_IO.Exists(siteId + ".pos") || m_IO.Exists(siteId + ".repair")) { return; }
        if (barrelPresent)
        {
            Print("[HC Events] police grant orphan kept; " + siteId + "; reason=barrel_present runtime=PENDING");
            return;
        }
        m_RepairPending.Insert(siteId);
    }

    override HCEventRewardPlan Commit(string siteId)
    {
        m_Refusal = "police_cache_site_invalid";
        if (siteId != "coastal-police-source" && siteId != "inland-police-source") { return null; }
        m_Refusal = "police_cache_journal_unavailable";
        if (!m_IO || m_Fault || !m_IO.Ensure()) { return null; }
        string name = siteId + ".txt";
        // These are site spends, not leases owned by a live event. Never release
        // them on event expiry: native cargo may still exist outside this scan.
        m_Refusal = "police_cache_grant_spent";
        if (m_Granted.Find(siteId) >= 0) { return null; }
        m_Refusal = "police_cache_position_recorded";
        if (m_IO.Exists(siteId + ".pos")) { return null; }
        int repair = m_RepairPending.Find(siteId);
        if (repair < 0)
        {
            m_Refusal = "police_cache_repair_spent";
            if (m_IO.Exists(siteId + ".repair")) { return null; }
            m_Refusal = "police_cache_grant_spent";
            if (m_IO.Exists(name)) { return null; }
        }
        m_Refusal = "police_cache_journal_fault";
        if (repair >= 0)
        {
            m_RepairPending.Remove(repair);
            // The marker is the spend: it is durable before any native creation.
            if (m_IO.Exists(siteId + ".repair")) { m_Refusal = "police_cache_repair_spent"; return null; }
            if (!m_IO.WriteNew(siteId + ".repair", "HC-POLICE-STOCK-REPAIR v1 " + siteId, 128)) { Fault(); return null; }
            Print("[HC Events] police grant orphan repaired; " + siteId + "; runtime=PENDING");
        }
        m_Granted.Insert(siteId);
        HCEventRewardPlan plan = HCFreshPlan(siteId);
        // A repair consumes its marker-backed allowance without rewriting the spent .txt.
        if (repair < 0 && !m_IO.WriteNew(name, "HC-POLICE-STOCK v1 " + siteId, 128)) { Fault(); return null; }
        m_Refusal = "";
        return plan;
    }

    // Ownership lives in this ledger, never in entity storage: extending Barrel_Green
    // OnStoreSave broke every persisted barrel ("Scripted variables corrupted", 103 boot).
    bool RecordCache(string siteId, vector position)
    {
        if (!m_IO || m_Fault) { return false; }
        return m_IO.WriteNew(siteId + ".pos", position.ToString(false), 96);
    }

    // The one stock table: first creation, refill and replacement all use it.
    HCEventRewardPlan HCFreshPlan(string siteId)
    {
        HCEventRewardPlan plan = new HCEventRewardPlan;
        plan.SiteId = siteId;
        plan.Items.Insert("BandageDressing");
        plan.Items.Insert("SodaCan_Cola");
        plan.Items.Insert("MetalWire");
        return plan;
    }
    static bool HCSiteValid(string siteId)
    {
        return siteId == "coastal-police-source" || siteId == "inland-police-source";
    }
    // Persisted record complete (spent .txt plus recorded .pos) and the position valid.
    bool HCBarrelRecordPosition(string siteId, out vector position)
    {
        position = vector.Zero;
        if (!HCSiteValid(siteId)) { return false; }
        if (!m_IO || m_Fault || !m_IO.Ensure() || !m_IO.Exists(siteId + ".txt")) { return false; }
        return CachePosition(siteId, position);
    }
    protected int HCEpochOf(string siteId, string name, string kind)
    {
        string prefix = siteId + "." + kind;
        if (name.IndexOf(prefix) != 0) { return 0; }
        int tail = name.Length() - prefix.Length();
        string digits = name.Substring(prefix.Length(), tail);
        int value = digits.ToInt();
        if (value < 1 || value.ToString() != digits) { return 0; }
        return value;
    }
    protected bool HCReadReceipt(string name, string tag, int generation, out int utc, out int items, out string barrelId, out string kind)
    {
        utc = 0;
        items = 0;
        barrelId = "";
        kind = "";
        if (!m_IO.Exists(name)) { return false; }
        string text = m_IO.Read(name, 256);
        if (text == "") { return false; }
        array<string> tokens = new array<string>;
        text.Split(" ", tokens);
        if (tokens.Count() < 11) { return false; }
        if (tokens[0] != tag || tokens[1] != "v1" || tokens[3] != "gen" || tokens[4].ToInt() != generation || tokens[5] != "utc" || tokens[9] != "items") { return false; }
        utc = tokens[6].ToInt();
        items = tokens[10].ToInt();
        kind = tokens[8];
        // Optional barrel identity (persistent id) recorded with the completed generation.
        if (tokens.Count() >= 16 && tokens[11] == "id") { barrelId = tokens[12] + " " + tokens[13] + " " + tokens[14] + " " + tokens[15]; }
        return utc > 0;
    }
    // Best-effort delete of one receipt; a persistent failure is logged once per process.
    protected void HCPrune(string name)
    {
        if (!m_IO.Exists(name)) { return; }
        if (m_IO.Remove(name) || m_PruneLogged) { return; }
        m_PruneLogged = true;
        Print("[HC Police] action=receipt_prune_failed reason=delete_refused file=" + name);
    }
    // Loads the receipts once per process; null = unavailable this process (never refuses boot).
    // Num is the highest number of any receipt file (readable or torn) so a new WriteNew never collides.
    // A torn gen-N is ignored (native work starts only after a successful readback). A torn ok-N
    // falls back to the readable gen-N utc (identity unknown). No readable anchor: Ok = 0 and the
    // caller re-arms durably.
    HCPoliceGeneration HCGeneration(string siteId)
    {
        if (!HCSiteValid(siteId) || !m_IO || m_Fault) { return null; }
        HCPoliceGeneration state;
        if (m_Generations.Find(siteId, state)) { return state; }
        // Bounded directory listing (27 files, no sub-directories); null = unavailable.
        array<string> names = m_IO.Names();
        if (!names) { return null; }
        state = new HCPoliceGeneration;
        int genMax = 0;
        int okMax = 0;
        foreach (string listed : names)
        {
            int genNumber = HCEpochOf(siteId, listed, "gen-");
            if (genNumber > genMax) { genMax = genNumber; }
            int okNumber = HCEpochOf(siteId, listed, "ok-");
            if (okNumber > okMax) { okMax = okNumber; }
        }
        state.Num = genMax;
        if (okMax > state.Num) { state.Num = okMax; }
        int utc;
        int items;
        string barrelId;
        string kind;
        bool okReadable = false;
        if (okMax > 0)
        {
            if (HCReadReceipt(siteId + ".ok-" + okMax.ToString(), "HC-POLICE-OK", okMax, utc, items, barrelId, kind))
            {
                okReadable = true;
                state.Ok = okMax;
                state.OkUtc = utc;
                state.Id = barrelId;
            }
            else if (HCReadReceipt(siteId + ".gen-" + okMax.ToString(), "HC-POLICE-GEN", okMax, utc, items, barrelId, kind))
            {
                // Torn ok-N: the generation utc is the anchor; identity is unknown, gen-N is kept.
                Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=ok_receipt_torn");
                state.Ok = okMax;
                state.OkUtc = utc;
            }
            else
            {
                Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=ok_receipt_no_anchor");
            }
        }
        state.Gen = state.Ok;
        if (genMax > state.Ok)
        {
            if (HCReadReceipt(siteId + ".gen-" + genMax.ToString(), "HC-POLICE-GEN", genMax, utc, items, barrelId, kind))
            {
                state.Gen = genMax;
                state.GenUtc = utc;
                state.GenItems = items;
                state.GenKind = kind;
                state.GenId = state.Id;
                // A replace/recreate generation recorded the id of the barrel it created (bar-N).
                if (kind != "refill")
                {
                    state.GenId = "";
                    if (HCReadReceipt(siteId + ".bar-" + genMax.ToString(), "HC-POLICE-BAR", genMax, utc, items, barrelId, kind)) { state.GenId = barrelId; }
                }
            }
            else
            {
                Print("[HC Police] site=" + siteId + " action=receipt_unreadable reason=gen_receipt_torn_ignored");
            }
        }
        // Best-effort prune of superseded receipts; torn higher files are pruned by a later generation.
        foreach (string stale : names)
        {
            int staleGen = HCEpochOf(siteId, stale, "gen-");
            if (staleGen > 0 && state.Ok > 0 && (staleGen < state.Ok || (staleGen == state.Ok && okReadable))) { HCPrune(stale); }
            int staleOk = HCEpochOf(siteId, stale, "ok-");
            if (staleOk > 0 && staleOk < state.Ok) { HCPrune(stale); }
            int staleBar = HCEpochOf(siteId, stale, "bar-");
            if (staleBar > 0 && staleBar <= state.Ok) { HCPrune(stale); }
        }
        m_Generations.Insert(siteId, state);
        return state;
    }
    // Cooldown and lifetime anchor: the last create/refill time from the durable receipt (0 = none).
    int HCEpochAnchor(HCPoliceGeneration state)
    {
        if (state.Gen > state.Ok) { return state.GenUtc; }
        return state.OkUtc;
    }
    // Writes a completed-generation marker that is not tied to an open gen: legacy migration,
    // first creation ("initial") or re-arm after a missing/future-dated anchor ("rearm").
    // barrelId is the exact identity to record ("" = unknown). utc = now.
    bool HCEpochMark(string siteId, HCPoliceGeneration state, int now, string kind, string barrelId)
    {
        if (!m_IO || m_Fault || now < 1 || state.Num >= 1000000000) { return false; }
        int next = state.Num + 1;
        string text = "HC-POLICE-OK v1 " + siteId + " gen " + next.ToString() + " utc " + now.ToString() + " kind " + kind + " items 0";
        if (barrelId != "") { text = text + " id " + barrelId; }
        if (!m_IO.WriteNew(siteId + ".ok-" + next.ToString(), text, 256)) { Fault(); return false; }
        state.Num = next;
        state.Ok = next;
        state.Gen = next;
        state.OkUtc = now;
        state.GenUtc = 0;
        state.GenItems = 0;
        state.Id = barrelId;
        return true;
    }
    // Durable intent, written BEFORE any native create/delete/item of this generation.
    bool HCEpochBegin(string siteId, HCPoliceGeneration state, int now, string kind, int items, string carryId)
    {
        if (!m_IO || m_Fault || now < 1 || items < 1 || state.Num >= 1000000000) { return false; }
        int next = state.Num + 1;
        string text = "HC-POLICE-GEN v1 " + siteId + " gen " + next.ToString() + " utc " + now.ToString() + " kind " + kind + " items " + items.ToString();
        if (!m_IO.WriteNew(siteId + ".gen-" + next.ToString(), text, 256)) { Fault(); return false; }
        int prior = state.Gen;
        bool priorIncomplete = state.Gen > state.Ok;
        state.Num = next;
        state.Gen = next;
        state.GenUtc = now;
        state.GenItems = items;
        state.GenKind = kind;
        state.GenId = "";
        if (kind == "refill") { state.GenId = carryId; }
        if (priorIncomplete)
        {
            HCPrune(siteId + ".gen-" + prior.ToString());
            HCPrune(siteId + ".bar-" + prior.ToString());
        }
        return true;
    }
    // Identity of the barrel a replace/recreate generation just created, written BEFORE its items
    // so a crash mid-fill leaves a barrel the next boot can recognise as its own.
    bool HCEpochBarrel(string siteId, HCPoliceGeneration state, int now, string barrelId)
    {
        if (!m_IO || m_Fault || state.Gen <= state.Ok || barrelId == "") { return false; }
        string text = "HC-POLICE-BAR v1 " + siteId + " gen " + state.Gen.ToString() + " utc " + now.ToString() + " kind " + state.GenKind + " items 0 id " + barrelId;
        if (!m_IO.WriteNew(siteId + ".bar-" + state.Gen.ToString(), text, 256)) { Fault(); return false; }
        state.GenId = barrelId;
        return true;
    }
    // Completion marker for the open generation; carries the generation utc as the anchor and the
    // exact barrel identity of the generation ("" = unknown).
    bool HCEpochComplete(string siteId, HCPoliceGeneration state, string kind, int now, string barrelId)
    {
        if (!m_IO || m_Fault || state.Gen <= state.Ok) { return false; }
        int generation = state.Gen;
        int utc = state.GenUtc;
        if (utc < 1) { utc = now; }
        int items = state.GenItems;
        string text = "HC-POLICE-OK v1 " + siteId + " gen " + generation.ToString() + " utc " + utc.ToString() + " kind " + kind + " items " + items.ToString();
        if (barrelId != "") { text = text + " id " + barrelId; }
        if (!m_IO.WriteNew(siteId + ".ok-" + generation.ToString(), text, 256)) { Fault(); return false; }
        int priorOk = state.Ok;
        state.Ok = generation;
        state.OkUtc = utc;
        state.Id = barrelId;
        HCPrune(siteId + ".gen-" + generation.ToString());
        HCPrune(siteId + ".bar-" + generation.ToString());
        if (priorOk > 0) { HCPrune(siteId + ".ok-" + priorOk.ToString()); }
        return true;
    }

    bool CachePosition(string siteId, out vector position)
    {
        position = vector.Zero;
        if (!m_IO || m_Fault || !m_IO.Exists(siteId + ".pos")) { return false; }
        string text = m_IO.Read(siteId + ".pos", 96);
        if (text == "") { return false; }
        text.Trim();
        position = text.ToVector();
        return position != vector.Zero;
    }
}
// Native: 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition, :65 PGFilter.SetFlags;
// Game.c GetWorld().GetAIWorld(). Outdoor walkable polygons only (INSIDE excluded).
class HCEventPoliceNav
{
    static vector Sample(vector wanted, float radius)
    {
        if (!GetGame() || !GetGame().GetWorld()) { return vector.Zero; }
        AIWorld world = GetGame().GetWorld().GetAIWorld();
        if (!world) { return vector.Zero; }
        PGFilter filter = new PGFilter;
        filter.SetFlags(PGPolyFlags.WALK, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.INSIDE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        vector found;
        if (!world.SampleNavmeshPosition(wanted, radius, filter, found)) { return vector.Zero; }
        return found;
    }
}
// Retain native query order with a capped cargo handle snapshot per container.
// No inventory is cloned; fallbacks start only after the full capped scan.
class HCEventPoliceStockSlice
{
    ref array<Object> Nearby;
    int Next;
    int Stage;
    Barrel_Green OwnedCache;
    vector OwnedPosition;
    bool HasOwnedPosition;
    bool GroundBarrelPresent;
    // Any live barrel within 2 m of the recorded position (ruined or not).
    Barrel_Green NearBarrel;
    ItemBase GroundItem;
    ItemBase DeliveryContainer;
    ItemBase CargoOwner;
    int CargoNext;
    ref array<ItemBase> CargoItems;
}
class HCEventCacheSpawner
{
    // Upper bound for the native physical-stock sphere around a mission source (metres).
    static const float SCAN_RADIUS_MAX = 25;
    protected static ref map<string, ref HCEventPoliceStockSlice> s_StockSlices = new map<string, ref HCEventPoliceStockSlice>;
    protected static ref HCEventRewardLedger s_PoliceLedger;
    protected static ref array<string> s_PoliceLogged = new array<string>;
    protected static ref array<ref HCEventTarget> s_PoliceTargets;

    protected static int s_PoliceQueryPeak;
    protected static int s_CacheQueryPeak;
    // The native query allocates the entire sphere before returning. Isolate
    // its peak from inspection/cargo/ledger work without changing stock order,
    // overflow refusal, radius, retry semantics or the durability barrier.
    static void HCStockQueryCost(int began, bool police)
    {
        int cost = TickCount(began);
        string consumer = "SITUATIONS";
        if (police)
        {
            if (cost <= s_PoliceQueryPeak) { return; }
            s_PoliceQueryPeak = cost;
            consumer = "POLICE_BIND";
        }
        else
        {
            if (cost <= s_CacheQueryPeak) { return; }
            s_CacheQueryPeak = cost;
        }
        if (cost >= 40000)
        {
            Print("[HC Events] stock_query consumer=" + consumer + " ticks_max=" + cost.ToString() + " atomic=1 runtime=PENDING");
        }
    }

    protected static string s_PoliceReason;
    protected static string s_PoliceDetails;

    static string PoliceReason() { return s_PoliceReason; }
    static string PoliceDetails() { return s_PoliceDetails; }
    static void PoliceRefused(string reason, string details = "")
    {
        s_PoliceReason = reason;
        s_PoliceDetails = details;
    }

    static HCEventRewardLedger PoliceLedger()
    {
        if (!s_PoliceLedger)
        {
            HCEventRewardPool pool = new HCEventRewardPool;
            pool.MaxCaches = 2;
            pool.ItemsPerCache = 3;
            pool.Entries.Insert(HCEventRewardPools.Entry("BandageDressing", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("SodaCan_Cola", 2));
            pool.Entries.Insert(HCEventRewardPools.Entry("MetalWire", 2));
            s_PoliceLedger = new HCEventPoliceStockLedger;
            HCEventPoliceRewardIO policeIO = new HCEventPoliceRewardIO;
            s_PoliceLedger.Configure(policeIO, pool);
        }
        return s_PoliceLedger;
    }
    static HCEventTarget PoliceTarget(string missionId)
    {
        if (!s_PoliceTargets) { return null; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.MissionId == missionId) { return target; }
        }
        return null;
    }
    static HCEventTarget CreatePolice(HCEventMission mission)
    {
        PoliceRefused("");
        if (!HCEventSites.PoliceSupplies(mission)) { PoliceRefused("police_mission_mismatch"); return null; }
        if (!HCEventSitesGate.Admitted()) { PoliceRefused("police_gate_closed"); return null; }
        if (!GetGame() || !GetGame().IsServer()) { PoliceRefused("police_server_unavailable"); return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { PoliceRefused("police_mission_invalid"); return null; }
        HCEventTarget existing = PoliceTarget(mission.Id);
        if (existing) { return existing; }
        // Keep the CE lookup at the exact origin; only the HC fallback uses navmesh.
        SpawnPoliceSlice(mission);
        return PoliceTarget(mission.Id);
    }
    static HCEventTarget Create(HCEventMission mission)
    {
        if (!mission || !mission.RewardCache || mission.Family != HCEventFamily.RECOVERY) { return null; }
        if (!HCEventSitesGate.Admitted() || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { return null; }
        return Spawn(mission, mission.Source, mission.ItemClass, false);
    }
    // Used only for newly reserved HC stock; never moves existing world stock.
    static vector SpawnPosition(HCEventMission mission, vector anchor, bool police)
    {
        if (police) { PoliceRefused(""); }
        if (!mission) { if (police) { PoliceRefused("police_mission_invalid"); } return vector.Zero; }
        if (!GetGame() || !GetGame().IsServer()) { if (police) { PoliceRefused("police_server_unavailable"); } return vector.Zero; }
        float height = GetGame().SurfaceY(anchor[0], anchor[2]);
        if (height != height)
        {
            if (police) { PoliceRefused("police_terrain_unavailable"); }
            if (!police) { Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height"); }
            return vector.Zero;
        }
        vector position;
        if (police)
        {
            // Police Source is the station's stock mapgrouppos model origin, which stands
            // above its ground (stock neighbours sit ~5 m lower). Accept ground up to 12 m
            // below it, then take an outdoor walkable navmesh point so the barrel is not
            // inside a wall. Retries report through BindFailed's bounded (mission, reason) set.
            if (height > mission.Source[1] + 3 || height < mission.Source[1] - 12)
            {
                PoliceRefused("police_terrain_height", "; h=" + height.ToString() + "; src=" + mission.Source[1].ToString());
                return vector.Zero;
            }
            position = HCEventPoliceNav.Sample(Vector(anchor[0], height, anchor[2]), 6);
            if (position == vector.Zero) { PoliceRefused("police_navmesh_none"); return vector.Zero; }
        }
        else
        {
            if (Math.AbsFloat(height - mission.Source[1]) > 6)
            {
                Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height");
                return vector.Zero;
            }
            position = Vector(anchor[0], height, anchor[2]);
        }
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius)
        {
            if (police) { PoliceRefused("police_position_outside_radius"); }
            return vector.Zero;
        }
        return position;
    }
    // One shared admission owner for stock and infected bind continuations.
    // Their roster slot is serialized by HCEventModule, so they cannot consume
    // each other's sole starvation grant in the same refresh.
    static bool PoliceWork()
    {
        return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_POLICE_BIND, 8);
    }

    static HCEventTarget SpawnPoliceSlice(HCEventMission mission)
    {
        PoliceRefused("police_work_budget");
        if (!HCPhysicalEnabled()) { PoliceRefused("police_physical_disabled"); return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        if (!policy) { PoliceRefused("police_policy_invalid"); return null; }
        if (!PoliceWork()) { return null; }
        HCEventPoliceStockSlice job = s_StockSlices.Get(mission.Id);
        if (!job)
        {
            job = new HCEventPoliceStockSlice;
            job.Nearby = new array<Object>;
            array<CargoBase> proxies = new array<CargoBase>;
            int began = TickCount(0);
            GetGame().GetObjectsAtPosition3D(mission.Source, Math.Min(mission.Radius, SCAN_RADIUS_MAX), job.Nearby, proxies);
            HCStockQueryCost(began, true);
            s_StockSlices.Set(mission.Id, job);
            return null;
        }
        if (job.Stage == 0)
        {
            HCEventPoliceStockLedger ledger = HCEventPoliceStockLedger.Cast(PoliceLedger());
            job.HasOwnedPosition = ledger && ledger.CachePosition(mission.SiteId, job.OwnedPosition);
            job.Stage = 1;
            return null;
        }
        if (job.Stage == 1)
        {
            array<string> classes = HCW38SituationPolicy.PoliceClasses(mission.Family);
            HCWorkBudget slice = new HCWorkBudget;
            slice.HCReset(32, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
            while (slice.HCContinue())
            {
                if (job.CargoOwner)
                {
                    ItemBase cargoOwner = job.CargoOwner;
                    // Validate the retained owner before any native inventory access.
                    if (!HCPhysicalGround(cargoOwner) || vector.DistanceSq(cargoOwner.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    CargoBase cargo;
                    if (cargoOwner.GetInventory()) { cargo = cargoOwner.GetInventory().GetCargo(); }
                    if (!cargo)
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    if (!job.CargoItems)
                    {
                        // One grant snapshots at most 64 weak item handles in
                        // native order. No yield can shift indices mid-copy.
                        job.CargoItems = new array<ItemBase>;
                        int cargoCount = Math.Min(cargo.GetItemCount(), policy.PhysicalScanCargo);
                        for (int cargoIndex = 0; cargoIndex < cargoCount; cargoIndex++)
                        {
                            job.CargoItems.Insert(ItemBase.Cast(cargo.GetItem(cargoIndex)));
                        }
                        return null;
                    }
                    if (job.CargoNext >= job.CargoItems.Count())
                    {
                        job.CargoOwner = null;
                        job.CargoItems = null;
                        continue;
                    }
                    ItemBase item = job.CargoItems[job.CargoNext];
                    job.CargoNext++;
                    if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
                    if (item.GetHierarchyParent() != cargoOwner || !PoliceItemMatches(item, mission, classes) || PoliceItemUsed(item)) { continue; }
                    if (mission.Family == HCEventFamily.DELIVERY && !PoliceDeliveryValid(mission, job.DeliveryContainer)) { continue; }
                    s_StockSlices.Remove(mission.Id);
                    if (mission.Family == HCEventFamily.DELIVERY) { return RememberPolice(mission, item, job.DeliveryContainer); }
                    return RememberPolice(mission, item, cargoOwner);
                }
                if (job.Next >= job.Nearby.Count() || job.Next >= policy.PhysicalScanObjects)
                {
                    job.Stage = 2;
                    return null;
                }
                ItemBase cache = ItemBase.Cast(job.Nearby[job.Next]);
                job.Next++;
                // Even a ruined ground barrel blocks repair; it may be the old HC cache.
                Barrel_Green nearbyBarrel = Barrel_Green.Cast(cache);
                if (!job.GroundBarrelPresent && nearbyBarrel && !nearbyBarrel.IsSetForDeletion() && !nearbyBarrel.GetHierarchyParent() && !nearbyBarrel.GetHierarchyRootPlayer() && vector.DistanceSq(nearbyBarrel.GetPosition(), mission.Source) <= mission.Radius * mission.Radius)
                {
                    job.GroundBarrelPresent = true;
                    HCEventPoliceStockLedger barrelLedger = HCEventPoliceStockLedger.Cast(PoliceLedger());
                    if (barrelLedger) { barrelLedger.HCRepairOrphan(mission.SiteId, true); }
                }
                // A barrel (even ruined) at the recorded position is the site container.
                if (nearbyBarrel && job.HasOwnedPosition && !nearbyBarrel.IsSetForDeletion() && !nearbyBarrel.GetHierarchyParent() && vector.DistanceSq(nearbyBarrel.GetPosition(), job.OwnedPosition) <= 4) { job.NearBarrel = nearbyBarrel; }
                if (!HCPhysicalGround(cache)) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
                Barrel_Green tagged = Barrel_Green.Cast(cache);
                if (tagged && job.HasOwnedPosition && vector.DistanceSq(tagged.GetPosition(), job.OwnedPosition) <= 4) { job.OwnedCache = tagged; }
                if (!job.GroundItem && PoliceItemMatches(cache, mission, classes) && !PoliceItemUsed(cache)) { job.GroundItem = cache; }
                if (cache.GetType() != mission.ContainerClass || !cache.GetInventory() || !cache.GetInventory().GetCargo()) { continue; }
                if (vector.DistanceSq(cache.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius) { job.DeliveryContainer = cache; }
                job.CargoOwner = cache;
                job.CargoNext = 0;
                job.CargoItems = null;
                // Isolate the bounded snapshot from object inspection work.
                return null;
            }
            return null;
        }
        if (job.Stage == 2)
        {
            // A retained ground item may have been picked up between grants.
            // Refuse that attempt rather than borrowing a different target.
            if (job.GroundItem && (!HCPhysicalGround(job.GroundItem) || PoliceItemUsed(job.GroundItem) || vector.DistanceSq(job.GroundItem.GetPosition(), mission.Source) > mission.Radius * mission.Radius))
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_target_changed");
                return null;
            }
            if (job.DeliveryContainer && !PoliceDeliveryValid(mission, job.DeliveryContainer))
            {
                if (mission.Family == HCEventFamily.DELIVERY)
                {
                    s_StockSlices.Remove(mission.Id);
                    PoliceRefused("police_target_changed");
                    return null;
                }
                job.DeliveryContainer = null;
            }
            if (job.GroundItem && (mission.Family != HCEventFamily.DELIVERY || PoliceDeliveryValid(mission, job.DeliveryContainer)))
            {
                s_StockSlices.Remove(mission.Id);
                return RememberPolice(mission, job.GroundItem, job.DeliveryContainer);
            }
            if (job.Nearby.Count() > policy.PhysicalScanObjects)
            {
                s_StockSlices.Remove(mission.Id);
                PoliceRefused("police_scan_limit", "; queried=" + job.Nearby.Count().ToString() + "; scan_cap=" + policy.PhysicalScanObjects.ToString());
                return null;
            }
            if (job.HasOwnedPosition)
            {
                // Recorded site: container lifecycle (refill, replace, recreate) or its stock.
                s_StockSlices.Remove(mission.Id);
                return PoliceContainer(mission, job);
            }
            HCEventPoliceStockLedger repairLedger = HCEventPoliceStockLedger.Cast(PoliceLedger());
            if (repairLedger) { repairLedger.HCRepairOrphan(mission.SiteId, job.GroundBarrelPresent); }
            // No native creation handle or partially initialized cache crosses a grant.
            s_StockSlices.Remove(mission.Id);
            Barrel_Green created = CreatePoliceStock(mission);
            if (created) { return PoliceStockTarget(mission, created); }
            return null;
        }
        return null;
    }

    // Container lifecycle, owner 2026-11-22. Runs on police bind attempts inside the
    // PoliceWork grant of SpawnPoliceSlice (no separate timer); one create per grant.
    // Every generation (refill, replace, recreate) is gated on RefillCooldownSeconds read
    // from the durable receipt, so a carried-off or looted container cannot be farmed by
    // restarting, and on no player within RefillClearRadius of the recorded position.
    // Only the barrel whose persistent id is in the ok receipt, holding only untouched plan
    // items, is ever drained or deleted; any other barrel at the record is left alone and the
    // site waits (police_container_not_ours). Native: EntityAI.c:3374 GetPersistentID,
    // Inventory.c:205 AttachmentCount, :138 GetCargo; Cargo.c GetItemCount/GetItem.
    // The empty-container pickup (Barrel_ColorBase.c CanPutIntoHands) is not blocked: an HC
    // Barrel_Green subclass needs a config class and CE types entry, unverified here.
    static int PoliceCargoCount(Barrel_Green barrel)
    {
        if (!barrel || !barrel.GetInventory()) { return -1; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return -1; }
        return cargo.GetItemCount();
    }
    // "" = unknown (zero id or no barrel). The id is recorded in the ok receipt.
    static string PoliceBarrelId(Barrel_Green barrel)
    {
        int b1;
        int b2;
        int b3;
        int b4;
        if (!barrel) { return ""; }
        barrel.GetPersistentID(b1, b2, b3, b4);
        if (b1 == 0 && b2 == 0 && b3 == 0 && b4 == 0) { return ""; }
        return b1.ToString() + " " + b2.ToString() + " " + b3.ToString() + " " + b4.ToString();
    }
    // 1 = the recorded id matches; 0 = no id recorded for this site; -1 = another barrel.
    // An open replace/recreate generation uses the id its own bar-N receipt recorded.
    static string PoliceExpectedId(HCPoliceGeneration state)
    {
        if (state.Gen > state.Ok) { return state.GenId; }
        return state.Id;
    }
    static int PoliceOwnership(Barrel_Green barrel, HCPoliceGeneration state)
    {
        string expected = PoliceExpectedId(state);
        if (expected == "") { return 0; }
        if (PoliceBarrelId(barrel) == expected) { return 1; }
        return -1;
    }
    static void PoliceLogOnce(string siteId, string reason)
    {
        string key = siteId + ":" + reason;
        if (s_PoliceLogged.Count() >= 16 || s_PoliceLogged.Find(key) >= 0) { return; }
        s_PoliceLogged.Insert(key);
        Print("[HC Police] site=" + siteId + " action=replace_refused reason=" + reason);
    }
    static bool PoliceInPlan(HCEventRewardPlan plan, string className)
    {
        return plan.Items.Find(className) >= 0;
    }
    // "" = every cargo item is an untouched plan item of this barrel (no cargo or attachments of
    // its own, count within the plan size, none reserved by a police event); otherwise the reason.
    static string PoliceCargoRefusal(Barrel_Green barrel, HCEventRewardPlan plan)
    {
        if (!barrel || !barrel.GetInventory()) { return "player_items"; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return "player_items"; }
        int count = cargo.GetItemCount();
        if (count > plan.Items.Count()) { return "player_items"; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.GetHierarchyParent() != barrel || !PoliceInPlan(plan, item.GetType())) { return "player_items"; }
            GameInventory inner = item.GetInventory();
            if (inner && inner.AttachmentCount() > 0) { return "player_items"; }
            CargoBase innerCargo = null;
            if (inner) { innerCargo = inner.GetCargo(); }
            if (innerCargo && innerCargo.GetItemCount() > 0) { return "player_items"; }
            if (PoliceItemUsed(item)) { return "item_reserved"; }
        }
        return "";
    }
    static bool PolicePlayersWithin(vector position, float radius)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        int count = players.Count();
        if (count > 64) { count = 64; }
        for (int index = 0; index < count; index++)
        {
            Man player = players[index];
            if (!player || !player.IsAlive()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), position) <= radius * radius) { return true; }
        }
        return false;
    }
    // Deletes the cargo of a barrel PoliceCargoRefusal already verified (at most the plan size).
    static void PoliceDrain(Barrel_Green barrel)
    {
        if (!barrel || !barrel.GetInventory()) { return; }
        CargoBase cargo = barrel.GetInventory().GetCargo();
        if (!cargo) { return; }
        int count = cargo.GetItemCount();
        for (int index = count - 1; index >= 0; index--)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsSetForDeletion() || item.GetHierarchyParent() != barrel) { continue; }
            GetGame().ObjectDelete(item);
        }
    }
    static bool PoliceFillCargo(Barrel_Green cache, HCEventRewardPlan plan)
    {
        // Native: ItemBase/Barrel_ColorBase.c:87 Open, :512 cargo requires IsOpen.
        cache.Open();
        foreach (string itemClass : plan.Items)
        {
            // Preserve 60a261e3: never delete the cache or its cargo on failure here;
            // the open receipt makes the next generation discard a partial one.
            if (!HCPhysicalGround(cache) || !cache.IsOpen() || !cache.GetInventory() || !cache.GetInventory().CreateInInventory(itemClass)) { return false; }
        }
        return true;
    }
    static HCEventTarget PoliceContainer(HCEventMission mission, HCEventPoliceStockSlice job)
    {
        Barrel_Green cache = job.OwnedCache;
        Barrel_Green barrel = cache;
        if (!barrel) { barrel = job.NearBarrel; }
        HCEventPoliceStockLedger ledger = HCEventPoliceStockLedger.Cast(PoliceLedger());
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        vector recorded;
        HCPoliceGeneration state;
        HCEventRewardPlan plan;
        int now = HCInfectedClock.UtcSeconds();
        bool ready = ledger && policy && now > 0 && GetGame() && GetGame().IsServer();
        if (ready) { ready = ledger.HCBarrelRecordPosition(mission.SiteId, recorded); }
        if (ready)
        {
            state = ledger.HCGeneration(mission.SiteId);
            ready = state != null;
        }
        if (ready) { plan = ledger.HCFreshPlan(mission.SiteId); }
        if (ready && state.Num < 1)
        {
            // Old record without receipts: migrate in place; the cooldown starts now. The identity
            // of the barrel found is recorded only when it holds nothing but untouched plan items.
            string legacyId = "";
            if (barrel && PoliceCargoRefusal(barrel, plan) == "") { legacyId = PoliceBarrelId(barrel); }
            if (ledger.HCEpochMark(mission.SiteId, state, now, "migrate", legacyId)) { Print("[HC Police] site=" + mission.SiteId + " action=ledger_migrated reason=legacy_record"); }
            ready = state.Ok > 0;
        }
        int anchor = 0;
        if (ready) { anchor = ledger.HCEpochAnchor(state); }
        if (ready && (anchor < 1 || anchor > now + 86400))
        {
            // No readable or a future-dated anchor: re-arm durably (ok-(max+1), utc now) so recovery
            // takes exactly one cooldown across restarts. The recorded identity is carried over.
            Print("[HC Police] site=" + mission.SiteId + " action=receipt_rearmed reason=anchor_unusable");
            ready = ledger.HCEpochMark(mission.SiteId, state, now, "rearm", state.Id);
            anchor = now;
        }
        if (!ready)
        {
            // Lifecycle unavailable (clock, record or receipt IO): stock lookup only.
            if (cache) { return PoliceStockTarget(mission, cache); }
            PoliceRefused("police_cache_position_recorded");
            return null;
        }
        int remaining = policy.RefillCooldownSeconds - (now - anchor);
        bool cooled = remaining <= 0;
        if (!barrel)
        {
            if (!cooled) { PoliceRefused("police_container_cooldown", "; wait_s=" + remaining.ToString()); return null; }
            if (PolicePlayersWithin(recorded, policy.RefillClearRadius)) { PoliceRefused("police_container_players_near"); return null; }
            return PoliceGenerate(mission, state, recorded, null, "recreate", "missing_entity", now);
        }
        int ownership = PoliceOwnership(barrel, state);
        if (ownership < 0)
        {
            // A different barrel stands on the record (for example a player's own): never touched.
            PoliceLogOnce(mission.SiteId, "not_ours");
            PoliceRefused("police_container_not_ours");
            return null;
        }
        string cargoRefusal = PoliceCargoRefusal(barrel, plan);
        int count = PoliceCargoCount(barrel);
        string keepId = PoliceExpectedId(state);
        if (keepId == "") { keepId = PoliceBarrelId(barrel); }
        bool incomplete = state.Gen > state.Ok;
        if (cache && incomplete && count >= 0 && cargoRefusal == "")
        {
            // A generation that crashed after its items but before its marker is completed,
            // never regenerated: its items are present.
            int planned = state.GenItems;
            if (planned < 1) { planned = plan.Items.Count(); }
            if (count >= planned && ledger.HCEpochComplete(mission.SiteId, state, "resume", now, keepId))
            {
                Print("[HC Police] site=" + mission.SiteId + " action=generation_completed reason=items_present");
                incomplete = false;
            }
        }
        if (!cache)
        {
            // Ruined barrel at the record: replace only our own, untouched one.
            if (!cooled) { PoliceRefused("police_container_cooldown", "; wait_s=" + remaining.ToString()); return null; }
            if (PolicePlayersWithin(recorded, policy.RefillClearRadius)) { PoliceRefused("police_container_players_near"); return null; }
            if (ownership != 1) { PoliceLogOnce(mission.SiteId, "not_ours"); PoliceRefused("police_container_not_ours"); return null; }
            if (cargoRefusal != "") { PoliceLogOnce(mission.SiteId, cargoRefusal); PoliceRefused("police_container_not_ours"); return null; }
            return PoliceGenerate(mission, state, recorded, barrel, "replace", "ruined", now);
        }
        bool expired = !incomplete && (now - anchor) >= policy.ContainerLifetimeSeconds;
        bool empty = count == 0;
        if ((empty || incomplete || expired) && cooled && !PolicePlayersWithin(recorded, policy.RefillClearRadius))
        {
            // Never add to a container that still holds items: only an empty one refills in place.
            if (empty) { return PoliceGenerate(mission, state, recorded, barrel, "refill", "depleted", now); }
            string why = "lifetime";
            if (incomplete) { why = "incomplete_generation"; }
            if (ownership != 1) { PoliceLogOnce(mission.SiteId, "not_ours"); }
            else if (cargoRefusal != "") { PoliceLogOnce(mission.SiteId, cargoRefusal); }
            else { return PoliceGenerate(mission, state, recorded, barrel, "replace", why, now); }
        }
        return PoliceStockTarget(mission, cache);
    }
    // kind: refill (in place), replace (drain + delete + create), recreate (missing: create).
    // Callers verified identity and cargo before any replace.
    static HCEventTarget PoliceGenerate(HCEventMission mission, HCPoliceGeneration state, vector position, Barrel_Green old, string kind, string reason, int now)
    {
        if (vector.DistanceSq(position, mission.Source) > mission.Radius * mission.Radius) { PoliceRefused("police_position_outside_radius"); return null; }
        HCEventPoliceStockLedger ledger = HCEventPoliceStockLedger.Cast(PoliceLedger());
        HCEventRewardPlan plan = ledger.HCFreshPlan(mission.SiteId);
        // Durable receipt first: a crash after it loses one generation, never doubles one.
        string barrelId = PoliceExpectedId(state);
        if (!ledger.HCEpochBegin(mission.SiteId, state, now, kind, plan.Items.Count(), barrelId)) { PoliceRefused("police_receipt_write_failed"); return null; }
        Barrel_Green barrel = old;
        if (kind != "refill")
        {
            if (old)
            {
                PoliceDrain(old);
                GetGame().ObjectDelete(old);
            }
            barrel = Barrel_Green.Cast(GetGame().CreateObjectEx("Barrel_Green", position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS));
            if (!barrel) { PoliceRefused("police_cache_create_failed"); return null; }
            HCGroundSnap.Snap(barrel);
            if (vector.DistanceSq(barrel.GetPosition(), position) > 4)
            {
                // The new barrel is still empty: delete it; the open receipt retries after a cooldown.
                GetGame().ObjectDelete(barrel);
                PoliceRefused("police_cache_position_drift");
                return null;
            }
            barrelId = PoliceBarrelId(barrel);
            if (barrelId != "" && !ledger.HCEpochBarrel(mission.SiteId, state, now, barrelId))
            {
                GetGame().ObjectDelete(barrel);
                PoliceRefused("police_receipt_write_failed");
                return null;
            }
        }
        else if (barrelId == "")
        {
            barrelId = PoliceBarrelId(barrel);
        }
        if (!PoliceFillCargo(barrel, plan)) { PoliceRefused("police_cache_cargo_failed"); return null; }
        ledger.HCEpochComplete(mission.SiteId, state, kind, now, barrelId);
        if (kind == "refill")
        {
            Print("[HC Police] site=" + mission.SiteId + " action=refilled reason=" + reason);
            HCModuleReadiness.HCUse("Events", "container_refilled");
        }
        else if (kind == "recreate")
        {
            Print("[HC Police] site=" + mission.SiteId + " action=barrel_recreated reason=" + reason);
            HCModuleReadiness.HCUse("Events", "police_barrel_recreated");
        }
        else
        {
            Print("[HC Police] site=" + mission.SiteId + " action=replaced reason=" + reason);
            HCModuleReadiness.HCUse("Events", "container_replaced");
        }
        return PoliceStockTarget(mission, barrel);
    }

    // Restore the pre-slicing creation order (4b12d4f0) within one PoliceWork grant.
    // The plan is fixed at three items; only the capped world/cargo scan yields.
    static Barrel_Green CreatePoliceStock(HCEventMission mission)
    {
        vector position = SpawnPosition(mission, mission.Source, true);
        if (position == vector.Zero) { return null; }
        HCEventRewardLedger stockLedger = PoliceLedger();
        HCEventRewardPlan plan = stockLedger.Commit(mission.SiteId);
        if (!plan) { PoliceRefused(stockLedger.Refusal()); return null; }
        Barrel_Green cache = Barrel_Green.Cast(GetGame().CreateObjectEx("Barrel_Green", position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS));
        if (!cache) { PoliceRefused("police_cache_create_failed"); return null; }
        HCGroundSnap.Snap(cache);
        HCEventPoliceStockLedger owner = HCEventPoliceStockLedger.Cast(PoliceLedger());
        if (!owner || !owner.RecordCache(mission.SiteId, cache.GetPosition()))
        {
            // Reservation already spent; an unrecorded cache is still finite native loot.
            Print("[HC Events] police cache position not recorded; " + mission.SiteId + " runtime=PENDING");
        }
        if (!PoliceFillCargo(cache, plan))
        {
            PoliceRefused("police_cache_cargo_failed");
            return null;
        }
        // Start the lifecycle clock; a crash before this write migrates at the next boot.
        int createdUtc = HCInfectedClock.UtcSeconds();
        HCPoliceGeneration createdState;
        if (owner) { createdState = owner.HCGeneration(mission.SiteId); }
        if (createdState && createdState.Num < 1 && createdUtc > 0) { owner.HCEpochMark(mission.SiteId, createdState, createdUtc, "initial", PoliceBarrelId(cache)); }
        Print("[HC Events] police cache created; " + mission.SiteId + "; stock=finite_until_depleted; refill=after_cooldown runtime=PENDING");
        return cache;
    }

    static bool PoliceDeliveryValid(HCEventMission mission, ItemBase container)
    {
        if (!HCPhysicalGround(container) || container.GetType() != mission.ContainerClass || !container.GetInventory() || !container.GetInventory().GetCargo()) { return false; }
        return vector.DistanceSq(container.GetPosition(), mission.Source) <= mission.Radius * mission.Radius && vector.DistanceSq(container.GetPosition(), mission.Destination) <= mission.Radius * mission.Radius;
    }

    static HCEventTarget Spawn(HCEventMission mission, vector anchor, string containerClass, bool police)
    {
        // Police owns a retained job; ordinary recovery keeps its bounded lookup.
        if (police) { return SpawnPoliceSlice(mission); }
        if (!mission || !GetGame() || !GetGame().IsServer() || !HCEventSitesGate.Admitted() || !HCPhysicalEnabled()) { return null; }
        HCW38SituationPolicy policy = HCW38SituationPolicy.HCGet();
        int consumer = HCUnitBudget.HC_WORK_SITUATIONS;
        if (!policy || !HCServer.HCTickWork().HCTakeFor(consumer, 8)) { return null; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        int began = TickCount(0);
        GetGame().GetObjectsAtPosition3D(anchor, Math.Min(mission.Radius, SCAN_RADIUS_MAX), nearby, proxies);
        HCStockQueryCost(began, false);
        int remaining = policy.PhysicalScanObjects;
        foreach (Object candidate : nearby)
        {
            if (remaining <= 0) { break; }
            remaining--;
            ItemBase cache = ItemBase.Cast(candidate);
            if (!HCPhysicalGround(cache) || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius) { continue; }
            if (!HCPhysicalStock(cache) || cache.GetType() != containerClass) { continue; }
            HCEventTarget result = new HCEventTarget;
            result.MissionId = mission.Id;
            result.Item = cache;
            result.Presence = cache;
            return result;
        }
        HCPhysicalPending();
        return null;
    }

    static HCEventTarget PoliceStockTarget(HCEventMission mission, Barrel_Green cache)
    {
        // OwnedCache can come from an earlier scan grant: validate before dereference.
        if (!HCPhysicalGround(cache) || !cache.GetInventory() || vector.DistanceSq(cache.GetPosition(), mission.Source) > mission.Radius * mission.Radius)
        {
            PoliceRefused("police_target_changed");
            return null;
        }
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (!cargo) { PoliceRefused("police_cache_depleted"); return null; }
        int count = cargo.GetItemCount();
        if (count > 16) { count = 16; }
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(index));
            if (!item || item.IsSetForDeletion() || item.IsRuined() || item.GetHierarchyRootPlayer()) { continue; }
            if (item.GetHierarchyParent() != cache || item.GetType() != mission.ItemClass || PoliceItemUsed(item)) { continue; }
            return RememberPolice(mission, item, cache);
        }
        PoliceRefused("police_cache_depleted");
        return null;
    }

    // Exact configured classes only; retain the original wanted barrel item.
    static bool PoliceItemMatches(ItemBase item, HCEventMission mission, array<string> classes)
    {
        if (item.GetType() == mission.ItemClass) { return true; }
        return classes && classes.Find(item.GetType()) >= 0;
    }
    static bool PoliceItemUsed(ItemBase item)
    {
        if (!s_PoliceTargets) { return false; }
        foreach (HCEventTarget target : s_PoliceTargets)
        {
            if (target.Item == item) { return true; }
        }
        return false;
    }
    static HCEventTarget RememberPolice(HCEventMission mission, ItemBase item, ItemBase container)
    {
        HCEventTarget supply = new HCEventTarget;
        supply.MissionId = mission.Id;
        supply.Item = item;
        supply.DeliveryContainer = container;
        if (!s_PoliceTargets) { s_PoliceTargets = new array<ref HCEventTarget>; }
        s_PoliceTargets.Insert(supply);
        return supply;
    }
    // Rosters are rebuilt on retry. Pin the objective to the actual native class
    // before Announce so Ready and later inventory evidence retain exact matching.
    static void PoliceObjectiveClass(HCEventMission mission)
    {
        if (!HCEventSites.PoliceSupplies(mission)) { return; }
        HCEventTarget supply = PoliceTarget(mission.Id);
        if (supply && supply.Item && !supply.Item.IsSetForDeletion()) { mission.ItemClass = supply.Item.GetType(); }
    }
    static bool HCPhysicalGround(ItemBase item)
    {
        return item && !item.IsSetForDeletion() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && !item.GetHierarchyParent();
    }

    protected static bool s_PhysicalPendingPrinted;
    protected static bool s_PhysicalAdmissionPrinted;
    protected static bool s_PhysicalEnabled;
    static bool HCPhysicalEnabled()
    {
        // Operator marker is probed once per process, like the other acceptance markers.
        if (s_PhysicalAdmissionPrinted) { return s_PhysicalEnabled; }
        s_PhysicalAdmissionPrinted = true;
        s_PhysicalEnabled = !FileExist("$profile:HollowCountry/acceptance/w38_rewards.disable");
        Print(HCV2Admission.Line("PhysicalSpoils", s_PhysicalEnabled, "w38_rewards", false) + " runtime=PENDING");
        return s_PhysicalEnabled;
    }

    static void HCPhysicalPending()
    {
        if (s_PhysicalPendingPrinted) { return; }
        s_PhysicalPendingPrinted = true;
        Print("[HC Events] physical_stock=waiting EXISTING_CE_CAMP_STOCK_PENDING runtime=PENDING");
    }

    static bool HCPhysicalStock(ItemBase cache)
    {
        if (!cache || cache.IsSetForDeletion() || cache.IsRuined()) { return false; }
        if (cache.GetHierarchyRootPlayer() || cache.GetHierarchyParent() || !cache.GetInventory()) { return false; }
        CargoBase cargo = cache.GetInventory().GetCargo();
        return cargo && cargo.GetItemCount() > 0;
    }
    // Borrowed physical stock always stays with its native owner.
    static void Discard(ItemBase cache) {}
}
