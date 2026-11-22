// #136 infected open / break down closed building doors (variant-specific).
// Server only, gated on the existing EnableInfected setting; source
// implementation, runtime acceptance PENDING (nothing observed in DayZ yet).
//
// Native evidence, installed scripts-1.30.164289:
//  3_Game/Entities/Building.c:5-10 DoorManipulationParams, :31 GetDoorCount,
//    :52 IsDoorClosed, :55 IsDoorLocked, :58 PlayDoorSound, :61 OpenDoor,
//    :70 UnlockDoor(index, animate), :73 GetDoorSoundPos (world space),
//    :141-158 CanDoorBeOpened(params) (m_CheckIfLocked semantics), :317
//    GetDoorInfoHolder; 3_Game/Entities/AdditionalDoorsInfo.c:11
//    m_LockCompatibilityBitMask (lockpick by default, :32), :82
//    GetSingleDoorInfo; 3_Game/Enums/EBuildingLockTypes.c:7-10 LOCKPICK.
//  HC-8 external-lock refusal mirrors native ActionUnlockDoors.c:39-51:
//    AdditionalDoorInfo.m_RelatedInventorySlotNames (AdditionalDoorsInfo.c:12),
//    EntityAI.FindAttachmentBySlotName (3_Game/Entities/EntityAI.c:1897),
//    ItemBase.IsExternalLockType (4_World/Entities/ItemBase.c:4852).
//    Man.GetIdentity (3_Game/Entities/Man.c:21) refuses unproven NPC targets.
//  4_World/Entities/Building/Bunker.c:1 Bunker (its CanDoorBeOpened :47 casts
//    the caller to PlayerBase) and 4_World/Entities/ItemBase/ContainerLocked.c:1
//    ContainerLockedBase are excluded outright.
//  3_Game/Entities/DayZInfected.c:13-18 mind states, :107 GetInputController;
//    3_Game/Entities/DayZInfectedInputController.c:9 GetMindState, :10
//    GetTargetEntity (the same native target ZombieBase.ChaseAttackLogic reads,
//    4_World/Entities/Creatures/Infected/ZombieBase.c:685/:726); ZombieBase.c:1090
//    IsCrawling; 3_Game/Entities/EntityAI.c:744 IsZombieMilitary.
//  3_Game/Global/Game.c:930 GetObjectsAtPosition3D, :1120 IsServer;
//    3_Game/Entities/Object.c:215 IsPendingDeletion, :287 GetPosition, :467
//    GetType, :517 IsAlive; 1_Core/proto/EnConvert.c:210 DistanceSq, :284 Dot,
//    :30 int.ToString; EnMath.c:54 RandomIntInclusive, :553 Min;
//    EnScript.c:380/385/407/463 Count/Clear/Insert/Remove; EnDebug.c:96 Print.
//  Shared repo services: HCPerfPlayers / HCWorkBudget (World/HCWorkBudget.c)
//    and HCSearchNoise.EmitAt (Loot/HCSearchNoise.c; native NoiseSystem
//    AddNoisePos 3_Game/Noise.c:7, LoadFromPath :25, Game.c:738).
//
// Driven from players, never from a map-wide infected scan. Per core tick
// (1 s default): <=2 players from the shared snapshot (cursor, <=32 roster),
// each ONE 8 m GetObjectsAtPosition3D, <=128 results inspected, <=4 buildings,
// <=8 door indices each (retained building cursor; <=64 total indices/tick,
// HCUnitBudget), <=6 watched doors per player; then <=4 watched doors (hot
// pressure first, then a cursor), each ONE 2 m GetObjectsAtPosition3D at the
// door sound point, <=128 results inspected, <=8 infected qualified. Script-only
// expiry passes over <=64 pressure rows and <=64 building cursors.
// <=1 native noise per tick. Every native
// query consumes one HCWorkBudget unit (limit 6, 4 ms cooperative slice).
//
// Not omniscient: an infected counts only when alive, not crawling, natively
// ALERTED/CHASE/FIGHT, within 2 m of the door, and its native target is a
// living identity-bearing player (or, with no target, the watching player) within 8 m of the
// door who is either within 2.5 m of it or on the opposite side.
//
// Rules held: no teleport/forced movement of anyone, never closes, locks or
// blocks a door, only server-side OpenDoor/UnlockDoor (doors replicate
// natively), no persistence or new settings/config. A bounded cosmetic RPC
// sends pressure progress to nearby clients; it grants no gameplay authority.
// No infected attack
// animation is started: StartCommand_Attack (DayZInfected.c:112) is consumed
// inside the native command handler, whose FightLogic (ZombieBase.c:629-660)
// would apply melee damage to m_ActualTarget (the player) rather than the door,
// so the warning uses client-side vanilla attack foley at the door instead.
class HCInfectedDoorsModule : HCModule
{
    // Fortify: doors compared when binding a barricade to its nearest door entry, and the
    // slack (seconds) added to the Grace lapse test for barricade pressure.
    static const int MAX_BARRICADE_BIND_DOORS = 64;
    static const float GRACE_SLACK = 0.25;
    protected bool m_Running;
    protected bool m_Printed;
    protected float m_Clock;
    protected float m_LogAt = 600;
    protected int m_PlayerCursor;
    protected int m_DoorCursor;
    protected int m_NoiseThisTick;
    protected int m_Hits;
    protected int m_Opened;
    protected int m_Broken;
    protected int m_Refused;
    // #160 HC-S001: cause of the latest refusal; read by the summary line.
    protected string m_LastRefusal;
    protected int m_Full;
    protected int m_BuildingFilterRejected;
    protected ref map<string, bool> m_BuildingTypes;
    protected ref array<ref HCInfectedDoorPressure> m_Doors;
    protected ref array<ref HCInfectedDoorScan> m_Scans;
    protected ref array<Object> m_Objects;
    protected ref array<CargoBase> m_Proxies;
    protected ref HCWorkBudget m_Budget;
    protected ref HCUnitBudget m_IndexBudget;

    override string GetName() { return "InfectedDoors"; }

    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "door_pressure_started");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        if (!settings) { return false; }
        return settings.EnableInfected;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer() || m_Running || !IsEnabled(settings)) { return; }
        if (!m_Printed)
        {
            Print(HCV2Admission.Line("InfectedDoors", true, "W6-136", false));
            m_Printed = true;
        }
        m_Doors = new array<ref HCInfectedDoorPressure>;
        m_Scans = new array<ref HCInfectedDoorScan>;
        m_Objects = new array<Object>;
        m_Proxies = new array<CargoBase>;
        m_Budget = new HCWorkBudget;
        m_IndexBudget = new HCUnitBudget;
        m_BuildingTypes = new map<string, bool>;
        m_BuildingFilterRejected = 0;
        m_PlayerCursor = 0;
        m_DoorCursor = 0;
        m_Hits = 0;
        m_Opened = 0;
        m_Broken = 0;
        m_Refused = 0;
        m_LastRefusal = "none";
        m_Full = 0;
        m_Clock = 0;
        m_LogAt = 600;
        m_Running = true;
        int maxDoors = HCInfectedDoorPolicy.MAX_DOORS;
        int playersPerTick = HCInfectedDoorPolicy.PLAYERS_PER_TICK;
        int doorsPerTick = HCInfectedDoorPolicy.DOORS_PER_TICK;
        int maxIndices = HCInfectedDoorPolicy.MAX_DOOR_INDICES_PER_TICK;
        int maxCursors = HCInfectedDoorPolicy.MAX_BUILDING_CURSORS;
        Print("[HC Plan] HC-8 door_cursor=bounded max_indices=" + maxIndices.ToString() + " state=on max_cursors=" + maxCursors.ToString() + " npc_targets=refused runtime=PENDING");
        Print("[HC Doors] ready players_per_tick=" + playersPerTick.ToString() + " doors_per_tick=" + doorsPerTick.ToString() + " max_doors=" + maxDoors.ToString() + " watch_m=8 door_m=2 common_s=6-10 heavy_hits=4-6 cooldown_s=45; door replication/sound acceptance pending");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 300) { return; }
        m_Clock = m_Clock + deltaTime;
        m_NoiseThisTick = 0;
        m_Budget.HCReset(HCInfectedDoorPolicy.PLAYERS_PER_TICK + HCInfectedDoorPolicy.DOORS_PER_TICK);
        m_IndexBudget.HCReset(HCInfectedDoorPolicy.MAX_DOOR_INDICES_PER_TICK);
        ExpireScans();
        WatchPlayers();
        ExpireDoors();
        VisitDoors();
        HCReached.Mark("infected_doors.visit");
        if (m_Clock >= m_LogAt)
        {
            m_LogAt = m_Clock + 600;
            int watched = m_Doors.Count();
            Print("[HC Doors] summary watched=" + watched.ToString() + " hits=" + m_Hits.ToString() + " opened=" + m_Opened.ToString() + " broken=" + m_Broken.ToString() + " refused=" + m_Refused.ToString() + " table_full=" + m_Full.ToString() + " building_filter_rejected=" + m_BuildingFilterRejected.ToString() + " runtime=PENDING");
            if (m_Refused > 0)
            {
                Print("[HC Doors] summary refusal last_refusal=" + m_LastRefusal + " refused=" + m_Refused.ToString() + " runtime-unverified");
            }
            m_Hits = 0;
            m_Opened = 0;
            m_Broken = 0;
            m_Refused = 0;
            m_LastRefusal = "none";
            m_Full = 0;
            m_BuildingFilterRejected = 0;
        }
    }

    override void OnStop()
    {
        m_Running = false;
        if (m_Doors) { m_Doors.Clear(); }
        if (m_Scans) { m_Scans.Clear(); }
        if (m_Objects) { m_Objects.Clear(); }
        if (m_Proxies) { m_Proxies.Clear(); }
        m_Doors = null;
        m_Scans = null;
        m_Objects = null;
        m_Proxies = null;
        m_Budget = null;
        m_IndexBudget = null;
        m_BuildingTypes = null;
    }

    protected void WatchPlayers()
    {
        array<Man> players = HCPerfPlayers.HCGet();
        int count = Math.Min(HCInfectedDoorPolicy.MAX_PLAYERS, players.Count());
        if (count < 1) { return; }
        int visits = Math.Min(HCInfectedDoorPolicy.PLAYERS_PER_TICK, count);
        for (int visit = 0; visit < visits; visit++)
        {
            if (!m_Budget.HCContinue())
            {
                m_Budget.HCDeferred(GetName(), visits - visit);
                return;
            }
            if (m_PlayerCursor >= count) { m_PlayerCursor = 0; }
            PlayerBase player = PlayerBase.Cast(players[m_PlayerCursor]);
            m_PlayerCursor = m_PlayerCursor + 1;
            if (!player || !player.IsAlive()) { continue; }
            WatchAround(player);
        }
    }

    protected bool Eligible(Building building)
    {
        if (!building || building.IsPendingDeletion()) { return false; }
        if (Bunker.Cast(building)) { return false; }
        if (ContainerLockedBase.Cast(building)) { return false; }
        string className = building.GetType();
        bool eligible;
        if (!m_BuildingTypes.Find(className, eligible))
        {
            eligible = HCBuildingAncestry(className);
            // Bound retained config facts; uncached classes still use the same filter.
            if (m_BuildingTypes.Count() < 256) { m_BuildingTypes.Set(className, eligible); }
        }
        if (!eligible) { m_BuildingFilterRejected = m_BuildingFilterRejected + 1; }
        return eligible;
    }

    // #300: script Building also covers static vehicle wrecks. The installed
    // structures_wrecks config has no common wreck-only root: e.g. the wine
    // sedan -> Land_Wreck_Car_ThreeDoors -> HouseNoDestruct. Inspect every
    // CfgVehicles ancestor for the wreck family token, including the concrete
    // class, so renamed descendants are covered without a concrete-class list.
    // Transport (Car/Boat) and Air are the installed live-vehicle roots.
    // Native Game.c:602 ConfigGetBaseName; :1437 IsKindOf uses config ancestry
    // too, rather than the Enforce script inheritance tree.
    protected bool HCBuildingAncestry(string className)
    {
        string currentClass = className;
        for (int depth = 0; depth < 32; depth++)
        {
            string family = currentClass;
            if (family.Length() > 256) { return false; }
            family.ToLower();
            if (family.IndexOf("wreck") >= 0 || family == "transport" || family == "air") { return false; }
            string path = "CfgVehicles " + currentClass;
            if (!GetGame().ConfigIsExisting(path)) { return false; }
            string parentName;
            if (!GetGame().ConfigGetBaseName(path, parentName) || parentName == "") { return true; }
            if (parentName == currentClass) { return false; }
            currentClass = parentName;
        }
        // Malformed/cyclic or over-budget ancestry cannot establish a building.
        return false;
    }

    protected void WatchAround(PlayerBase player)
    {
        vector origin = player.GetPosition();
        float radiusSq = HCInfectedTuning.Get().Doors.WatchRadius * HCInfectedTuning.Get().Doors.WatchRadius;
        m_Objects.Clear();
        m_Proxies.Clear();
        GetGame().GetObjectsAtPosition3D(origin, HCInfectedTuning.Get().Doors.WatchRadius, m_Objects, m_Proxies);
        int inspected = Math.Min(m_Objects.Count(), HCInfectedDoorPolicy.MAX_OBJECTS_PER_QUERY);
        int buildings = 0;
        int watched = 0;
        for (int objectIndex = 0; objectIndex < inspected; objectIndex++)
        {
            if (watched >= HCInfectedDoorPolicy.MAX_DOORS_PER_PLAYER || buildings >= HCInfectedDoorPolicy.MAX_BUILDINGS_PER_PLAYER) { break; }
            Building building = Building.Cast(m_Objects[objectIndex]);
            if (!Eligible(building)) { continue; }
            int doorCount = building.GetDoorCount();
            if (doorCount < 1) { continue; }
            buildings = buildings + 1;
            HCInfectedDoorScan scan = HCScanFor(building);
            if (!scan) { continue; }
            int indices = Math.Min(doorCount, HCInfectedDoorPolicy.DOOR_INDICES_PER_BUILDING);
            for (int offset = 0; offset < indices; offset++)
            {
                if (watched >= HCInfectedDoorPolicy.MAX_DOORS_PER_PLAYER) { break; }
                // Advance only after admission; resume this index on a yield.
                if (!m_IndexBudget.HCTake(1))
                {
                    m_Objects.Clear();
                    m_Proxies.Clear();
                    return;
                }
                if (scan.m_NextIndex >= doorCount) { scan.m_NextIndex = 0; }
                int doorIndex = scan.m_NextIndex;
                scan.m_NextIndex = scan.m_NextIndex + 1;
                if (!building.IsDoorClosed(doorIndex)) { continue; }
                if (vector.DistanceSq(building.GetDoorSoundPos(doorIndex), origin) > radiusSq) { continue; }
                if (Watch(building, doorIndex, player)) { watched = watched + 1; }
            }
        }
        m_Objects.Clear();
        m_Proxies.Clear();
    }

    // Bounded lookup; a claimed building gains no immunity. HC-17 will bind
    // read-only claim facts here serially; native lock rules stay authoritative.
    protected HCInfectedDoorScan HCScanFor(Building building)
    {
        foreach (HCInfectedDoorScan existing : m_Scans)
        {
            if (existing.m_Building != building) { continue; }
            existing.m_WatchUntil = m_Clock + HCInfectedTuning.Get().Doors.WatchSeconds;
            return existing;
        }
        if (m_Scans.Count() >= HCInfectedDoorPolicy.MAX_BUILDING_CURSORS)
        {
            m_Full = m_Full + 1;
            return null;
        }
        HCInfectedDoorScan created = new HCInfectedDoorScan;
        created.m_Building = building;
        created.m_WatchUntil = m_Clock + HCInfectedTuning.Get().Doors.WatchSeconds;
        m_Scans.Insert(created);
        return created;
    }

    protected void ExpireScans()
    {
        for (int row = m_Scans.Count() - 1; row >= 0; row--)
        {
            HCInfectedDoorScan scan = m_Scans[row];
            if (!scan.m_Building || scan.m_Building.IsPendingDeletion() || m_Clock > scan.m_WatchUntil)
            {
                m_Scans.Remove(row);
            }
        }
    }

    // <=64 script comparisons; refuses (counted) when the table is full.
    protected bool Watch(Building building, int doorIndex, PlayerBase player)
    {
        foreach (HCInfectedDoorPressure existing : m_Doors)
        {
            if (existing.m_Building != building || existing.m_Index != doorIndex) { continue; }
            existing.m_Player = player;
            existing.m_WatchUntil = m_Clock + HCInfectedTuning.Get().Doors.WatchSeconds;
            return true;
        }
        if (m_Doors.Count() >= HCInfectedDoorPolicy.MAX_DOORS)
        {
            m_Full = m_Full + 1;
            return false;
        }
        HCInfectedDoorPressure created = new HCInfectedDoorPressure;
        created.m_Building = building;
        created.m_Index = doorIndex;
        created.m_Player = player;
        created.m_WatchUntil = m_Clock + HCInfectedTuning.Get().Doors.WatchSeconds;
        created.m_OpenNeeded = Math.RandomIntInclusive(HCInfectedTuning.Get().Doors.OpenMinSeconds, HCInfectedTuning.Get().Doors.OpenMaxSeconds);
        created.m_HitsNeeded = Math.RandomIntInclusive(HCInfectedTuning.Get().Doors.HitsMin, HCInfectedTuning.Get().Doors.HitsMax);
        m_Doors.Insert(created);
        return true;
    }

    // Script-only pass over <=64 rows; deleted buildings and expired rows go.
    protected void ExpireDoors()
    {
        for (int row = m_Doors.Count() - 1; row >= 0; row--)
        {
            HCInfectedDoorPressure entry = m_Doors[row];
            if (!entry.m_Building || entry.m_Building.IsPendingDeletion() || HCInfectedDoorPolicy.Expired(m_Clock, entry.m_WatchUntil, entry.m_CooldownUntil))
            {
                m_Doors.Remove(row);
            }
        }
    }

    protected void VisitDoors()
    {
        int visited = 0;
        float hotSince = m_Clock - HCInfectedTuning.Get().Doors.Grace;
        // Hot pressure first so a sustained push is not starved by the cursor.
        for (int hotIndex = 0; hotIndex < m_Doors.Count(); hotIndex++)
        {
            if (visited >= HCInfectedDoorPolicy.DOORS_PER_TICK) { break; }
            HCInfectedDoorPressure hot = m_Doors[hotIndex];
            if (hot.m_LastHot < hotSince || m_Clock < hot.m_CooldownUntil) { continue; }
            if (!m_Budget.HCContinue())
            {
                m_Budget.HCDeferred(GetName(), m_Doors.Count() - hotIndex);
                return;
            }
            Visit(hot);
            visited = visited + 1;
        }
        int total = m_Doors.Count();
        int examined = 0;
        while (visited < HCInfectedDoorPolicy.DOORS_PER_TICK && examined < total)
        {
            if (m_DoorCursor >= total) { m_DoorCursor = 0; }
            HCInfectedDoorPressure cold = m_Doors[m_DoorCursor];
            examined = examined + 1;
            if (cold.m_VisitedAt == m_Clock || m_Clock < cold.m_CooldownUntil)
            {
                m_DoorCursor = m_DoorCursor + 1;
                continue;
            }
            // Cursor is retained on this row when the budget yields.
            if (!m_Budget.HCContinue())
            {
                m_Budget.HCDeferred(GetName(), total - examined + 1);
                return;
            }
            m_DoorCursor = m_DoorCursor + 1;
            Visit(cold);
            visited = visited + 1;
        }
    }

    protected int LockState(Building building, int doorIndex)
    {
        if (!building.IsDoorLocked(doorIndex)) { return HCInfectedDoorPolicy.LOCK_NONE; }
        AdditionalDoorInfosHolder holder = building.GetDoorInfoHolder();
        if (!holder) { return HCInfectedDoorPolicy.LOCK_PROTECTED; }
        AdditionalDoorInfo info = holder.GetSingleDoorInfo(doorIndex);
        if (!info) { return HCInfectedDoorPolicy.LOCK_PROTECTED; }
        if (info.m_RelatedInventorySlotNames)
        {
            int slots = info.m_RelatedInventorySlotNames.Count();
            if (slots > HCInfectedDoorPolicy.MAX_LOCK_SLOTS) { return HCInfectedDoorPolicy.LOCK_PROTECTED; }
            for (int slotIndex = 0; slotIndex < slots; slotIndex++)
            {
                ItemBase attachment = ItemBase.Cast(building.FindAttachmentBySlotName(info.m_RelatedInventorySlotNames[slotIndex]));
                if (attachment && attachment.IsExternalLockType()) { return HCInfectedDoorPolicy.LOCK_PROTECTED; }
            }
        }
        int lockpick = 1 << EBuildingLockType.LOCKPICK;
        if ((info.m_LockCompatibilityBitMask & lockpick) == 0) { return HCInfectedDoorPolicy.LOCK_PROTECTED; }
        return HCInfectedDoorPolicy.LOCK_BREAKABLE;
    }

    protected int Qualify(ZombieBase infected, HCInfectedDoorPressure entry, vector doorPos)
    {
        int kind = HCInfectedDoorPolicy.Kind(infected.IsAlive(), infected.IsCrawling(), infected.IsZombieMilitary(), infected.GetType());
        if (kind == HCInfectedDoorPolicy.KIND_NONE) { return kind; }
        DayZInfectedInputController controller = infected.GetInputController();
        if (!controller) { return HCInfectedDoorPolicy.KIND_NONE; }
        if (!HCInfectedDoorPolicy.Pursuing(controller.GetMindState())) { return HCInfectedDoorPolicy.KIND_NONE; }
        EntityAI targetEntity = controller.GetTargetEntity();
        PlayerBase quarry = PlayerBase.Cast(targetEntity);
        // Chasing something else (animal, decoy): not this door's business.
        if (targetEntity && !quarry) { return HCInfectedDoorPolicy.KIND_NONE; }
        if (!quarry) { quarry = PlayerBase.Cast(entry.m_Player); }
        // PlayerBase also covers provider human AI. Their observation path is
        // unqualified; never admit NPC-target pressure from that cast alone.
        if (!quarry || !quarry.IsAlive() || !quarry.GetIdentity()) { return HCInfectedDoorPolicy.KIND_NONE; }
        float distanceSq = vector.DistanceSq(quarry.GetPosition(), doorPos);
        vector toPlayer = quarry.GetPosition() - doorPos;
        vector toInfected = infected.GetPosition() - doorPos;
        toPlayer[1] = 0;
        toInfected[1] = 0;
        if (!HCInfectedDoorPolicy.PlayerQualifies(distanceSq, vector.Dot(toPlayer, toInfected))) { return HCInfectedDoorPolicy.KIND_NONE; }
        return kind;
    }

    protected void Visit(HCInfectedDoorPressure entry)
    {
        entry.m_VisitedAt = m_Clock;
        Building building = entry.m_Building;
        int doorIndex = entry.m_Index;
        if (!Eligible(building) || doorIndex < 0 || doorIndex >= building.GetDoorCount())
        {
            entry.m_WatchUntil = -1;
            return;
        }
        // A fortification pack barricade can stand in front of an open door too.
        bool doorClosed = building.IsDoorClosed(doorIndex);
        bool fortified = HCFortifyBridge.HCActive();
        if (!doorClosed && !fortified)
        {
            entry.HCAdvance(HCInfectedDoorPolicy.KIND_NONE, HCInfectedDoorPolicy.LOCK_NONE, m_Clock);
            return;
        }
        vector doorPos = building.GetDoorSoundPos(doorIndex);
        m_Objects.Clear();
        m_Proxies.Clear();
        GetGame().GetObjectsAtPosition3D(doorPos, HCInfectedTuning.Get().Doors.DoorRadius, m_Objects, m_Proxies);
        int inspected = Math.Min(m_Objects.Count(), HCInfectedDoorPolicy.MAX_OBJECTS_PER_QUERY);
        int candidates = 0;
        int kind = HCInfectedDoorPolicy.KIND_NONE;
        ZombieBase chosen;
        // The barricade search is independent of the infected cap below.
        Object barricade;
        if (fortified) { barricade = HCDoorBarricade(entry, building, doorIndex, doorPos, inspected); }
        for (int objectIndex = 0; objectIndex < inspected; objectIndex++)
        {
            ZombieBase infected = ZombieBase.Cast(m_Objects[objectIndex]);
            if (!infected) { continue; }
            candidates = candidates + 1;
            if (candidates > HCInfectedDoorPolicy.MAX_INFECTED_PER_DOOR) { break; }
            int candidateKind = Qualify(infected, entry, doorPos);
            if (candidateKind > kind)
            {
                kind = candidateKind;
                chosen = infected;
            }
        }
        m_Objects.Clear();
        m_Proxies.Clear();
        // Pressure on a barricaded door lands on the barricade through the native
        // damage path at the configured rate; the door itself is untouched until it falls.
        if (barricade && kind != HCInfectedDoorPolicy.KIND_NONE && chosen)
        {
            HCPressBarricade(entry, barricade, kind, chosen, doorPos);
            return;
        }
        if (!doorClosed)
        {
            entry.HCAdvance(HCInfectedDoorPolicy.KIND_NONE, HCInfectedDoorPolicy.LOCK_NONE, m_Clock);
            return;
        }
        int lockState = HCInfectedDoorPolicy.LOCK_NONE;
        if (kind != HCInfectedDoorPolicy.KIND_NONE) { lockState = LockState(building, doorIndex); }
        int action = entry.HCAdvance(kind, lockState, m_Clock);
        // A cue is sent on first contact and as pressure builds, including
        // common infected visits with ACTION_NONE. No cue on the giving hit,
        // refused lock, stale contact, cooldown or already-open door.
        if (chosen && entry.m_LastHot == m_Clock && m_Clock >= entry.m_CooldownUntil)
        {
            if (action == HCInfectedDoorPolicy.ACTION_NONE || action == HCInfectedDoorPolicy.ACTION_HIT)
            {
                HCWarnPressure(entry, kind, doorPos);
            }
        }
        if (action == HCInfectedDoorPolicy.ACTION_NONE || !chosen) { return; }
        Apply(entry, action, chosen, doorPos);
    }

    // The standing door barricade that belongs to this door entry, or null. A bound
    // barricade is cached on the entry (no rescan while it stands). Otherwise the nearest
    // standing one among the already queried objects is taken (native cast filter first,
    // no extra query), then bound only if no other door of the building is nearer to it,
    // so an adjacent door's barricade is never pressed from the wrong entry.
    protected Object HCDoorBarricade(HCInfectedDoorPressure entry, Building building, int doorIndex, vector doorPos, int inspected)
    {
        if (entry.m_Barricade)
        {
            if (HCFortifyBridge.HCStanding(entry.m_Barricade)) { return entry.m_Barricade; }
            entry.m_Barricade = null;
        }
        Object nearest;
        float nearestSq = 1000000;
        for (int index = 0; index < inspected; index++)
        {
            Object candidate = m_Objects[index];
            if (candidate == entry.m_ForeignBarricade || !HCFortifyBridge.HCBlocksDoor(candidate)) { continue; }
            float candidateSq = vector.DistanceSq(candidate.GetPosition(), doorPos);
            if (candidateSq < nearestSq)
            {
                nearestSq = candidateSq;
                nearest = candidate;
            }
        }
        if (!nearest) { return null; }
        if (!HCBarricadeBelongs(building, doorIndex, nearest))
        {
            entry.m_ForeignBarricade = nearest;
            return null;
        }
        entry.m_Barricade = nearest;
        return nearest;
    }

    // True when no other door of the building is nearer to the barricade than this one.
    // Native GetDoorSoundPos only; <=MAX_BARRICADE_BIND_DOORS indices, once per found barricade.
    protected bool HCBarricadeBelongs(Building building, int doorIndex, Object barricade)
    {
        vector at = barricade.GetPosition();
        float ownSq = vector.DistanceSq(at, building.GetDoorSoundPos(doorIndex));
        int count = Math.Min(building.GetDoorCount(), MAX_BARRICADE_BIND_DOORS);
        for (int other = 0; other < count; other++)
        {
            if (other == doorIndex) { continue; }
            if (vector.DistanceSq(at, building.GetDoorSoundPos(other)) < ownSq) { return false; }
        }
        return true;
    }

    // One bounded breach step per visit: elapsed time is clamped to the door
    // tuning MaxStep and a lapsed contact starts fresh, like HCAdvance. The lapse
    // limit carries a small slack so float-summed clocks and tick jitter never make a
    // contact that is exactly Grace old look lapsed.
    // A qualified contact keeps the door hot, so the next visit comes from the hot-first
    // pass (the cold cursor alone revisits too rarely to ever build a step with several
    // players). Only a real refusal (damage disabled by the server, no standing part)
    // leaves it cold, so a refused barricade cannot starve the other doors (HC-8).
    protected void HCPressBarricade(HCInfectedDoorPressure entry, Object barricade, int kind, ZombieBase chosen, vector doorPos)
    {
        float step = 0;
        if (entry.m_BarricadeAt >= 0 && m_Clock - entry.m_BarricadeAt <= HCInfectedTuning.Get().Doors.Grace + GRACE_SLACK)
        {
            step = Math.Min(m_Clock - entry.m_BarricadeAt, HCInfectedTuning.Get().Doors.MaxStep);
        }
        entry.m_BarricadeAt = m_Clock;
        int result = HCFortifyBridge.HCBreach(barricade, step, kind == HCInfectedDoorPolicy.KIND_HEAVY);
        if (result == HCFortifyBridge.BREACH_REFUSED) { return; }
        entry.m_LastHot = m_Clock;
        HCWarnPressure(entry, kind, doorPos);
        if (result != HCFortifyBridge.BREACH_NONE) { Noise(chosen, doorPos); }
    }

    // <=4 visited doors/tick, <=32 roster entries per cue, one RPC per nearby
    // identity (never broadcast). No new native query or retained player list.
    // Native gameplay.c:104-117 ScriptRPC.Write/Send; DayZGame.Event_OnRPC
    // is registered by the 5_Mission receiver. Unreliable: no stale cue backlog.
    protected void HCWarnPressure(HCInfectedDoorPressure entry, int kind, vector doorPos)
    {
        if (m_Clock < entry.m_NextCueAt) { return; }
        entry.m_NextCueAt = m_Clock + HCInfectedDoorPolicy.CUE_INTERVAL;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(HCInfectedDoorPolicy.CUE_VERSION);
        rpc.Write(doorPos);
        rpc.Write(entry.HCCueLevel(kind));
        array<Man> players = HCPerfPlayers.HCGet();
        int count = Math.Min(players.Count(), HCInfectedDoorPolicy.MAX_PLAYERS);
        for (int playerIndex = 0; playerIndex < count; playerIndex++)
        {
            PlayerBase recipient = PlayerBase.Cast(players[playerIndex]);
            if (!recipient || !recipient.IsAlive()) { continue; }
            PlayerIdentity identity = recipient.GetIdentity();
            if (!identity || vector.DistanceSq(recipient.GetPosition(), doorPos) > HCInfectedDoorPolicy.CUE_RADIUS_SQ) { continue; }
            rpc.Send(null, HCInfectedDoorPolicy.RPC_PRESSURE_CUE, false, identity);
        }
    }

    protected void Apply(HCInfectedDoorPressure entry, int action, ZombieBase chosen, vector doorPos)
    {
        Building building = entry.m_Building;
        int doorIndex = entry.m_Index;
        if (action == HCInfectedDoorPolicy.ACTION_HIT)
        {
            building.PlayDoorSound(doorIndex);
            Noise(chosen, doorPos);
            m_Hits = m_Hits + 1;
            return;
        }
        DoorManipulationParams request = new DoorManipulationParams;
        request.m_DoorIndex = doorIndex;
        request.m_Caller = chosen;
        // Vanilla semantics: true = must be unlocked; false = must be locked.
        request.m_CheckIfLocked = action != HCInfectedDoorPolicy.ACTION_BREAK;
        // Respect the building's own (possibly modded) opening rules.
        if (!building.CanDoorBeOpened(request))
        {
            m_Refused = m_Refused + 1;
            m_LastRefusal = "building_rules_refused";
            return;
        }
        string verb = "opened";
        if (action == HCInfectedDoorPolicy.ACTION_BREAK)
        {
            building.UnlockDoor(doorIndex, false);
            verb = "broke-lock";
            m_Broken = m_Broken + 1;
        }
        else
        {
            m_Opened = m_Opened + 1;
        }
        building.PlayDoorSound(doorIndex);
        building.OpenDoor(doorIndex);
        HCModuleReadiness.HCUse("InfectedDoors", "door_action");
        Noise(chosen, doorPos);
        string kindName = "common";
        if (HCInfectedDoorPolicy.Kind(true, false, chosen.IsZombieMilitary(), chosen.GetType()) == HCInfectedDoorPolicy.KIND_HEAVY) { kindName = "heavy"; }
        // At most once per door per COOLDOWN seconds.
        Print("[HC Doors] " + verb + " kind=" + kindName + " infected=" + chosen.GetType() + " building=" + building.GetType() + " door=" + doorIndex.ToString());
    }

    protected void Noise(ZombieBase source, vector position)
    {
        if (m_NoiseThisTick >= HCInfectedDoorPolicy.MAX_NOISE_PER_TICK) { return; }
        m_NoiseThisTick = m_NoiseThisTick + 1;
        HCSearchNoise.EmitAt(source, position);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInfectedDoorsModule);
    }
}
