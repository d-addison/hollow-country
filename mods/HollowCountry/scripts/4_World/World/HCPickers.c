// W5-PERF-5: <=one finite visit/60s, <=32 item rows per visit.
// Shared guard precedes route/native work; journal barriers remain synchronous.
// Native timing evidence: HCWorkBudget.c (Game.c:914).
// LC-T407/409, #101. Native evidence in installed scripts-1.30.164289:
// 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation, :873 ModelToWorld;
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 1_Core/proto/EnScript.c:394 Find, :385 Clear; EnConvert.c:30 int.ToString;
// 3_Game/Entities/EntityAI.c:885 GetHierarchyParent, :1884 GetInventory;
// 3_Game/Systems/Inventory/Inventory.c:138 GetCargo; Cargo.c:28 GetItemCount, :32 GetItem;
// 1_Core/proto/EnScript.c:380 Count, :407 Insert; EnDebug.c:96 Print.
// Files/journal use HCSearchHouseJournal/HCEncounterStore, clock uses HCWorldClock.
// Abstract routes change ledger progress only; no body, door or actor relocation.
// Admission is preference-only; native inventory/noise/restart acceptance PENDING.
class HCPickerPolicy
{
    static int ChargeAfterVisit(int used, int phase)
    {
        if (phase == 2) return used + 1;
        return used;
    }

    static bool MayVisit(int used, int recordedDay, int today, bool visited)
    {
        return used >= 0 && used < 6 && recordedDay == today && !visited;
    }
}

// Shared immutable journal transaction. Entry phase 0 was durably bound by the
// caller. Phase 1 is installed before callbacks. Neither failure nor restart
// ever reopens the row. There is exactly one native move and no compensation.
class HCNonPlayerMoves
{
    ref HCSearchHouseJournal m_Journal;
    ref HCSearchSupplyRegistry m_Registry;

    int CommitMove(HCSearchEntry entry, EntityAI destination, string actorId, int index)
    {
        if (!m_Journal || !m_Registry || !m_Journal.Healthy()) return 3;
        if (!m_Journal.Row(index)) return 3;
        int prior = m_Journal.Row(index).Phase;
        if (prior == 2 || prior == 3 || prior == 4) return prior;
        if (prior != 0) return 3;
        m_Journal.SetPhase(index, 1);
        int phase = 3;
        if (m_Journal.Write(index, "claim", actorId, 1))
        {
            if (m_Journal.Write(index, "attempt", actorId, 1))
            {
                phase = m_Registry.Transfer(entry, destination, actorId);
            }
            if (!m_Journal.Write(index, "result", actorId, phase)) phase = 3;
        }
        m_Journal.SetPhase(index, phase);
        return phase;
    }
}

// Uses the SAME service, source ids, site ids, registry and refresh cooldown as
// player searches. Two independent journals must never race to bind a house.
modded class HCSearchHouses
{
    protected int m_V2Cursor;

    int V2Visit(Object structure, EntityAI destination, string actorId, int siteNumber)
    {
        if (!m_Started || m_Fault || m_Busy || !m_Settings || !GetGame().IsServer()) return 0;
        if (!structure || !destination || !HCInteriorTemplates.Loaded()) { return 0; }
        if (!HCObserverTransitionGate.CanTransition(structure.GetPosition(), 500) || !HCObserverTransitionGate.CanTransition(destination.GetPosition(), 500)) return 0;
        HCInteriorTemplateClassRow classRow = HCInteriorTemplates.ClassRow(structure.GetType());
        HCInteriorTemplate layout = HCInteriorTemplates.Template(structure.GetType());
        if (!classRow || classRow.Search != "covered" || !layout || layout.SearchSites.Count() < 1) return 0;
        HCInteriorTemplateSearchSite templateSite = layout.SearchSites[siteNumber % layout.SearchSites.Count()];
        if (!SiteShapeValid(templateSite) || !HCInteriorRules.TiltAcceptable(structure.GetOrientation(), HCInteriorRules.MAX_HOUSE_TILT_DEGREES)) return 0;
        HCSearchHouseHit hit = new HCSearchHouseHit;
        hit.Structure = structure;
        hit.BuildingClass = structure.GetType();
        hit.InstanceId = hit.BuildingClass + "_" + HCInteriorRules.TransformKey(structure.GetPosition(), structure.GetOrientation());
        hit.TemplateSiteId = templateSite.Id;
        hit.SiteId = hit.InstanceId + "_site" + templateSite.Id.ToString() + "_v2";
        hit.Room = templateSite.Room;
        hit.Center = structure.ModelToWorld(HCInteriorTemplates.AsVector(templateSite.Center));
        hit.Radius = templateSite.Radius;
        foreach (string groupId : templateSite.Groups) hit.Groups.Insert(groupId);
        if (SessionOfSite(hit.SiteId)) return 0;
        if (!EnsureJournal()) return 3;
        HCSearchHouseSlot slot = Touch(hit);
        if (!slot) return 0;
        string scope = m_Journal.RefreshScope();
        if (m_Journal.RefreshHasHistory(hit.SiteId)) HCSearchRefreshModule.Mark(scope, hit.SiteId, true);
        // Match native Prepare: bind/activate a site once per occupied slot.
        // Repeated visits must never append duplicate site ids or rebind supply.
        if (slot.Sites.Find(hit.SiteId) < 0)
        {
            if (!m_Journal.SiteBound(hit.SiteId) || HCSearchRefreshModule.Ready(scope, hit.SiteId))
            {
                if (!Bind(slot, hit))
                {
                    if (!m_Journal.Healthy()) return 3;
                    return 0;
                }
                if (HCSearchRefreshModule.Ready(scope, hit.SiteId)) HCSearchRefreshModule.Mark(scope, hit.SiteId);
            }
            else if (!Activate(slot, hit))
            {
                if (!m_Journal.Healthy()) return 3;
                return 0;
            }
        }
        // Only 32 journal rows examined on one visit, carrying the cursor on.
        int examined = 0;
        while (examined < 32 && examined < m_Journal.Count())
        {
            if (m_V2Cursor >= m_Journal.Count()) m_V2Cursor = 0;
            int index = m_V2Cursor;
            m_V2Cursor++;
            examined++;
            HCSearchHouseRow row = m_Journal.Row(index);
            if (!row || row.SiteId != hit.SiteId || row.Phase != 0 || !m_Registry.Find(row.SupplyId)) continue;
            HCNonPlayerMoves mover = new HCNonPlayerMoves;
            mover.m_Journal = m_Journal;
            mover.m_Registry = m_Registry;
            m_Busy = true;
            int result = mover.CommitMove(EntryOf(row), destination, actorId, index);
            m_Busy = false;
            // Release a terminal handle so later cache-to-cache moves can bind
            // it independently. The spent house row stays immutable forever.
            if (m_Registry) m_Registry.Forget(row.SupplyId);
            if (result == 2 && !HCDeadDrops.RecordHouseDeposit(destination, row.SupplyId)) return 3;
            if (result == 2 && m_Started) HCSearchNoise.EmitAt(destination, hit.Center);
            return result;
        }
        return 0;
    }
}

// A second, finite journal is exclusively for withdrawals from real caches.
// Different root from template search: same item can make another journaled hop,
// but no identical source-cache/item pair can ever replay here.
class HCCacheMoveJournal : HCSearchHouseJournal
{
    override bool Open(string sourceId, string sourcePin, string worldName, string build)
    {
        if (m_Open || m_Fault || !GetGame().IsServer()) return false;
        m_SourceId = sourceId;
        m_SourcePin = sourcePin;
        m_WorldName = worldName;
        m_Build = build;
        m_Root = "$profile:HollowCountry/CacheMoves";
        if (!FileExist(m_Root) && !MakeDirectory(m_Root)) return Fail("cache journal unavailable");
        m_Open = true;
        return Restore();
    }
}

class HCCacheMoves
{
    protected static ref HCCacheMoves s_Shared;

    static HCCacheMoves Shared()
    {
        if (!s_Shared) s_Shared = new HCCacheMoves;
        return s_Shared;
    }

    protected ref HCSearchHouseJournal m_Journal;
    protected ref HCSearchSupplyRegistry m_Registry;
    protected bool m_Fault;
    static const string PIN = "cace000100000000000000000000000000000000000000000000000000000000";

    int TakeOne(EntityAI source, EntityAI destination, string actorId, array<string> allowed)
    {
        if (m_Fault || (m_Journal && !m_Journal.Healthy())) return 3;
        if (!source || !destination || source == destination || source.GetHierarchyParent() || source.GetHierarchyRootPlayer()) return 4;
        if (!m_Journal)
        {
            m_Journal = new HCCacheMoveJournal;
            m_Registry = new HCSearchSupplyRegistry;
            if (!m_Journal.Open("v2-cache-withdrawals", PIN, HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()), HCBuildIdentity.Canonical()) || !m_Registry.BindLazySource("v2-cache-withdrawals", PIN, HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()), HCBuildIdentity.Canonical()))
            {
                m_Fault = true;
                return 3;
            }
        }
        if (HCSearchSupplyRegistry.PersistentId(source) == "" || !source.GetInventory() || !source.GetInventory().GetCargo()) return 4;
        CargoBase cargo = source.GetInventory().GetCargo();
        int count = cargo.GetItemCount();
        if (count > 32) count = 32;
        for (int slotIndex = 0; slotIndex < count; slotIndex++)
        {
            EntityAI item = cargo.GetItem(slotIndex);
            string supplyId = HCSearchSupplyRegistry.PersistentId(item);
            if (!item || !HCDeadDrops.MayWithdraw(allowed, supplyId) || m_Journal.SupplyKnown(supplyId)) continue;
            if (!m_Registry.RegisterOwned(item, "cache_" + supplyId)) continue;
            int index = m_Journal.Count();
            string siteId = "cache_" + HCSearchSupplyRegistry.PersistentId(source);
            if (!m_Journal.Add(siteId, supplyId, item.GetType()))
            {
                m_Registry.Forget(supplyId);
                m_Fault = true;
                return 3;
            }
            HCSearchEntry entry = new HCSearchEntry;
            entry.SiteId = siteId;
            entry.SupplyId = supplyId;
            entry.ItemClass = item.GetType();
            HCNonPlayerMoves mover = new HCNonPlayerMoves;
            mover.m_Journal = m_Journal;
            mover.m_Registry = m_Registry;
            int phase = mover.CommitMove(entry, destination, actorId, index);
            m_Registry.Forget(supplyId);
            if (phase == 2 && source) HCSearchNoise.EmitAt(source, source.GetPosition());
            return phase;
        }
        return 0;
    }

    void Stop()
    {
        if (m_Registry) m_Registry.Retire();
        if (s_Shared == this) s_Shared = null;
        m_Fault = true;
    }
}

class HCPickerState
{
    int Version = 1;
    ref HCWorldParty Party = new HCWorldParty;
    int NextVisit;
    bool Quarantined;
    int NextHouse;
    bool Published;
}

class HCPickers : HCModule
{
    protected ref HCEncounterStore<HCPickerState> m_Store;
    protected ref HCPickerState m_State;
    protected float m_Elapsed;
    protected bool m_Ready;
    protected int m_Reports;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;

    override string GetName() { return "Pickers"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Pickers", true, "EXP-L5", HCV2Gates.Qualified("EXP-L5")));
        m_Store = new HCEncounterStore<HCPickerState>("pickers");
        m_State = m_Store.Load(new HCPickerState, "Party");
        if (!m_State || m_State.Version != 1 || !m_State.Party || m_State.Party.DailyTransfers < 0 || m_State.Party.DailyTransfers > 6 || m_State.Party.TransferDay < 0 || m_State.Party.Edge < 0 || m_State.Party.Edge >= 16 || !m_State.Party.Route || m_State.Party.Route.Count() > 16 || m_State.NextHouse < 0 || m_State.NextHouse >= HCAILimits.Get().MaxHoldouts || m_State.NextVisit < 0) { Print("[HC AI] picker state invalid or exceeds AILimits.MaxHoldouts; load refused"); return; }
        if (m_State.Party.Id == "")
        {
            m_State.Party.Id = "hc-pickers-01";
            m_State.Party.FactionId = "scavengers";
            m_State.Party.Kind = "PICKER";
            m_State.Party.Size = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, m_State.Party.Id, "party");
            m_State.Party.TransferDay = HCEscalationClock.Day();
            m_State.NextVisit = HCWorldClock.UTC() + 900;
            if (!m_Store.Save(m_State)) return;
        }
        m_Ready = true;
        Print("[HollowCountry] V2 pickers ready parties=1 abstract=1 cap=6/day interval=900s");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || m_State.Quarantined) return;
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) return;
        m_Elapsed = 0;
        m_WorkBudget.HCReset(1);
        if (!m_WorkBudget.HCContinue()) { m_WorkBudget.HCDeferred(GetName(), 1); return; }
        HCHoldouts holdouts = HCHoldouts.Get();
        HCDeadDrops drops = HCDeadDrops.Get();
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCWorldModule world = HCWorldModule.Get();
        if (!holdouts || !drops || !houses || !world || holdouts.Count() < 1) return;
        int now = HCWorldClock.UTC();
        int today = HCEscalationClock.Day();
        if (now < 1 || today < m_State.Party.TransferDay || now < m_State.Party.LastMoved) { return; }
        if (now < m_State.NextVisit) return;
        if (today > m_State.Party.TransferDay)
        {
            m_State.Party.TransferDay = today;
            m_State.Party.DailyTransfers = 0;
        }
        if (!HCPickerPolicy.MayVisit(m_State.Party.DailyTransfers, m_State.Party.TransferDay, today, false)) return;
        if (m_State.Party.Route.Count() == 0)
        {
            int routeCount = holdouts.Count();
            if (routeCount > 16) routeCount = 16;
            for (int routeIndex = 0; routeIndex < routeCount; routeIndex++) m_State.Party.Route.Insert(holdouts.PlaceId(routeIndex));
            if (m_State.Party.Route.Count() == 1) m_State.Party.Route.Insert(holdouts.PlaceId(0));
            m_State.Party.Home = holdouts.PlaceId(0);
            if (!m_Store.Save(m_State)) { m_Ready = false; return; }
        }
        if (!m_State.Published)
        {
            m_State.Published = world.AddParty(m_State.Party);
            if (!m_Store.Save(m_State)) { m_Ready = false; return; }
        }
        int houseIndex = m_State.NextHouse % holdouts.Count();
        Object house = holdouts.Structure(houseIndex);
        EntityAI destination = drops.Cache(houseIndex % drops.Count());
        if (!house || !destination) return;
        EntityAI home = holdouts.Cache(houseIndex);
        if (!HCObserverTransitionGate.CanTransition(house.GetPosition(), 500) || !HCObserverTransitionGate.CanTransition(destination.GetPosition(), 500)) return;
        if (home && !HCObserverTransitionGate.CanTransition(home.GetPosition(), 500)) return;
        // Persist route progress before callbacks; charge only a confirmed move.
        // Immutable item intents prevent replay after an interrupted visit.
        m_State.NextHouse = (houseIndex + 1) % holdouts.Count();
        m_State.Party.Edge = (m_State.Party.Edge + 1) % m_State.Party.Route.Count();
        m_State.Party.LastMoved = now;
        m_State.NextVisit = now + 900;
        if (!m_Store.Save(m_State)) { m_Ready = false; return; }
        int phase;
        // Every fourth visit can withdraw a drop into a recoverable hold-out
        // cache; all other visits empty an actual template search site.
        if ((m_State.Party.DailyTransfers + 1) % 4 == 0 && home)
            phase = drops.TakeOne(houseIndex % drops.Count(), home, m_State.Party.Id);
        else
            phase = houses.V2Visit(house, destination, m_State.Party.Id, m_State.Party.DailyTransfers);
        m_State.Party.DailyTransfers = HCPickerPolicy.ChargeAfterVisit(m_State.Party.DailyTransfers, phase);
        if (phase == 3) Quarantine();
        else if (!m_Store.Save(m_State)) { m_Ready = false; return; }
        string place = world.NearestPlace(house.GetPosition());
        place.ToLower();
        if (phase == 2) world.AddFact("picker_searched", place, 0);
        if (m_Reports < 12)
        {
            m_Reports++;
            Print("[HollowCountry] V2 picker visit phase=" + phase.ToString() + " used=" + m_State.Party.DailyTransfers.ToString() + "/6");
        }
    }

    void Quarantine()
    {
        m_State.Quarantined = true;
        if (!m_Store.Save(m_State)) m_Ready = false;
        Print("[HollowCountry] V2 pickers quarantined; no replay or replacement supply");
    }

    override void OnStop() { m_Ready = false; }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCPickers);
    }
}
