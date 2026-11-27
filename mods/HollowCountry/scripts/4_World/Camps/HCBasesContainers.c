// #151 spec -> bounded native-container discovery -> existing camp DTO/store.
// No module slot, world scan, stash copy, item creation or inventory serialization.
// Native evidence scripts-1.30.164289:
// 3_Game/Entities/EntityAI.c:905/946 EEInit/EEDelete;
// Entities/Object.c:215/287/467/511/1219 deletion/position/type/kind/ruin;
// Global/Game.c:1120 IsServer, :1437 IsKindOf (config inheritance);
// gameplay.c:636 GetGame; hearth promotion uses the inspected HCCampModule APIs.
// Hearth native evidence: 4_World/Entities/ItemBase/FireplaceBase.c:1639
// IsBurning; 3_Game/Entities/EntityAI.c:885 GetHierarchyParent;
// Entities/Object.c:517 IsAlive; Entities/Man.c:21 GetIdentity.
// 1_Core/proto/EnScript.c:380/407/463 array Count/Insert/swap Remove;
// :879/900/906 map Find/Set/Remove (native hashmap, no linear membership scan).
// EnConvert.c:210 DistanceSq; EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// ActionConstants.c:111-114 UAMaxDistances.DEFAULT (under Actions/).
// HCCampScan owns inspected TentBase state and native persistent-id evidence.
class HCBasesContainers
{
    protected static ref array<ItemBase> s_Items = new array<ItemBase>;
    protected static ref map<ItemBase, int> s_Indices = new map<ItemBase, int>;
    protected static string s_Refusal;

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        Print("[HC Plan] HC-17 containers reason=" + reason + " runtime=PENDING");
    }

    static bool HCStorageClass(ItemBase item)
    {
        return item && (item.IsKindOf("TentBase") || item.IsKindOf("WoodenCrate") || item.IsKindOf("SeaChest") || item.IsKindOf("Barrel_ColorBase"));
    }

    static bool HCRemember(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCStorageClass(item)) { return false; }
        // Keep packed tents: pitching may follow EEInit. Admission rechecks state.
        int index;
        if (s_Indices.Find(item, index)) { return true; }
        index = s_Items.Insert(item);
        s_Indices.Set(item, index);
        return true;
    }

    static void HCForget(ItemBase item)
    {
        int found;
        if (!s_Indices.Find(item, found)) { return; }
        int last = s_Items.Count() - 1;
        ItemBase moved = s_Items[last];
        s_Items.Remove(found); // Native swap-remove, preserving a dense cursor array.
        s_Indices.Remove(item);
        if (found != last) { s_Indices.Set(moved, found); }
    }

    static int HCCount() { return s_Items.Count(); }
    static ItemBase HCAt(int index)
    {
        if (index < 0 || index >= s_Items.Count()) { return null; }
        return s_Items[index];
    }
}

modded class HCCampModule
{
    protected bool m_HCBasesEnabled;
    protected bool m_HCBasesAdmissionPrinted;
    protected int m_HCBasesCursor;
    // Target one sweep per minute; hard per-tick cap and shared budget take priority.
    // With a stable N, even exhausted shared budgets advance at least one row/tick:
    // worst-case revisit <= N dispatches (deletions may move a row across the cursor).
    protected static const int HC_BASES_CANDIDATES_PER_TICK = 16;
    protected static const float HC_BASES_REVISIT_SECONDS = 60.0;

    override protected void Candidate(FireplaceBase fire, int now, array<Man> roster, map<string, PlayerBase> hcPlayers)
    {
        if (!m_HCBasesEnabled) { super.Candidate(fire, now, roster, hcPlayers); return; }
        if (!fire || fire.IsPendingDeletion() || fire.GetHierarchyParent() || !fire.IsBurning()) { return; }
        // Match the hearth owner's live nearest-group selection. Only native
        // storage rows may be promoted; an existing hearth keeps its binding.
        vector hearthPosition = fire.GetPosition();
        string hearthGroup;
        float hearthBest = 145; // Existing Candidate selection threshold.
        array<Man> hearthPlayers = roster;
        foreach (Man hearthPerson : hearthPlayers)
        {
            PlayerBase hearthPlayer = PlayerBase.Cast(hearthPerson);
            if (!hearthPlayer || !hearthPlayer.IsAlive() || !hearthPlayer.GetIdentity()) { continue; }
            string hearthPeerGroup = HCGroupIdWithPlayers(hearthPlayer, hcPlayers);
            float hearthDistance = vector.DistanceSq(hearthPlayer.GetPosition(), hearthPosition);
            if (hearthPeerGroup != "" && hearthDistance < hearthBest) { hearthBest = hearthDistance; hearthGroup = hearthPeerGroup; }
        }
        array<ref HCCampRecord> hearthCamps = m_Data.Camps;
        HCCampRecord hearthStorage;
        foreach (HCCampRecord hearthCamp : hearthCamps)
        {
            // Preserve the base owner's existing-fire match before group admission.
            if (hearthCamp.FireClass == fire.GetType() && vector.DistanceSq(hearthCamp.Position, hearthPosition) <= 1) { super.Candidate(fire, now, roster, hcPlayers); return; }
            if (hearthGroup == "" || hearthCamp.GroupId != hearthGroup) { continue; }
            string anchorClass = hearthCamp.FireClass;
            if (!GetGame().IsKindOf(anchorClass, "TentBase") && !GetGame().IsKindOf(anchorClass, "WoodenCrate") && !GetGame().IsKindOf(anchorClass, "SeaChest") && !GetGame().IsKindOf(anchorClass, "Barrel_ColorBase")) { continue; }
            hearthStorage = hearthCamp;
        }
        if (hearthStorage)
        {
            // Promote in place, including legacy persisted storage anchors.
            // Native inventories and durable camp/probe metadata stay intact.
            hearthStorage.Position = hearthPosition;
            hearthStorage.FireClass = fire.GetType();
            hearthStorage.FireRef = HCCampScan.RefOf(fire);
            if (hearthStorage.FireRef == "") { hearthStorage.FireRef = hearthStorage.Id + "-hearth"; }
            hearthStorage.LastLit = now;
            hearthStorage.LastScan = 0;
            HCRecognise(hearthStorage, now, 1);
            return;
        }
        super.Candidate(fire, now, roster, hcPlayers);
    }

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (m_Running) { HCCampProbes.HCStart(); }
        m_HCBasesEnabled = m_Running && !FileExist("$profile:HollowCountry/acceptance/base_containers.disable");
        if (!m_HCBasesAdmissionPrinted)
        {
            Print(HCV2Admission.Line("BaseContainers", m_HCBasesEnabled, "HC-17-CONTAINERS", false) + " runtime=PENDING");
            m_HCBasesAdmissionPrinted = true;
        }
    }

    // One server candidate, <=MaxCamps rows and <=MAX_PLAYERS cached actors per
    // dispatch. Reuse named native action reach rather than inventing a radius.
    bool HCBasesWantsPlayers(ItemBase stash, int now)
    {
        if (!stash || stash.IsPendingDeletion() || stash.IsRuined() || !HCCampScan.StorageItem(stash)) { return false; }
        string stashRef = HCCampScan.RefOf(stash);
        if (stashRef == "") { return false; } // Native persistence has not assigned it yet.
        vector stashPosition = stash.GetPosition();
        array<ref HCCampRecord> stashCamps = m_Data.Camps;
        foreach (HCCampRecord knownStash : stashCamps)
        {
            // [HC TickCost] window 12 of 096: include rows before an early return.
            HCServer.HCTickWork().HCCharge(1);
            if (knownStash.FireRef == stashRef && knownStash.FireClass == stash.GetType())
            {
                // Moving a native item never moves the stored camp anchor.
                // A moved/stolen stash cannot become an unreviewed respawn site.
                if (vector.DistanceSq(knownStash.Position, stashPosition) <= UAMaxDistances.DEFAULT * UAMaxDistances.DEFAULT) { knownStash.LastLit = now; }
                return false;
            }
        }
        if (stashCamps.Count() >= HCAILimits.Get().MaxCamps) { return false; }
        return true;
    }

    void HCBasesCandidate(ItemBase stash, int now, array<Man> roster, map<string, PlayerBase> hcPlayers)
    {
        string stashRef = HCCampScan.RefOf(stash);
        vector stashPosition = stash.GetPosition();
        array<ref HCCampRecord> stashCamps = m_Data.Camps;
        array<Man> stashPlayers = roster;
        if (!stashPlayers || stashPlayers.Count() > HCWorldMaterializer.MAX_PLAYERS) { return; }
        string selectedGroup;
        foreach (Man stashPerson : stashPlayers)
        {
            // [HC TickCost] window 12 of 096: include rows before an early return.
            HCServer.HCTickWork().HCCharge(1);
            PlayerBase stashPlayer = PlayerBase.Cast(stashPerson);
            if (!HCBuildingClaim.HCActor(stashPlayer)) { continue; }
            if (vector.DistanceSq(stashPlayer.GetPosition(), stashPosition) > HCBuildingClaimConfig.DEFAULT_ACTION_REACH_METERS * HCBuildingClaimConfig.DEFAULT_ACTION_REACH_METERS) { continue; }
            string nearbyGroup = HCGroupIdWithPlayers(stashPlayer, hcPlayers);
            if (nearbyGroup == "") { continue; }
            // Contested proximity is not ownership evidence. Defer discovery.
            if (selectedGroup != "" && selectedGroup != nearbyGroup) { return; }
            selectedGroup = nearbyGroup;
        }
        if (selectedGroup == "") { return; }
        foreach (HCCampRecord groupStash : stashCamps)
        {
            // [HC TickCost] window 12 of 096: include rows before an early return.
            HCServer.HCTickWork().HCCharge(1);
            if (groupStash.GroupId == selectedGroup) { return; } // Existing hearth/stash wins.
        }
        HCCampRecord stashCamp = new HCCampRecord;
        stashCamp.GroupId = selectedGroup;
        stashCamp.Id = "camp-" + selectedGroup;
        stashCamp.Position = stashPosition;
        stashCamp.FireClass = stash.GetType();
        stashCamp.FireRef = stashRef;
        stashCamp.LastLit = now;
        m_Data.Camps.Insert(stashCamp);
        HCRecognise(stashCamp, now, 2);
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (!m_Running || !m_HCBasesEnabled || !(deltaTime > 0)) { return; }
        int stashCount = HCBasesContainers.HCCount();
        if (stashCount < 1) { return; }
        // Scale the slice toward a minute-long sweep instead of one row per tick.
        // Clamp before converting: large deltas/registries must never cause a burst.
        float desired = stashCount * (deltaTime / HC_BASES_REVISIT_SECONDS);
        int candidates = HC_BASES_CANDIDATES_PER_TICK;
        if (desired < HC_BASES_CANDIDATES_PER_TICK) { candidates = desired; candidates++; }
        if (candidates > stashCount) { candidates = stashCount; }
        array<Man> roster;
        map<string, PlayerBase> hcPlayers;
        for (int scanned = 0; scanned < candidates && scanned < HC_BASES_CANDIDATES_PER_TICK; scanned++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, 1)) { return; }
            m_HCBasesCursor = m_HCBasesCursor % stashCount;
            ItemBase nextStash = HCBasesContainers.HCAt(m_HCBasesCursor);
            m_HCBasesCursor++;
            if (!HCBasesWantsPlayers(nextStash, m_LastUtc)) { continue; }
            if (!roster)
            {
                roster = new array<Man>;
                GetGame().GetPlayers(roster);
                if (roster.Count() <= HCWorldMaterializer.MAX_PLAYERS) { hcPlayers = HCGroupService.HCPlayersFromRoster(roster); }
            }
            HCBasesCandidate(nextStash, m_LastUtc, roster, hcPlayers);
        }
    }
}

modded class ItemBase
{
    protected bool m_HCBasesRegistered;
    override void EEInit()
    {
        super.EEInit();
        m_HCBasesRegistered = HCBasesContainers.HCRemember(this);
    }
    override void EEDelete(EntityAI parent)
    {
        // Unregistered/non-storage objects reach no registry lookup at all.
        if (m_HCBasesRegistered)
        {
            HCBasesContainers.HCForget(this);
            m_HCBasesRegistered = false;
        }
        super.EEDelete(parent);
    }
}
