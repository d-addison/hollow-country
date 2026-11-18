// W5 #129/#130. Bound per 10s tick: maintain <=4 of <=40 nodes by cursor;
// cache GetPlayers once (refuse spawning above 16), inspect one player's one
// candidate, <=40 node lookups/counts, <=16 distance vetoes, one geometry query,
// <=1 spawn and <=1 16384-byte store transaction. No full-map enumeration.
// Inventory callback: <=40 exact-reference comparisons, no file I/O. Shutdown
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
// 1_Core/proto/EnMath.c:225 AbsFloat, :427 Floor; EnConvert.c:210 DistanceSq,
// :30 int.ToString; EnMath3D.c:18 Vector;
// EnScript.c:380,385,389,399,407 arrays; EnDebug.c:96 Print;
// EnString.c:171 ToLower, :240 IndexOf. HCV2ThreatStore/HCGroupIO provide
// bounded persistence (native evidence in Progression/HCProgression.c).
// Static 200m cell/slot anchors are candidate design inputs, not surveyed sites.
// Chernarus only; all placement/replication/CE persistence requires native tests.
// No vanilla edible herb class identified: herbs intentionally omitted.
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

class HCForageModule : HCModule
{
    static const string PATH = "$profile:HollowCountry/forage.json";
    protected static HCForageModule s_HCInstance;
    protected ref HCForageState m_State;
    protected ref array<ref HCForageNode> m_Nodes;
    protected ref array<Man> m_Players;
    protected ref array<Object> m_Exclude;
    protected bool m_Healthy;
    protected bool m_Dirty;
    protected int m_NodeCursor;
    protected int m_PlayerCursor;
    protected int m_SlotCursor;
    protected int m_LastUtc;
    protected float m_Elapsed;

    override string GetName() { return "Forage"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableForage; }

    protected void HCFail()
    {
        m_Healthy = false;
        if (s_HCInstance == this) { s_HCInstance = null; }
        Print("[HC Forage] disabled: clock/schema/store fault; preserve forage.json .tmp .bak");
    }

    protected bool HCValidState(int now)
    {
        if (!m_State || m_State.Version != 1) { return false; }
        if (m_State.WorldName != "chernarusplus") { return false; }
        if (!m_State.Spots || m_State.Spots.Count() > 40) { return false; }
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
        Print(HCV2Admission.Line("Forage", settings.EnableForage, "W5-129", false));
        if (!settings.EnableForage || !HCSurvivalRuntime.HCIsServer()) { return; }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != "chernarusplus")
        {
            Print("[HC Forage] unavailable: only Chernarus surface/cell candidates authored");
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
        m_Players = new array<Man>;
        m_Exclude = new array<Object>;
        m_LastUtc = now;
        m_Healthy = true;
        s_HCInstance = this;
        Print("[HC Forage] ready cap=40 per-cell=3 respawn=1800 lifetime=600; berries/mushrooms seasonal; runtime acceptance pending");
    }

    protected bool HCFlush()
    {
        if (!m_Dirty) { return true; }
        if (!HCV2ThreatStore<HCForageState>.Save(PATH, m_State, 16384)) { HCFail(); return false; }
        m_Dirty = false;
        return true;
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
        m_Dirty = true;
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
        foreach (Man observer : m_Players)
        {
            if (!observer) { return false; }
            if (vector.DistanceSq(observer.GetPosition(), position) < 900) { return false; }
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
        foreach (HCForageNode candidate : m_Nodes)
        {
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
        if (!found && m_Nodes.Count() >= 40) { return null; }
        position = HCPosition(cellX, cellZ, slot);
        if (!HCClearCandidate(position)) { return null; }
        if (!found)
        {
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
        m_Dirty = true;
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
        int work = m_Nodes.Count();
        if (work > 4) { work = 4; }
        for (int tickIndex = 0; tickIndex < work; tickIndex++)
        {
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
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        HCForageNode selected;
        string type;
        if (m_Players.Count() > 0 && m_Players.Count() <= 16)
        {
            int year;
            int month;
            int day;
            int hour;
            int minute;
            GetGame().GetWorld().GetDate(year, month, day, hour, minute);
            type = HCSeasonalType(month, m_SlotCursor);
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
        if (!HCFlush()) { return; }
        if (!selected) { return; }
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
        if (m_Healthy) { HCFlush(); }
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
