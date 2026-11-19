// W5-PERF-5: <=one drop/60s; shared work guard before consuming its cursor.
// Durable crate creation, finite deposit and provenance barriers remain
// synchronous: deferring them without continuations risks replay.
// Native timing evidence: HCWorkBudget.c (Game.c:914).
// #117, finite authored dead drops. Native evidence: scripts-1.30.164289:
// 3_Game/Global/Game.c:1176 SurfaceY, :1188 SurfaceGetNormal, :1196/1197
// SurfaceIsSea/SurfaceIsPond; surface normal y >= cos(30deg) rejects steep sites; :930 GetObjectsAtPosition3D and :703
// CreateObjectEx via HCEncounterCacheIO; 3_Game/Entities/Object.c:287 GetPosition;
// 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove,
// :902 map.Set, :917 map.Contains; EntityAI.c:1248 EECargoOut (WoodenCrate bridge);
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print.
// HCEncounterStore uses the inspected HCWorldStore/HCSearchJson file primitives.
// Coordinates are OWN approximate hidden woodland spots, not surveyed geometry
// or acceptance evidence. Terrain height + collision refusal precede creation.
// HC-34 retires abstract remote harvesting. Existing provenance/history stays
// intact, in recoverable ordinary persistent vanilla crates. No refill.
// EXP-L4 persistence and EXP-L5 noise, native compile and two clients PENDING.
class HCDeadDropRow
{
    string Id;
    ref HCEncounterCache Cache = new HCEncounterCache;
    int Deposits;
    int NextDay;
    bool Quarantined;
    ref array<string> SurvivorDeposits = new array<string>;
}

class HCDeadDropState
{
    int Version = 1;
    ref array<ref HCDeadDropRow> Rows = new array<ref HCDeadDropRow>;
}

class HCDeadDrops : HCModule
{
    protected static HCDeadDrops s_Instance;
    protected ref HCEncounterStore<HCDeadDropState> m_Store;
    protected ref HCDeadDropState m_State;
    protected ref array<ref HCEncounterCacheIO> m_Caches = new array<ref HCEncounterCacheIO>;
    protected bool m_Ready;
    protected bool m_Dirty;
    protected int m_Next;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected float m_Elapsed;

    static HCDeadDrops Get() { if (s_Instance && s_Instance.m_Ready) { return s_Instance; } return null; }
    override string GetName() { return "DeadDrops"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    int Count() { if (!m_State) { return 0; } return m_State.Rows.Count(); }

    bool SaveChanged()
    {
        if (!m_Dirty) return true;
        if (!m_Store.Save(m_State)) { m_Ready = false; return false; }
        m_Dirty = false;
        return true;
    }

    static bool MayWithdraw(array<string> recorded, string itemId)
    {
        return recorded && itemId != "" && recorded.Find(itemId) >= 0;
    }

    static bool TheftAllowed(EntityAI container, string itemId)
    {
        HCDeadDrops module = Get();
        // Cannot classify a persisted dead drop while its owner is unavailable.
        if (!module || !container || itemId == "") return false;
        for (int theftIndex = 0; theftIndex < module.Count(); theftIndex++)
        {
            HCDeadDropRow known = module.m_State.Rows[theftIndex];
            if (known.Cache.EntityRef != "" && known.Cache.EntityRef == HCSearchSupplyRegistry.PersistentId(container))
                return MayWithdraw(known.SurvivorDeposits, itemId);
            if (vector.DistanceSq(known.Cache.Position, container.GetPosition()) <= 1) return false;
        }
        return true;
    }

    // Legacy provenance writer, retained for compatibility only. V2Visit now
    // refuses remote hops; never infer a new deposit from abstract progress.
    static bool RecordHouseDeposit(EntityAI destination, string itemId)
    {
        HCDeadDrops module = Get();
        if (!module) return true;
        for (int depositIndex = 0; depositIndex < module.Count(); depositIndex++)
        {
            if (module.Cache(depositIndex) != destination) continue;
            HCDeadDropRow deposit = module.m_State.Rows[depositIndex];
            if (itemId == "" || deposit.SurvivorDeposits.Count() >= 32) return false;
            if (deposit.SurvivorDeposits.Find(itemId) < 0)
            {
                deposit.SurvivorDeposits.Insert(itemId);
                module.m_Dirty = true;
            }
            return module.SaveChanged();
        }
        return true;
    }

    // Any cargo removal revokes provenance before a player can put it back.
    static void CargoRemoved(EntityAI container, EntityAI item)
    {
        HCDeadDrops module = Get();
        if (!module || !GetGame().IsServer() || !item) return;
        string itemId = HCSearchSupplyRegistry.PersistentId(item);
        for (int removalIndex = 0; removalIndex < module.Count(); removalIndex++)
        {
            HCDeadDropRow removed = module.m_State.Rows[removalIndex];
            if (module.m_Caches[removalIndex].Handle != container && (removed.Cache.EntityRef == "" || removed.Cache.EntityRef != HCSearchSupplyRegistry.PersistentId(container))) continue;
            int recordedIndex = module.m_State.Rows[removalIndex].SurvivorDeposits.Find(itemId);
            if (recordedIndex < 0) return;
            module.m_State.Rows[removalIndex].SurvivorDeposits.Remove(recordedIndex);
            module.m_Dirty = true;
            module.SaveChanged();
            return;
        }
    }

    void Spot(string id, vector position, int day)
    {
        HCDeadDropRow row = new HCDeadDropRow;
        row.Id = id;
        row.Cache.Position = position;
        row.NextDay = day;
        m_State.Rows.Insert(row);
        m_Dirty = true;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("DeadDrops", true, "EXP-L4", HCV2Gates.Qualified("EXP-L4")));
        m_Store = new HCEncounterStore<HCDeadDropState>("dead-drops");
        m_State = m_Store.Load(new HCDeadDropState, "Rows");
        if (!m_State || m_State.Version != 1 || !m_State.Rows) { HCRefuseState(); return; }
        if (m_State.Rows.Count() == 0)
        {
            int day = HCEscalationClock.Day();
            Spot("hc-drop-balota", "4086 0 3005", day);
            Spot("hc-drop-pavlovo", "2008 0 4230", day);
            Spot("hc-drop-zeleno", "2470 0 5795", day);
            Spot("hc-drop-vybor", "3405 0 9380", day);
            Spot("hc-drop-stary", "5675 0 7990", day);
            Spot("hc-drop-gorka", "9065 0 9115", day);
            Spot("hc-drop-severo", "7450 0 13040", day);
            Spot("hc-drop-berezino", "11710 0 10285", day);
            if (!SaveChanged()) { HCRefuseState(); return; }
        }
        if (Count() < 6 || Count() > 10) { HCRefuseState(); return; }
        map<string, bool> ids = new map<string, bool>;
        foreach (HCDeadDropRow row : m_State.Rows)
        {
            if (!row || !HCWorldLimits.Token(row.Id) || ids.Contains(row.Id) || !HCEncounterCacheIO.Valid(row.Cache) || row.Deposits < 0 || row.Deposits > 4 || row.NextDay < 0 || !row.SurvivorDeposits || row.SurvivorDeposits.Count() > 32) { HCRefuseState(); return; }
            if (!HCWorldLimits.Strings(row.SurvivorDeposits, 32)) { HCRefuseState(); return; }
            ids.Set(row.Id, true);
            m_Caches.Insert(new HCEncounterCacheIO);
        }
        s_Instance = this;
        m_Ready = true;
        Print("[HC Plan] HC-34 party=dead-drops phase=refused cargo_owner=native-cache state=refused count=0 refusal=ABSTRACT_DEPOSIT_WITHDRAWAL_RETIRED runtime=PENDING");
    }

    protected void HCRefuseState()
    {
        Print("[HollowCountry] V2 dead drops refused: invalid dead-drops.json state or save failure; preserve file, .tmp and .bak");
    }

    string CacheId(int index)
    {
        if (index < 0 || index >= Count()) return "";
        return m_State.Rows[index].Id;
    }

    EntityAI Cache(int index)
    {
        if (!m_Ready || index < 0 || index >= Count() || m_State.Rows[index].Cache.Phase != 2) return null;
        EntityAI cache = m_Caches[index].Handle;
        if (!cache || cache.IsRuined() || cache.GetHierarchyParent() || cache.GetHierarchyRootPlayer()) return null;
        return cache;
    }

    // Compatibility refusal for former server-side abstract consumers.
    // Players use ordinary vanilla inventory; no RPC or client-owned state.
    int TakeOne(int index, EntityAI destination, string actorId)
    {
        // HC-34: a cache-to-cache hop has no carrier or observed route. Keep
        // existing caches stealable but refuse this legacy abstract withdrawal.
        return 4;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !HCWorldModule.Get()) return;
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) return;
        m_Elapsed = 0;
        m_Units.HCReset(1);
        m_WorkBudget.HCReset(1);
        if (!m_Units.HCTake(1) || !m_WorkBudget.HCContinue()) { m_WorkBudget.HCDeferred(GetName(), 1); return; }
        if (m_Next >= Count()) { m_Next = 0; }
        int index = m_Next;
        m_Next++;
        HCDeadDropRow row = m_State.Rows[index];
        if (row.Quarantined) return;
        if (row.Cache.Phase == 0)
        {
            vector anchor = row.Cache.Position;
            if (GetGame().SurfaceIsSea(anchor[0], anchor[2]) || GetGame().SurfaceIsPond(anchor[0], anchor[2])) return;
            vector normal = GetGame().SurfaceGetNormal(anchor[0], anchor[2]);
            if (normal[1] < 0.8660254) return;
            vector spot = Vector(anchor[0], GetGame().SurfaceY(anchor[0], anchor[2]) + 0.03, anchor[2]);
            if (!HCObserverTransitionGate.CanTransition(spot, 500)) return;
            row.Cache.Position = spot;
            if (!HCWorldLimits.Position(row.Cache.Position) || !m_Caches[index].Clear(row.Cache, null)) return;
            row.Cache.Phase = 1;
            m_Dirty = true;
            if (!SaveChanged()) return;
            m_Caches[index].Create(row.Cache);
            m_Dirty = true;
        }
        int priorPhase = row.Cache.Phase;
        string priorRef = row.Cache.EntityRef;
        m_Caches[index].LinkCache(row.Cache);
        if (row.Cache.Phase != priorPhase || row.Cache.EntityRef != priorRef) m_Dirty = true;
        if (!SaveChanged()) return;
        // HC-34: old house -> remote drop deposits bypassed a real survivor.
        // Preserve the finite caches/history; new deposits require the same
        // actual item carried by an admitted party and a native return receipt.
        // No automatic stock harvesting, route progression or refill here.
    }

    override void OnStop()
    {
        // Flush deposits/removals marked by EECargoIn/Out since the last tick; a faulted store stays unwritten.
        if (m_Ready && m_State) SaveChanged();
        m_Ready = false;
        if (s_Instance == this) s_Instance = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCDeadDrops);
    }
}
