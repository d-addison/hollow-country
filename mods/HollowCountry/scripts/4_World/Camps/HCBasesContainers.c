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
// 1_Core/proto/EnScript.c:380/394/407/470 Count/Find/Insert/RemoveOrdered;
// EnConvert.c:210 DistanceSq; EnSystem.c:397 FileExist; EnDebug.c:96 Print.
// ActionConstants.c:111-114 UAMaxDistances.DEFAULT (under Actions/).
// HCCampScan owns inspected TentBase state and native persistent-id evidence.
class HCBasesContainers
{
    protected static ref array<ItemBase> s_Items = new array<ItemBase>;
    protected static string s_Refusal;

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        Print("[HC Plan] HC-17 containers reason=" + reason + " runtime=PENDING");
    }

    static void HCRemember(ItemBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !item) { return; }
        // Keep packed tents as candidates: pitching may follow EEInit. Actual
        // admission rechecks state, parent, ruin and native persistent identity.
        if (!item.IsKindOf("TentBase") && !item.IsKindOf("WoodenCrate") && !item.IsKindOf("SeaChest") && !item.IsKindOf("Barrel_ColorBase")) { return; }
        if (s_Items.Find(item) >= 0) { return; }
        // This is a live native-item registry, not a per-camp member snapshot.
        // MaxCampItems bounds the latter, not all storage in the world. Retain
        // overflow for the budgeted one-item cursor; EEDelete releases entries.
        s_Items.Insert(item);
    }

    static void HCForget(ItemBase item)
    {
        int found = s_Items.Find(item);
        if (found >= 0) { s_Items.RemoveOrdered(found); }
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

    override protected void Candidate(FireplaceBase fire, int now)
    {
        if (!m_HCBasesEnabled) { super.Candidate(fire, now); return; }
        if (!fire || fire.IsPendingDeletion() || fire.GetHierarchyParent() || !fire.IsBurning()) { return; }
        // Match the hearth owner's live nearest-group selection. Only native
        // storage rows may be promoted; an existing hearth keeps its binding.
        vector hearthPosition = fire.GetPosition();
        string hearthGroup;
        float hearthBest = 145; // Existing Candidate selection threshold.
        array<Man> hearthPlayers = m_Players;
        foreach (Man hearthPerson : hearthPlayers)
        {
            PlayerBase hearthPlayer = PlayerBase.Cast(hearthPerson);
            if (!hearthPlayer || !hearthPlayer.IsAlive() || !hearthPlayer.GetIdentity()) { continue; }
            string hearthPeerGroup = GroupId(hearthPlayer);
            float hearthDistance = vector.DistanceSq(hearthPlayer.GetPosition(), hearthPosition);
            if (hearthPeerGroup != "" && hearthDistance < hearthBest) { hearthBest = hearthDistance; hearthGroup = hearthPeerGroup; }
        }
        array<ref HCCampRecord> hearthCamps = m_Data.Camps;
        HCCampRecord hearthStorage;
        foreach (HCCampRecord hearthCamp : hearthCamps)
        {
            // Preserve the base owner's existing-fire match before group admission.
            if (hearthCamp.FireClass == fire.GetType() && vector.DistanceSq(hearthCamp.Position, hearthPosition) <= 1) { super.Candidate(fire, now); return; }
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
            if (!Commit(now)) { return; }
            Tell(hearthStorage, "Your group's fire is recognised as a camp. Nearby native structures determine its tier.");
            Print("[HC Plan] HC-17 containers=promoted_to_hearth camp=" + hearthStorage.Id + " runtime=PENDING");
            return;
        }
        super.Candidate(fire, now);
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
    void HCBasesCandidate(ItemBase stash, int now)
    {
        if (!stash || stash.IsPendingDeletion() || stash.IsRuined() || !HCCampScan.StorageItem(stash)) { return; }
        string stashRef = HCCampScan.RefOf(stash);
        if (stashRef == "") { return; } // Native persistence has not assigned it yet.
        vector stashPosition = stash.GetPosition();
        array<ref HCCampRecord> stashCamps = m_Data.Camps;
        foreach (HCCampRecord knownStash : stashCamps)
        {
            if (knownStash.FireRef == stashRef && knownStash.FireClass == stash.GetType())
            {
                // Moving a native item never moves the stored camp anchor.
                // A moved/stolen stash cannot become an unreviewed respawn site.
                if (vector.DistanceSq(knownStash.Position, stashPosition) <= UAMaxDistances.DEFAULT * UAMaxDistances.DEFAULT) { knownStash.LastLit = now; }
                return;
            }
        }
        if (stashCamps.Count() >= HCAILimits.Get().MaxCamps) { return; }
        array<Man> stashPlayers = HCPerfPlayers.HCGet();
        if (!stashPlayers || stashPlayers.Count() > HCWorldMaterializer.MAX_PLAYERS) { return; }
        string selectedGroup;
        foreach (Man stashPerson : stashPlayers)
        {
            PlayerBase stashPlayer = PlayerBase.Cast(stashPerson);
            if (!HCBuildingClaim.HCActor(stashPlayer)) { continue; }
            if (vector.DistanceSq(stashPlayer.GetPosition(), stashPosition) > HCBuildingClaimConfig.DEFAULT_ACTION_REACH_METERS * HCBuildingClaimConfig.DEFAULT_ACTION_REACH_METERS) { continue; }
            string nearbyGroup = GroupId(stashPlayer);
            if (nearbyGroup == "") { continue; }
            // Contested proximity is not ownership evidence. Defer discovery.
            if (selectedGroup != "" && selectedGroup != nearbyGroup) { return; }
            selectedGroup = nearbyGroup;
        }
        if (selectedGroup == "") { return; }
        foreach (HCCampRecord groupStash : stashCamps)
        {
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
        if (!Commit(now)) { return; }
        Print("[HC Plan] HC-17 containers=recognised camp=" + stashCamp.Id + " persistence=native runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (!m_Running || !m_HCBasesEnabled || !(deltaTime > 0)) { return; }
        int stashCount = HCBasesContainers.HCCount();
        if (stashCount < 1) { return; }
        // The shared owner charges the full bounded scan before it runs; no
        // separate scheduler, retry loop or per-container timers. The shared
        // HC_WORK_BASES consumer preserves progress after budget exhaustion.
        int stashCost = m_Data.Camps.Count() * 2 + HCWorldMaterializer.MAX_PLAYERS;
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_BASES, stashCost)) { return; }
        m_HCBasesCursor = m_HCBasesCursor % stashCount;
        ItemBase nextStash = HCBasesContainers.HCAt(m_HCBasesCursor);
        m_HCBasesCursor++;
        HCBasesCandidate(nextStash, m_LastUtc);
    }
}

modded class ItemBase
{
    override void EEInit()
    {
        super.EEInit();
        HCBasesContainers.HCRemember(this);
    }
    override void EEDelete(EntityAI parent)
    {
        HCBasesContainers.HCForget(this);
        super.EEDelete(parent);
    }
}
