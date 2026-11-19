// #151 original adapter, Expansion inspected read-only, never copied.
// Expansion xref/ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:213
// AddWaypoint, :222 GetWaypoints, :241 ClearWaypoints, :251
// SetWaypointBehaviour, :304 GetWaypointBehaviour, :1123 IsInCombat,
// :1139 GetMember, :1185 Count; Entities/DayZPlayerImplement.c:234 GetGroup.
// Entities/AI/eAIBase.c:9825 StartAction. Native forced entry remains the
// provider's path/perception behavior (:11662-11677 lock compatibility,
// damage/provider veto, physical door target); no direct UnlockDoor/damage.
// Native scripts-1.30.164289: Game.c:930 GetObjectsAtPosition3D, :1120
// IsServer; gameplay.c:636 GetGame; Object.c:215 IsPendingDeletion,
// :287 GetPosition, :517 IsAlive; PlayerBase.c:3925 IsUnconscious;
// Building.c:28 GetDoorIndex, :31 GetDoorCount, :55 IsDoorLocked,
// :73 GetDoorSoundPos; DayZPhysics.c:199 RaycastRV; EnConvert.c:210
// DistanceSq, :196 Distance; EnMath3D.c:18 Vector; EnString.c:20 ToInt; EnScript.c:380/385/394/407 arrays;
// EnDebug.c:96 Print. Anatomical ray origin follows HCXStance.Visible.
// Native ActionUnlockDoors.c:28-59 ActionCondition (tool/reach/attachments),
// :76-81 completion and real tool wear; ActionTargets.c:125 constructor;
// ActionBase.c:968 Can; PlayerBase.c:6733 GetItemInHands,
// :1887 GetActionManager; ActionManagerBase.c:214 GetAction,
// :91 GetRunningAction. Custody APIs/citations stay in HCPickers.c.

// Raid guard is evaluated twice by the existing physical custody handler.
class HCXAIBaseRaidInventory : HCScavengeInventory
{
    override bool HCPartyCurrent(HCScavengeState row)
    {
        if (!super.HCPartyCurrent(row) || !Source) { return false; }
        if (!HCBaseRaid.HCOwns(LeaseId)) { return false; }
        HCBaseRaidPort port = HCBaseRaid.HCGet();
        if (!port || !port.HCCustodyAllowed(Actor, Source)) { return false; }
        return HCBaseRaid.HCUnattended(HCTheftOwner, HCTheftCamp, Source.GetPosition());
    }
}

class HCXAIBaseRaid : HCBaseRaidPort
{
    protected ref HCBaseRaidConfig m_Config;
    protected ref HCEncounterStore<HCScavengeState> m_Store;
    protected ref HCScavengeState m_Receipt;
    protected ref HCXAIBaseRaidInventory m_Inventory;
    protected HCXAISiteState m_Site;
    protected eAIBase m_Actor;
    protected Object m_Seen;
    protected Building m_Building;
    protected ItemBase m_Source;
    protected int m_Door = -1;
    protected int m_Component = -1;
    protected vector m_Point;
    protected HCCampModule m_Owner;
    protected ref HCCampRecord m_Camp;
    protected int m_Due;
    protected int m_Ends;
    protected int m_PartyCursor;
    protected int m_ObjectCursor;
    protected int m_DoorCursor;
    protected bool m_Reserved;
    protected bool m_Walking;
    protected bool m_Busy;
    protected bool m_Healthy;
    protected string m_Reason;
    protected eAIGroup m_Group;
    protected eAIWaypointBehavior m_Behaviour;
    protected ref array<vector> m_Original = new array<vector>;

    void HCOpen()
    {
        if (!HCBaseRaid.HCEnabled()) { return; }
        m_Config = HCBaseRaid.HCConfig();
        m_Store = new HCEncounterStore<HCScavengeState>("base-raid-custody");
        HCScavengeState fresh = new HCScavengeState;
        m_Receipt = m_Store.Load(fresh, "Phase");
        if (!m_Receipt || m_Receipt.Version != 1) { m_Reason = "BASE_RAID_JOURNAL_INVALID"; return; }
        // Restart never reconstructs party/item handles or retries a transfer.
        // Camp LastProbe is already durable, including warned reservations.
        if (m_Receipt.Phase != "idle")
        {
            Print("[HC BaseRaid] BASE_RAID_RESTART_NO_REPLAY runtime=PENDING");
        }
        m_Healthy = true;
    }

    override bool HCReady() { return m_Healthy && m_Config && m_Store && m_Store.Healthy(); }
    override string HCRefusal()
    {
        if (m_Reason != "") { return m_Reason; }
        return "BASE_RAID_JOURNAL_UNAVAILABLE";
    }
    override bool HCOwns(string lease) { return m_Reserved && m_Site && m_Site.ProposalId == lease; }

    override bool HCCustodyAllowed(PlayerBase actor, EntityAI source)
    {
        if (!m_Reserved || actor != m_Actor || source != m_Source || !m_Camp || !HCLiveParty()) { return false; }
        if (vector.DistanceSq(source.GetPosition(), m_Camp.Position) > m_Config.SourceRangeMeters * m_Config.SourceRangeMeters) { return false; }
        return HCPerceive(source, source.GetPosition());
    }

    bool HCLiveParty()
    {
        if (!m_Site || !HCW38SituationRuntime.HCCandidate(m_Site) || !m_Actor) { return false; }
        if (!m_Actor.IsAlive() || m_Actor.IsPendingDeletion() || m_Actor.IsUnconscious()) { return false; }
        return m_Actor.GetGroup() == m_Site.Patrol.m_Group;
    }

    bool HCVisible(Object target, vector point)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        bool blocked = DayZPhysics.RaycastRV(m_Actor.GetPosition() + Vector(0, 1.6, 0), point, contact, normal, component, hits, null, m_Actor);
        if (!blocked) { m_Component = -1; return true; }
        if (hits.Find(target) < 0 || vector.Distance(contact, point) > UAMaxDistances.DEFAULT) { return false; }
        m_Component = component;
        return true;
    }

    bool HCPerceive(Object target, vector point)
    {
        if (!m_Actor || !target || !m_Config) { return false; }
        if (vector.DistanceSq(m_Actor.GetPosition(), point) > m_Config.NoticeRangeMeters * m_Config.NoticeRangeMeters) { return false; }
        return HCVisible(target, point);
    }

    // One party, one local object and one door per budgeted tick. Never reads
    // camps/claims/positions to choose a target. Ownership is resolved ONLY
    // after live distance + geometry; arbitrary camp coordinates cannot enter.
    bool HCPartyAllowed() { return m_Site && m_Site.ProviderFaction == "HCRaiders"; }

    void HCSense()
    {
        m_Seen = null;
        m_Source = null;
        m_Building = null;
        m_Door = -1;
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() == 0) { return; }
        m_PartyCursor = m_PartyCursor % states.Count();
        m_Site = states[m_PartyCursor];
        m_PartyCursor++;
        if (!HCW38SituationRuntime.HCCandidate(m_Site) || !HCPartyAllowed()) { return; }
        if (HCW38SituationRuntime.HCUsed(m_Site.ProposalId) || HCBaseRaid.HCOwns(m_Site.ProposalId)) { return; }
        eAIGroup party = m_Site.Patrol.m_Group;
        if (party.IsInCombat() || party.Count() > HCWorldMaterializer.MAX_PLAYERS) { return; }
        m_Actor = eAIBase.Cast(party.GetMember(0));
        if (!HCLiveParty()) { return; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(m_Actor.GetPosition(), m_Config.NoticeRangeMeters, nearby, cargos);
        if (nearby.Count() == 0 || nearby.Count() > m_Config.MaxObjects || cargos.Count() > m_Config.MaxObjects) { return; }
        m_ObjectCursor = m_ObjectCursor % nearby.Count();
        Object candidate = nearby[m_ObjectCursor];
        m_ObjectCursor++;
        if (!candidate || candidate.IsPendingDeletion()) { return; }
        ItemBase storage = ItemBase.Cast(candidate);
        if (storage && HCCampScan.StorageItem(storage))
        {
            vector storagePoint = storage.GetPosition();
            if (!HCPerceive(storage, storagePoint)) { return; }
            m_Source = storage;
            m_Seen = storage;
            m_Point = storagePoint;
            return;
        }
        Building house = Building.Cast(candidate);
        if (!house || house.GetDoorCount() < 1 || house.GetDoorCount() > m_Config.MaxDoors) { return; }
        m_DoorCursor = m_DoorCursor % house.GetDoorCount();
        int door = m_DoorCursor;
        m_DoorCursor++;
        if (!HCBuildingClaim.HCDoor(house, door)) { return; }
        vector doorway = house.GetDoorSoundPos(door);
        if (!HCPerceive(house, doorway)) { return; }
        // A wall hit is not perception of the door behind that wall.
        if (m_Component < 0 || house.GetDoorIndex(m_Component) != door) { return; }
        m_Building = house;
        m_Door = door;
        m_Seen = house;
        m_Point = doorway;
    }

    override bool HCSeen(HCCampRecord camp, HCCampScan scan)
    {
        if (!camp || !scan || m_Reserved || !m_Seen || !HCLiveParty()) { return false; }
        if (!HCPerceive(m_Seen, m_Point)) { return false; }
        if (m_Source)
        {
            return HCCampScan.RefOf(m_Source) == camp.FireRef || scan.Crates.Find(m_Source) >= 0;
        }
        HCBuildingClaim claims = HCBuildingClaim.HCGet();
        if (!claims || !m_Building || m_Component < 0 || m_Building.GetDoorIndex(m_Component) != m_Door) { return false; }
        return claims.HCHoldsClaim(camp.GroupId.ToInt(), HCBuildingClaim.HCIdentity(m_Building));
    }

    override bool HCReserve(HCCampModule owner, HCCampRecord camp, int now)
    {
        m_Reason = "BASE_RAID_PARTY_UNAVAILABLE";
        if (!HCReady() || m_Reserved || !HCLiveParty() || !m_Seen) { return false; }
        if (HCW38SituationRuntime.HCUsed(m_Site.ProposalId) || HCBaseRaid.HCOwns(m_Site.ProposalId)) { return false; }
        eAIGroup group = m_Actor.GetGroup();
        array<vector> route = group.GetWaypoints();
        if (!route || route.Count() == 0 || route.Count() > m_Config.MaxRouteNodes || group.IsInCombat()) { return false; }
        m_Owner = owner;
        m_Camp = camp;
        m_Reserved = true;
        m_Due = 0;
        m_Ends = 0;
        m_Reason = "";
        return true;
    }

    override void HCWarned(HCCampRecord camp, int now)
    {
        if (!m_Reserved || m_Camp != camp) { return; }
        m_Due = now + m_Config.WarningSeconds;
        m_Ends = m_Due + m_Config.RaidSeconds;
        Print("[HC BaseRaid] warned runtime=PENDING");
    }

    bool HCWalkTo(vector goal)
    {
        if (!HCLiveParty()) { return false; }
        eAIGroup group = m_Actor.GetGroup();
        array<vector> previous = group.GetWaypoints();
        if (!m_Group)
        {
            if (!previous || previous.Count() == 0 || previous.Count() > m_Config.MaxRouteNodes) { return false; }
            array<vector> saved = previous;
            foreach (vector node : saved) { m_Original.Insert(node); }
            m_Behaviour = group.GetWaypointBehaviour();
            m_Group = group;
        }
        if (m_Group != group) { return false; }
        group.ClearWaypoints();
        group.AddWaypoint(goal);
        group.SetWaypointBehaviour(eAIWaypointBehavior.ONCE);
        m_Walking = true;
        return true;
    }

    // Physical, real tool in hands only. Native Can/SetupAction/completion own
    // reach, compatibility, attachments, duration and tool wear. Never call
    // completion directly. Otherwise native path-driven forced entry remains.
    bool HCUnlockAllowed(eAIBase actor)
    {
        if (!m_Reserved || actor != m_Actor || !m_Camp || !m_Building) { return false; }
        int now = HCWorldClock.UTC();
        if (now < m_Due || now >= m_Ends || !HCLiveParty()) { return false; }
        return HCBaseRaid.HCUnattended(m_Owner, m_Camp, m_Building.GetDoorSoundPos(m_Door));
    }

    void HCTryLockpick()
    {
        if (!m_Building || m_Component < 0 || m_Building.GetDoorIndex(m_Component) != m_Door) { return; }
        if (!HCBuildingClaim.HCDoor(m_Building, m_Door) || !m_Building.IsDoorLocked(m_Door)) { return; }
        if (!m_Actor.GetActionManager() || m_Actor.GetActionManager().GetRunningAction()) { return; }
        ItemBase tool = m_Actor.GetItemInHands();
        if (!tool) { return; }
        ActionBase unlock = m_Actor.GetActionManager().GetAction(ActionUnlockDoors);
        if (!unlock) { HCBaseRaid.HCRefuse("BASE_RAID_NATIVE_UNLOCK_ACTION_UNAVAILABLE"); return; }
        ActionTarget doorTarget = new ActionTarget(m_Building, null, m_Component, m_Point, -1);
        if (!unlock.Can(m_Actor, doorTarget, tool)) { return; }
        m_Actor.HCBaseRaidUnlock = true;
        m_Actor.StartAction(ActionUnlockDoors, doorTarget, tool);
    }

    // After reaching the remembered door, discover loot only by fresh local
    // geometry. No remote cache, claim-list target or through-wall inventory.
    void HCFindLoot()
    {
        if (m_Source) { return; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> localCargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(m_Actor.GetPosition(), m_Config.SourceRangeMeters, nearby, localCargo);
        if (nearby.Count() == 0 || nearby.Count() > m_Config.MaxObjects || localCargo.Count() > m_Config.MaxObjects) { return; }
        m_ObjectCursor = m_ObjectCursor % nearby.Count();
        ItemBase crate = ItemBase.Cast(nearby[m_ObjectCursor]);
        m_ObjectCursor++;
        if (!crate || !HCLockTable.CampUnlocked(crate)) { return; }
        if (vector.DistanceSq(crate.GetPosition(), m_Camp.Position) > m_Config.SourceRangeMeters * m_Config.SourceRangeMeters) { return; }
        if (!HCPerceive(crate, crate.GetPosition())) { return; }
        m_Source = crate;
        HCWalkTo(crate.GetPosition());
    }

    // One same-item move, existing preflight/readback path, synchronous durable
    // intent BEFORE native callbacks. Failure/ambiguity never replays or deletes.
    void HCTakeLoot()
    {
        if (!m_Source) { return; }
        if (!HCLockTable.CampUnlocked(m_Source))
        {
            HCBaseRaid.HCRefuse("BASE_RAID_LOCKED_OR_UNSUPPORTED_STORAGE");
            return;
        }
        m_Inventory = new HCXAIBaseRaidInventory;
        m_Inventory.Actor = m_Actor;
        m_Inventory.Source = m_Source;
        // One-way custody: Home is an accessibility guard on the same source;
        // no return/deposit handler is called. Loot stays in raider inventory.
        m_Inventory.Home = m_Source;
        m_Inventory.LeaseId = m_Site.ProposalId;
        m_Inventory.HCTheftOwner = m_Owner;
        m_Inventory.HCTheftCamp = m_Camp;
        m_Inventory.Survey = new HCPickerSurvey;
        m_Inventory.Survey.MaxCargoScan = m_Config.MaxCargoScan;
        m_Inventory.Survey.ArrivalRangeMeters = m_Inventory.Defaults.TransferRangeMeters;
        if (!m_Inventory.HCAtSource()) { return; }
        m_Inventory.Item = m_Inventory.HCTheftFirstItem(m_Source);
        if (!m_Inventory.Item)
        {
            HCBaseRaid.HCRefuse("BASE_RAID_SAFE_PHYSICAL_STOCK_ABSENT");
            HCCancel();
            return;
        }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(m_Site.ProposalId);
        if (!HCAIPartyIdentity.HCValid(identity)) { HCCancel(); return; }
        m_Receipt = new HCScavengeState;
        m_Receipt.Phase = "acquiring";
        m_Receipt.PartyId = identity.HCPartyId();
        m_Receipt.CargoId = identity.HCCargoId();
        m_Receipt.Generation = identity.HCGeneration();
        m_Receipt.LeaseId = m_Site.ProposalId;
        m_Receipt.SourceId = HCSearchSupplyRegistry.PersistentId(m_Source);
        m_Receipt.HomeId = m_Receipt.SourceId;
        m_Receipt.ActorId = HCSearchSupplyRegistry.PersistentId(m_Actor);
        m_Receipt.ItemId = HCSearchSupplyRegistry.PersistentId(m_Inventory.Item);
        if (m_Receipt.ActorId == "" || m_Receipt.SourceId == "" || m_Receipt.ItemId == "")
        {
            HCBaseRaid.HCRefuse("BASE_RAID_PERSISTENT_ID_UNAVAILABLE");
            HCCancel();
            return;
        }
        if (!m_Store.Save(m_Receipt)) { m_Healthy = false; HCCancel(); return; }
        m_Busy = true;
        int result = m_Inventory.HCMove(false, m_Receipt);
        m_Busy = false;
        m_Receipt.Phase = "lost";
        if (result == 2) { m_Receipt.Phase = "returned"; }
        if (result == 3) { m_Receipt.Phase = "quarantined"; }
        m_Receipt.CargoOwner = m_Inventory.HCOwner();
        if (!m_Store.Save(m_Receipt)) { m_Healthy = false; }
        Print("[HC BaseRaid] custody_terminal no_replay=1 runtime=PENDING");
        HCCancel();
    }

    void HCStep(int now)
    {
        if (!HCReady() || !HCBaseRaid.HCEnabled() || !HCCampProbes.HCEnabled() || m_Busy) { return; }
        // Lead integration: add HC_WORK_BASE_RAID=12, raise CONSUMERS to 13.
        // This independent bounded loop must retain its own starvation slot.
        int cost = m_Config.MaxObjects + m_Config.MaxPlayers + m_Config.MaxRouteNodes;
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASE_RAID, cost)) { return; }
        if (!m_Reserved) { HCSense(); return; }
        if (!HCLiveParty() || now < m_Camp.LastProbe || now >= m_Ends || m_Due < 1) { HCCancel(); return; }
        if (now < m_Due) { return; }
        if (!HCBaseRaid.HCUnattended(m_Owner, m_Camp, m_Point)) { HCCancel(); return; }
        if (m_Actor.GetGroup().IsInCombat()) { HCCancel(); return; }
        if (!m_Walking && !HCWalkTo(m_Point)) { HCCancel(); return; }
        if (m_Building)
        {
            HCBuildingClaim claims = HCBuildingClaim.HCGet();
            if (!claims || !claims.HCHoldsClaim(m_Camp.GroupId.ToInt(), HCBuildingClaim.HCIdentity(m_Building))) { HCCancel(); return; }
            HCTryLockpick();
            HCFindLoot();
        }
        if (m_Source && HCPerceive(m_Source, m_Source.GetPosition())) { HCTakeLoot(); }
    }

    override void HCCancel()
    {
        if (m_Group)
        {
            m_Group.ClearWaypoints();
            array<vector> restore = m_Original;
            foreach (vector point : restore) { m_Group.AddWaypoint(point); }
            m_Group.SetWaypointBehaviour(m_Behaviour);
        }
        m_Group = null;
        m_Original.Clear();
        m_Reserved = false;
        m_Walking = false;
        m_Camp = null;
        m_Owner = null;
        m_Inventory = null;
        m_Seen = null;
        m_Source = null;
        m_Building = null;
        m_Site = null;
        m_Actor = null;
    }
}

// #203 physical visitors reuse only the perception/reservation/walking helpers.
// No loot, action, notification, dialogue or reward handler is called. Shared
// BaseRaid config supplies bounded sensing, observer range and visit duration.
// Engine/Expansion evidence is the exact inspected header above; new call:
// native EnConvert.c:210 DistanceSq. No spawn or coordinate-driven perception.
class HCAdminVisitorParty : HCXAIBaseRaid
{
    protected HCXAIAdapter m_HCAdapter;
    protected HCXAISiteDirector m_HCDirector;

    void HCOpenVisitor(HCXAIAdapter adapter)
    {
        if (!HCCampProbes.HCVisitorsEnabled() || !HCBaseRaid.HCEnabled()) { return; }
        m_Config = HCBaseRaid.HCConfig();
        m_Healthy = m_Config != null;
        m_HCAdapter = adapter;
        m_HCDirector = HCXAISiteDirector.Active();
    }

    // Provider readiness is independent of a currently available traveller or
    // native acceptance. Bind to this startup's adapter/director, then follow
    // the director's actual policy/settings lifecycle (HCXAISites.c:864-1006).
    override bool HCReady()
    {
        // Native 1.30 boot 077 refused the inline `HCRefusal() == ""` ("Incompatible parameter '@c00'").
        string refusal = HCRefusal();
        return refusal == "";
    }
    override string HCRefusal()
    {
        if (!m_Healthy || !m_Config) { return "CAMP_VISITOR_CONFIG_UNAVAILABLE"; }
        if (!m_HCAdapter || HCXAIService.Adapter() != m_HCAdapter) { return "CAMP_VISITOR_ADAPTER_UNAVAILABLE"; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director != m_HCDirector) { return "CAMP_VISITOR_DIRECTOR_UNAVAILABLE"; }
        string phase = director.Phase();
        if (phase != "run") { return "CAMP_VISITOR_DIRECTOR_" + phase; }
        return "";
    }
    override bool HCPartyAllowed() { return m_Site && m_Site.ProviderFaction == "HCTravellers"; }
    override bool HCCustodyAllowed(PlayerBase actor, EntityAI source) { return false; }

    override bool HCVisit(HCCampModule owner, HCCampRecord camp, int now)
    {
        if (!HCReserve(owner, camp, now)) { return false; }
        camp.LastVisit = now;
        // Intent debit before any route changes; uncertain save never replays.
        if (!owner.Commit(now)) { HCCancel(); return false; }
        m_Due = now;
        m_Ends = now + m_Config.RaidSeconds;
        Print("[HC CampVisitors] reserved walk=pending runtime=PENDING");
        return true;
    }

    void HCVisitStep(int now)
    {
        if (!HCReady() || !HCCampProbes.HCVisitorsEnabled() || !HCCampProbes.HCEnabled() || !HCBaseRaid.HCEnabled()) { return; }
        int cost = m_Config.MaxObjects + m_Config.MaxPlayers + m_Config.MaxRouteNodes;
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASE_RAID, cost)) { return; }
        if (!m_Reserved) { HCSense(); return; }
        if (!HCLiveParty() || now < m_Camp.LastVisit || now >= m_Ends) { HCCancel(); return; }
        if (HCW38SituationRuntime.HCUsed(m_Site.ProposalId)) { HCCancel(); return; }
        if (!HCBaseRaid.HCUnattended(m_Owner, m_Camp, m_Point)) { HCCancel(); return; }
        if (m_Actor.GetGroup().IsInCombat()) { HCCancel(); return; }
        // Normal finite native route, no teleport, item transfer or forced entry.
        if (!m_Walking && !HCWalkTo(m_Point)) { HCCancel(); return; }
    }
}

// Cancellation/attendance during the native continuous action also vetoes its
// completion. Keep the tag after cancellation so a late callback cannot unlock.
modded class eAIBase
{
    bool HCBaseRaidUnlock;
}
modded class ActionUnlockDoors
{
    override void OnFinishProgressServer(ActionData action_data)
    {
        eAIBase raidActor = eAIBase.Cast(action_data.m_Player);
        if (raidActor && raidActor.HCBaseRaidUnlock)
        {
            HCBaseRaidPort bound = HCBaseRaid.HCGet();
            HCXAIBaseRaid raid = HCXAIBaseRaid.Cast(bound);
            if (!raid || !raid.HCUnlockAllowed(raidActor))
            {
                raidActor.HCBaseRaidUnlock = false;
                HCBaseRaid.HCRefuse("BASE_RAID_UNLOCK_COMPLETION_VETOED");
                return;
            }
            raidActor.HCBaseRaidUnlock = false;
        }
        super.OnFinishProgressServer(action_data);
    }
}

// Uses the existing adapter lifecycle; no additional module slot.
modded class HCXAIAdapter
{
    protected ref HCXAIBaseRaid m_HCBaseRaid;
    protected ref HCAdminVisitorParty m_HCVisitorParty;
    protected bool m_HCVisitorFirst;
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer() || HCXAIService.Adapter() != this)
        {
            HCBaseRaid.HCRefuse("BASE_RAID_ADAPTER_NOT_SERVER_OWNER");
            return;
        }
        m_HCBaseRaid = new HCXAIBaseRaid;
        m_HCBaseRaid.HCOpen();
        HCBaseRaid.HCBind(m_HCBaseRaid);
        m_HCVisitorParty = new HCAdminVisitorParty;
        m_HCVisitorParty.HCOpenVisitor(this);
        HCCampProbes.HCBindVisitor(m_HCVisitorParty);
    }
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() == this)
        {
            // Alternate first service on the same bounded consumer so visits
            // cannot starve behind continuous raid sensing (or vice versa).
            int now = HCWorldClock.UTC();
            m_HCVisitorFirst = !m_HCVisitorFirst;
            if (m_HCVisitorFirst && m_HCVisitorParty) { m_HCVisitorParty.HCVisitStep(now); }
            if (m_HCBaseRaid) { m_HCBaseRaid.HCStep(now); }
            if (!m_HCVisitorFirst && m_HCVisitorParty) { m_HCVisitorParty.HCVisitStep(now); }
        }
    }
    override void OnStop()
    {
        if (m_HCVisitorParty) { m_HCVisitorParty.HCCancel(); }
        if (HCCampProbes.HCVisitor() == m_HCVisitorParty) { HCCampProbes.HCBindVisitor(null); }
        m_HCVisitorParty = null;
        if (m_HCBaseRaid) { m_HCBaseRaid.HCCancel(); }
        if (HCBaseRaid.HCGet() == m_HCBaseRaid) { HCBaseRaid.HCBind(null); }
        m_HCBaseRaid = null;
        super.OnStop();
    }
}

// HC-38 cannot borrow the same live lease while its warned base probe owns it.
modded class HCXAIRaidAdapter
{
    override string HCSelect(HCSituationState opportunity)
    {
        string selected = super.HCSelect(opportunity);
        if (HCBaseRaid.HCOwns(selected)) { return ""; }
        return selected;
    }
    override bool HCBegin(HCSituationState opportunity)
    {
        if (opportunity && HCBaseRaid.HCOwns(opportunity.Lease)) { return false; }
        return super.HCBegin(opportunity);
    }
}

// Survivor and transit directors share the same party exclusion as raids.
// Recheck at start because a visitor/warned raid can reserve after selection.
modded class HCXAISituationAdapter
{
    override string HCSelect(HCSituationState opportunity)
    {
        string selected = super.HCSelect(opportunity);
        if (HCBaseRaid.HCOwns(selected)) { return ""; }
        return selected;
    }
    override bool HCBegin(HCSituationState opportunity)
    {
        if (opportunity && HCBaseRaid.HCOwns(opportunity.Lease)) { return false; }
        return super.HCBegin(opportunity);
    }
}

modded class HCXAITransitAdapter
{
    override string HCSelect(HCSituationState opportunity)
    {
        string selected = super.HCSelect(opportunity);
        if (HCBaseRaid.HCOwns(selected)) { return ""; }
        return selected;
    }
    override bool HCBegin(HCSituationState opportunity)
    {
        if (opportunity && HCBaseRaid.HCOwns(opportunity.Lease)) { return false; }
        return super.HCBegin(opportunity);
    }
}
