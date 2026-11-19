// HC-12 / #150: finite reclaimable records, native supply retained.
// Shared sight native evidence: Ecology/HCEcologyMigrationNative.c:1-14
// (Object.c:238; human.c:1417; Global/DayZPhysics.c:199).
// Supplemental spawning uses existing surface/geometry/distance vetoes and
// HCEcologyMigrationNative.PointHidden for every observer. Two-client pop-in/native
// generator coexistence remains PENDING and never refuses all candidates.
// No new distances: all existing cell/geometry/exclusion values retained.
// 1_Core/proto/EnScript.c:470 RemoveOrdered; shared budgets/cache/save native evidence
// is in Core/HCUnitBudget.c and World/HCWorkBudget.c.
// W5 #129/#130. Bound per 10s tick: maintain <=4 of <=40 nodes by cursor;
// cache GetPlayers once (refuse spawning above 16), inspect one player's one
// candidate, <=40 node lookups/counts, <=16 shared sight tests (<=96 rays),
// <=16 distance vetoes, one geometry query,
// <=1 spawn; creation reservations use bounded 16384-byte stores. No map scan.
// Pickup only marks dirty; routine checkpoints wait >=60s, Stop flushes. Shutdown
// touches <=40 authored item handles. Off: return before allocating any data.
// Installed scripts-1.30.164289 native evidence:
// 3_Game/Global/Game.c:612 ConfigIsExisting, :703 CreateObjectEx, :705
// ObjectDelete, :931 GetWorld, :934 GetWorldName, :945 GetPlayers,
// :1176 SurfaceY, :1180 SurfaceGetType, :1196/1197 water veto,
// :1366 IsBoxCollidingGeometry; 3_Game/Global/World.c:28 GetDate;
// 3_Game/CE/CentralEconomy.c:9,10,17,33 ECE_SETUP/TRACE/CREATEPHYSICS and
// ECE_DYNAMIC_PERSISTENCY (unpicked items are not persisted; native pickup
// enables persistence). 3_Game/constants.c:31-36 ObjIntersect geometry enums;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive;
// 3_Game/Entities/EntityAI.c:882 GetHierarchyRootPlayer, :885 GetHierarchyParent,
// :3377 SetLifetime; 4_World/Entities/ItemBase.c:3906 OnInventoryEnter;
// 4_World/Entities/ItemBase/Edible_Base/{CaninaBerry,SambucusBerry,
// BoletusMushroom,MacrolepiotaMushroom}.c:1 vanilla item classes.
// W43 #202: Edible_Base/{AmanitaMushroom,AuriculariaMushroom,
// CraterellusMushroom,PsilocybeMushroom}.c:1; Gear/Food/MushroomBase.c:3-44.
// Installed stock Chernarus db/types.xml:2545-2555,6486-6495 (nominal=0);
// db/events.xml:925-1044 has none of these four children. No native CE
// generator modified; existing EnableForage preference opts out.
// W6 #129: Edible_Base/Cannabis.c:1,3,13,18,23-28 (native edible herb,
// no cooking, fruit/decay, ActionEat/ActionForceFeed); 1_Core/proto/EnMath.c:38
// RandomInt(min inclusive, max exclusive). Installed addons/gear_food.pbo
// config.bin/CfgVehicles/Cannabis: scope=2, Edible_Base, existing leafy model
// \dz\gear\food\cannabis_seedman.p3d. No custom item/config/art required.
// 1_Core/proto/EnMath.c:225 AbsFloat, :427 Floor; EnConvert.c:210 DistanceSq,
// :30 int.ToString; EnMath3D.c:18 Vector;
// EnScript.c:380,385,389,399,407 arrays; EnDebug.c:96 Print;
// EnString.c:171 ToLower, :240 IndexOf. HCV2ThreatStore/HCGroupIO provide
// bounded persistence (native evidence in Progression/HCProgression.c).
// Static 200m cell/slot anchors are candidate design inputs, not surveyed sites.
// Chernarus only; all placement/replication/CE persistence requires native tests.
// HC-33: runtime uses the existing June berry/herb table in every season.
// Calendar/HCVisualSeasons never gates supply; native generators retain ALL
// orchard fruit and five stock mushrooms. Four otherwise absent vanilla
// mushrooms use the same supplemental slot; poison/food-stage semantics are native.
// The legacy seasonal selector remains available, but no runtime date is read.
// No ActionPickBerry hook: installed Actions/Interact/ActionPickBerry.c:9,39-53
// is deprecated and its server completion is commented out.
// CE/CentralEconomy.c:239-746 exposes no generator lifecycle/harvest ownership
// query; see forage/habitats.json for named refusals and native experiments.
// Herb chance: one of ten rolls on slot 2, all year.
// Reuses all node/cell/cooldown caps;
// <=1 extra random draw per candidate; no extra query, spawn, store or tick.
class HCForageSpot
{
    int CellX;
    int CellZ;
    int NodeSlot;
    int ReadyUtc;
}

class HCForageState
{
    int Version = 1;
    string WorldName;
    ref array<ref HCForageSpot> Spots = new array<ref HCForageSpot>;
}

class HCForageNode
{
    ref HCForageSpot Spot;
    // Engine-owned handle; never keeps an engine item alive or changes storage.
    ItemBase Item;
    bool WasLive;
}

class HCForageSaveJob : HCSaveJob
{
    HCForageModule Owner;
    override string HCName() { return "Forage"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCStepCheckpoint();
    }
}

class HCForageModule : HCModule
{
    static const int RECORD_CAP = 40;
    static const int LIVE_CAP = 40;
    static const string PATH = "$profile:HollowCountry/forage.json";
    protected static HCForageModule s_HCInstance;
    protected ref HCForageState m_State;
    protected ref array<ref HCForageNode> m_Nodes;
    protected ref array<Man> m_Players; // shared HCPerfPlayers snapshot, never Clear()
    protected ref array<Object> m_Exclude;
    protected bool m_Healthy;
    protected bool m_Dirty;
    protected int m_NodeCursor;
    protected int m_PlayerCursor;
    protected int m_SlotCursor;
    protected int m_LastUtc;
    protected int m_SaveUtc;
    protected float m_Elapsed;
    protected int m_Deferred;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected int m_SaveStage;
    protected ref HCForageState m_Snapshot;
    protected ref HCForageSaveJob m_SaveJob;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    protected bool HCVisibilityQualified()
    {
        // Existing placement vetoes run below. Native acceptance is separate.
        return true;
    }

    protected void HCChanged()
    {
        m_Dirty = true;
        m_Revision = m_Revision + 1;
    }

    protected void HCReceipt(string state, string reason)
    {
        int live = 0;
        int records = 0;
        if (m_Nodes)
        {
            records = m_Nodes.Count();
            foreach (HCForageNode node : m_Nodes)
            {
                if (node.Item) { live = live + 1; }
            }
        }
        string line = "[HC Plan] HC-12 forage live=" + live.ToString() + " records=" + records.ToString() + " deferred=" + m_Deferred.ToString();
        Print(line + " state=" + state + " reason=" + reason + " runtime=PENDING");
        // Authored route dispositions, NOT admitted/observed native generators.
        // 8 stock flora + 5 essential-use families; 7 HC supplements; one
        // unsupported generator-control request. Four routes admitted unverified.
        string routeState = state;
        if (state == "pending") { routeState = "on"; }
        Print("[HC Plan] HC-33 native_routes=13 hc_routes=7 unresolved=1 counts=authored admitted=4 observed=0 state=" + routeState + " reason=" + reason + " runtime=PENDING");
        if (state == "pending")
        {
            Print("[HC Refusal] HC-33 native_generator_lifecycle_unexposed; no generator control or orchard grant; runtime=PENDING");
        }
    }

    override string GetName() { return "Forage"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableForage; }

    protected void HCFail()
    {
        m_Healthy = false;
        m_Status.HCPublish("refused", "clock_schema_store_fault");
        HCReceipt("refused", "clock_schema_store_fault");
        if (s_HCInstance == this) { s_HCInstance = null; }
        Print("[HC Forage] disabled: clock/schema/store fault; preserve forage.json .tmp .bak");
    }

    protected bool HCValidState(int now)
    {
        if (!m_State || m_State.Version != 1) { return false; }
        if (m_State.WorldName != "chernarusplus") { return false; }
        if (!m_State.Spots || m_State.Spots.Count() > RECORD_CAP) { return false; }
        for (int spotIndex = 0; spotIndex < m_State.Spots.Count(); spotIndex++)
        {
            HCForageSpot spot = m_State.Spots[spotIndex];
            if (!spot) { return false; }
            if (spot.CellX < 0 || spot.CellX > 76) { return false; }
            if (spot.CellZ < 0 || spot.CellZ > 76) { return false; }
            if (spot.NodeSlot < 0 || spot.NodeSlot > 2) { return false; }
            if (spot.ReadyUtc < 0 || spot.ReadyUtc > now + 1800) { return false; }
            for (int earlierIndex = 0; earlierIndex < spotIndex; earlierIndex++)
            {
                HCForageSpot earlier = m_State.Spots[earlierIndex];
                bool sameCell = earlier.CellX == spot.CellX && earlier.CellZ == spot.CellZ;
                if (sameCell && earlier.NodeSlot == spot.NodeSlot) { return false; }
            }
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        m_Deferred = 0;
        m_Elapsed = 0;
        m_NodeCursor = 0;
        m_PlayerCursor = 0;
        m_SlotCursor = 0;
        m_SaveStage = 0;
        m_Revision = 0;
        m_SnapshotRevision = 0;
        m_Dirty = false;
        Print(HCV2Admission.Line("Forage", settings.EnableForage, "W5-129", false));
        if (!settings.EnableForage || !HCSurvivalRuntime.HCIsServer())
        {
            m_Status.HCPublish("off", "preference_or_authority");
            HCReceipt("off", "preference_or_authority");
            return;
        }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != "chernarusplus")
        {
            m_Status.HCPublish("refused", "world_unsupported");
            HCReceipt("refused", "world_unsupported");
            return;
        }
        int now = HCGroupClock.Utc();
        if (now < 1 || now > 2146000000) { HCFail(); return; }
        if (!HCV2ThreatStore<HCForageState>.CanOpen(PATH)) { HCFail(); return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCForageState>.Load(PATH, 16384, m_State)) { HCFail(); return; }
        }
        else
        {
            m_State = new HCForageState;
            m_State.WorldName = worldName;
            if (!HCV2ThreatStore<HCForageState>.Save(PATH, m_State, 16384)) { HCFail(); return; }
        }
        if (!HCValidState(now)) { HCFail(); return; }
        m_Nodes = new array<ref HCForageNode>;
        foreach (HCForageSpot spot : m_State.Spots)
        {
            HCForageNode node = new HCForageNode;
            node.Spot = spot;
            m_Nodes.Insert(node);
        }
        m_SaveJob = new HCForageSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_Exclude = new array<Object>;
        m_LastUtc = now;
        m_SaveUtc = now;
        m_Healthy = true;
        s_HCInstance = this;
        m_Status.HCPublish("ready", "existing_placement_and_shared_sight_checks_runtime_pending");
        HCReceipt("pending", "visibility_and_native_generator_coexistence");
    }

    // Routine checkpoint: bounded snapshot then existing verified store. A
    // mutation during the snapshot is never lost; barriers finish the newest image.
    int HCStepCheckpoint()
    {
        if (!m_Healthy) { return HCSaveJob.STEP_FAILED; }
        if (m_SaveStage == 0)
        {
            m_Snapshot = new HCForageState;
            m_Snapshot.WorldName = m_State.WorldName;
            foreach (HCForageSpot spot : m_State.Spots)
            {
                HCForageSpot copy = new HCForageSpot;
                copy.CellX = spot.CellX;
                copy.CellZ = spot.CellZ;
                copy.NodeSlot = spot.NodeSlot;
                copy.ReadyUtc = spot.ReadyUtc;
                m_Snapshot.Spots.Insert(copy);
            }
            m_SnapshotRevision = m_Revision;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (!HCV2ThreatStore<HCForageState>.Save(PATH, m_Snapshot, 16384))
        {
            HCFail();
            return HCSaveJob.STEP_FAILED;
        }
        m_SaveStage = 0;
        m_Snapshot = null;
        if (m_SnapshotRevision != m_Revision) { return HCSaveJob.STEP_MORE; }
        m_Dirty = false;
        m_SaveUtc = HCGroupClock.Utc();
        return HCSaveJob.STEP_DONE;
    }

    protected bool HCFlush()
    {
        if (!m_Dirty) { return true; }
        m_SaveJob.HCDirty = true;
        if (HCSaveScheduler.HCFlush(m_SaveJob)) { return true; }
        HCFail();
        return false;
    }

    static void HCCollected(ItemBase item, PlayerBase player)
    {
        if (!s_HCInstance) { return; }
        s_HCInstance.HCObserveCollection(item, player);
    }

    protected void HCObserveCollection(ItemBase item, PlayerBase player)
    {
        if (!m_Healthy || !HCSurvivalRuntime.HCIsServer()) { return; }
        if (!item || !player) { return; }
        if (item.GetHierarchyRootPlayer() != player) { return; }
        foreach (HCForageNode node : m_Nodes)
        {
            if (node.Item != item) { continue; }
            HCReleaseNode(node, player);
            return;
        }
    }

    protected void HCReleaseNode(HCForageNode node, PlayerBase player)
    {
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc || now > 2146000000) { HCFail(); return; }
        // Clear the exact handle BEFORE any reward. Re-dropping or moving the
        // same item cannot grant another reward, spawn or shorten this timer.
        node.Item = null;
        node.WasLive = false;
        int familiarity = HCProgressionModule.HCRecordForage(player);
        node.Spot.ReadyUtc = now + HCSurvivalPolicy.ForageDelay(familiarity);
        HCChanged();
        // The pre-spawn 1800s reservation is already durable. Batch the
        // pickup-relative cooldown update; crash can retain that older timer.
        // No item is reconstructed from a record, so this cannot clone a pickup.
        Print("[HC Forage] node released; refill delay=" + HCSurvivalPolicy.ForageDelay(familiarity).ToString());
    }

    protected vector HCPosition(int cellX, int cellZ, int slot)
    {
        float offsetX = 45 + slot * 55;
        float offsetZ = 155 - slot * 55;
        vector position = Vector(cellX * 200 + offsetX, 0, cellZ * 200 + offsetZ);
        position[1] = GetGame().SurfaceY(position[0], position[2]);
        return position;
    }

    protected string HCSeasonalType(int month, int slot)
    {
        if (month >= 6 && month <= 11)
        {
            if (slot == 2)
            {
                int floraRoll = Math.RandomInt(0, 10);
                if (floraRoll == 0) { return "Cannabis"; }
                // Four vanilla classes absent from active Chernarus generators.
                // Same finite slot, cap, reservation and exact-handle custody.
                if (floraRoll == 1) { return "AmanitaMushroom"; }
                if (floraRoll == 2) { return "AuriculariaMushroom"; }
                if (floraRoll == 3) { return "CraterellusMushroom"; }
                if (floraRoll == 4) { return "PsilocybeMushroom"; }
            }
        }
        if (month >= 6 && month <= 8)
        {
            if (slot == 1) { return "CaninaBerry"; }
            return "SambucusBerry";
        }
        if (month >= 9 && month <= 11)
        {
            if (slot == 0) { return "BoletusMushroom"; }
            if (slot == 1) { return "MacrolepiotaMushroom"; }
            return "CaninaBerry";
        }
        return "";
    }

    protected bool HCClearCandidate(vector position)
    {
        if (!HCVisibilityQualified()) { return false; }
        if (!HCWorldLimits.Position(position)) { return false; }
        if (GetGame().SurfaceIsSea(position[0], position[2])) { return false; }
        if (GetGame().SurfaceIsPond(position[0], position[2])) { return false; }
        string surface;
        GetGame().SurfaceGetType(position[0], position[2], surface);
        surface.ToLower();
        bool forest = surface.IndexOf("cp_conifer_") == 0 || surface.IndexOf("cp_broadleaf_") == 0;
        if (!forest) { return false; }
        float slopeX = GetGame().SurfaceY(position[0] + 1, position[2]);
        float slopeZ = GetGame().SurfaceY(position[0], position[2] + 1);
        if (Math.AbsFloat(slopeX - position[1]) > 0.3) { return false; }
        if (Math.AbsFloat(slopeZ - position[1]) > 0.3) { return false; }
        array<Man> observers = m_Players;
        foreach (Man observer : observers)
        {
            if (!observer) { return false; }
            if (vector.DistanceSq(observer.GetPosition(), position) < 900) { return false; }
            PlayerBase viewer = PlayerBase.Cast(observer);
            if (!viewer) { return false; }
            // Shared native head/cover test; unknown/vehicle observers veto.
            // Reuse its existing ranges and bounded six-ray policy, no new limits.
            if (!HCEcologyMigrationNative.PointHidden(viewer, null, position)) { return false; }
        }
        vector center = position + "0 0.2 0";
        return !GetGame().IsBoxCollidingGeometry(center, "0 0 0", "0.3 0.3 0.3", ObjIntersect.View, ObjIntersect.Geom, m_Exclude);
    }

    protected HCForageNode HCSelectCandidate(PlayerBase player, int slot, int now)
    {
        if (!player || !player.IsAlive()) { return null; }
        vector position = player.GetPosition();
        if (!HCWorldLimits.Position(position)) { return null; }
        int cellX = Math.Floor(position[0] / 200);
        int cellZ = Math.Floor(position[2] / 200);
        HCForageNode found;
        int cellLive;
        int totalLive;
        int reclaim = -1;
        for (int candidateIndex = 0; candidateIndex < m_Nodes.Count(); candidateIndex++)
        {
            HCForageNode candidate = m_Nodes[candidateIndex];
            if (!candidate.Item && !candidate.WasLive && now >= candidate.Spot.ReadyUtc && reclaim < 0)
            {
                reclaim = candidateIndex;
            }
            bool sameCell = candidate.Spot.CellX == cellX && candidate.Spot.CellZ == cellZ;
            if (candidate.Item)
            {
                totalLive = totalLive + 1;
                if (sameCell) { cellLive = cellLive + 1; }
            }
            if (sameCell && candidate.Spot.NodeSlot == slot) { found = candidate; }
        }
        bool present;
        int ready;
        if (found)
        {
            present = found.Item != null;
            ready = found.Spot.ReadyUtc;
        }
        if (!HCSurvivalPolicy.CanRefill(present, cellLive, totalLive, now, ready)) { return null; }
        // A just-deleted handle awaits its maintenance cursor; do not mistake
        // it for a never-spawned node and bypass the post-despawn timer.
        if (found && found.WasLive) { return null; }
        if (totalLive >= LIVE_CAP) { return null; }
        if (!found && m_Nodes.Count() >= RECORD_CAP && reclaim < 0)
        {
            if (m_Deferred < RECORD_CAP) { m_Deferred = m_Deferred + 1; }
            return null;
        }
        position = HCPosition(cellX, cellZ, slot);
        if (!HCClearCandidate(position)) { return null; }
        if (!found)
        {
            if (m_Nodes.Count() >= RECORD_CAP)
            {
                // Same ordered index in both bounded arrays. No live handle,
                // pending disappearance or unexpired spent evidence is evicted.
                m_Nodes.RemoveOrdered(reclaim);
                m_State.Spots.RemoveOrdered(reclaim);
                if (reclaim < m_NodeCursor) { m_NodeCursor = m_NodeCursor - 1; }
                if (m_NodeCursor >= m_Nodes.Count()) { m_NodeCursor = 0; }
            }
            HCForageSpot spot = new HCForageSpot;
            spot.CellX = cellX;
            spot.CellZ = cellZ;
            spot.NodeSlot = slot;
            found = new HCForageNode;
            found.Spot = spot;
            m_State.Spots.Insert(spot);
            m_Nodes.Insert(found);
        }
        // Persist cooldown BEFORE allocating an item, including failed spawns.
        // Dynamic unpicked entities vanish on restart; picked items become
        // ordinary native inventory. Neither case is cloned/reconstructed.
        found.Spot.ReadyUtc = now + 1800;
        HCChanged();
        return found;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Healthy) { return; }
        if (!(deltaTime > 0 && deltaTime <= 60)) { return; }
        m_Elapsed = m_Elapsed + deltaTime;
        if (m_Elapsed < 10) { return; }
        m_Elapsed = 0;
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc || now > 2146000000) { HCFail(); return; }
        m_LastUtc = now;
        m_Units.HCReset(48);
        m_Work.HCReset(5);
        int work = m_Nodes.Count();
        if (work > 4) { work = 4; }
        for (int tickIndex = 0; tickIndex < work; tickIndex++)
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return; }
            if (m_NodeCursor >= m_Nodes.Count()) { m_NodeCursor = 0; }
            HCForageNode current = m_Nodes[m_NodeCursor];
            m_NodeCursor = m_NodeCursor + 1;
            if (!current.WasLive) { continue; }
            if (!current.Item) { HCReleaseNode(current, null); }
            else if (current.Item.GetHierarchyParent())
            {
                HCReleaseNode(current, PlayerBase.Cast(current.Item.GetHierarchyRootPlayer()));
            }
            if (!m_Healthy) { return; }
        }
        // HCPerfPlayers owns the snapshot; do not clear/mutate the shared array.
        m_Players = HCPerfPlayers.HCGet();
        if (!m_Work.HCContinue() || !m_Units.HCTake(RECORD_CAP)) { return; }
        HCForageNode selected;
        string type;
        if (m_Players.Count() > 0 && m_Players.Count() <= 16)
        {
            // Fixed berry/herb content table, independent of calendar and visual
            // seasons. Never select the legacy autumn mushroom supplement:
            // those classes already belong to native trajectory generators. The four
            // additional slot-2 classes have no active Chernarus child.
            type = HCSeasonalType(6, m_SlotCursor);
            if (m_PlayerCursor >= m_Players.Count()) { m_PlayerCursor = 0; }
            PlayerBase player = PlayerBase.Cast(m_Players[m_PlayerCursor]);
            m_PlayerCursor = m_PlayerCursor + 1;
            int slot = m_SlotCursor;
            if (m_PlayerCursor >= m_Players.Count())
            {
                m_SlotCursor = m_SlotCursor + 1;
                if (m_SlotCursor >= 3) { m_SlotCursor = 0; }
            }
            if (type != "" && GetGame().ConfigIsExisting("CfgVehicles " + type))
            {
                selected = HCSelectCandidate(player, slot, now);
            }
        }
        // Routine pickup/retirement checkpoints wait for the bounded interval.
        // Creation still persists its reservation before allocating an item.
        if (m_Dirty && m_SaveJob && now - m_SaveUtc >= 60) { m_SaveJob.HCDirty = true; }
        if (!selected) { return; }
        if (!HCFlush()) { return; }
        int flags = ECE_SETUP | ECE_TRACE | ECE_CREATEPHYSICS | ECE_DYNAMIC_PERSISTENCY;
        Object created = GetGame().CreateObjectEx(type, HCPosition(selected.Spot.CellX, selected.Spot.CellZ, selected.Spot.NodeSlot), flags);
        selected.Item = ItemBase.Cast(created);
        if (!selected.Item)
        {
            if (created) { GetGame().ObjectDelete(created); }
            Print("[HC Forage] create failed; reserved cooldown retained");
            return;
        }
        selected.WasLive = true;
        selected.Item.SetLifetime(600);
        Print("[HC Forage] spawned type=" + type + " nodes=" + m_Nodes.Count().ToString());
    }

    override void OnStop()
    {
        m_Deferred = 0;
        if (m_Healthy) { HCFlush(); }
        if (m_SaveJob)
        {
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.Owner = null;
            m_SaveJob = null;
        }
        m_Status.HCPublish("off", "stopped");
        HCReceipt("off", "stopped");
        m_Healthy = false;
        if (s_HCInstance == this) { s_HCInstance = null; }
        if (!m_Nodes) { return; }
        foreach (HCForageNode node : m_Nodes)
        {
            // Stop/restart cannot orphan an unpicked item. Never delete a
            // picked item, its native owner or anybody else's world loot.
            if (node.Item)
            {
                if (!node.Item.GetHierarchyParent()) { GetGame().ObjectDelete(node.Item); }
            }
        }
        m_Nodes = null;
        m_State = null;
        m_Snapshot = null;
        m_Players = null;
        m_Exclude = null;
    }
}

modded class ItemBase
{
    override void OnInventoryEnter(Man player)
    {
        super.OnInventoryEnter(player);
        HCForageModule.HCCollected(this, PlayerBase.Cast(player));
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCForageModule);
    }
}
