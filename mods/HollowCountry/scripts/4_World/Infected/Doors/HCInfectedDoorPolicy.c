// #136 infected door pressure: scalar policy and per-door state only.
// No engine calls here except Math (1_Core/proto/EnMath.c:553 Min) and
// string IndexOf (1_Core/proto/EnString.c:240). Native mind-state values are
// the enum at 3_Game/Entities/DayZInfected.c:13-18; military flag is
// EntityAI.IsZombieMilitary (3_Game/Entities/EntityAI.c:744), overridden true
// for soldier/patrol/NBC grey+white classes in 4_World/Entities/Creatures/
// Infected/ZombieMaleBase.c. Crawling is ZombieBase.IsCrawling (ZombieBase.c:1090).
// Behaviour parameters use HCInfectedConfig.Doors; defaults remain provisional.
//
// Variant mapping:
//  - weak (KIND_NONE): crawlers and dead infected; never pressure a door.
//  - common (KIND_COMMON): every other infected; opens an UNLOCKED door after
//    a per-door rolled 6..10 s of sustained pressure. Cannot defeat a lock.
//  - heavy (KIND_HEAVY): IsZombieMilitary() plus firefighters, heavy
//    industry/construction/offshore/oil-rig workers and special-forces
//    policemen (vanilla class prefixes below); 4..6 rolled hits paced at
//    HIT_INTERVAL (about 6..10 s at the 1 s core tick); final hit opens an
//    unlocked door or breaks a lockpick-class lock (UnlockDoor then OpenDoor).
//    Non-lockpick locks (shipping containers, script-only/code locks) refuse.
class HCInfectedDoorPolicy
{
    static const int KIND_NONE = 0;
    static const int KIND_COMMON = 1;
    static const int KIND_HEAVY = 2;

    static const int ACTION_NONE = 0;
    static const int ACTION_HIT = 1;
    static const int ACTION_OPEN = 2;
    static const int ACTION_BREAK = 3;

    // lockState passed to HCAdvance: 0 unlocked, 1 lockpick-class (breakable),
    // 2 any other lock (never defeated).
    static const int LOCK_NONE = 0;
    static const int LOCK_BREAKABLE = 1;
    static const int LOCK_PROTECTED = 2;

    // Common: rolled seconds of sustained pressure before opening.
    // Heavy: rolled hit count, minimum seconds between hits.
    // Pressure is "sustained": a gap longer than GRACE seconds resets it, and
    // one visit never adds more than MAX_STEP seconds.
    // Seconds a door is left alone after an infected opened/broke it.
    // Seconds a door stays watched after a player was last seen near it.

    // Geometry (metres).

    // Bounds.
    static const int MAX_DOORS = 64;
    static const int MAX_PLAYERS = 32;
    static const int PLAYERS_PER_TICK = 2;
    static const int DOORS_PER_TICK = 4;
    static const int MAX_BUILDINGS_PER_PLAYER = 4;
    static const int MAX_DOORS_PER_PLAYER = 6;
    // HC-8 (#121/#151): this is a scan slice, never a building-size cutoff.
    static const int DOOR_INDICES_PER_BUILDING = 8;
    static const int MAX_DOOR_INDICES_PER_TICK = 64;
    static const int MAX_BUILDING_CURSORS = 64;
    static const int MAX_LOCK_SLOTS = 8;
    static const int MAX_OBJECTS_PER_QUERY = 128;
    static const int MAX_INFECTED_PER_DOOR = 8;
    static const int MAX_NOISE_PER_TICK = 1;

    static bool HeavyClass(string className)
    {
        if (className.IndexOf("ZmbM_FirefighterNormal") == 0) { return true; }
        if (className.IndexOf("ZmbM_HeavyIndustryWorker") == 0) { return true; }
        if (className.IndexOf("ZmbM_ConstrWorkerNormal") == 0) { return true; }
        if (className.IndexOf("ZmbM_PolicemanSpecForce") == 0) { return true; }
        if (className.IndexOf("ZmbM_OffshoreWorker") == 0) { return true; }
        if (className.IndexOf("ZmbM_takiOilRigWorker") == 0) { return true; }
        return false;
    }

    static int Kind(bool alive, bool crawling, bool military, string className)
    {
        if (!alive || crawling) { return HCInfectedDoorPolicy.KIND_NONE; }
        if (military || HeavyClass(className)) { return HCInfectedDoorPolicy.KIND_HEAVY; }
        return HCInfectedDoorPolicy.KIND_COMMON;
    }

    // Already engaged infected only; calm or merely disturbed ones never count.
    static bool Pursuing(int mind)
    {
        if (mind == DayZInfectedConstants.MINDSTATE_ALERTED) { return true; }
        if (mind == DayZInfectedConstants.MINDSTATE_CHASE) { return true; }
        return mind == DayZInfectedConstants.MINDSTATE_FIGHT;
    }

    // distanceSq: player to door; facing: horizontal dot of (player - door)
    // and (infected - door). Negative means opposite sides of the door point.
    static bool PlayerQualifies(float distanceSq, float facing)
    {
        float watchSq = HCInfectedTuning.Get().Doors.WatchRadius * HCInfectedTuning.Get().Doors.WatchRadius;
        if (!(distanceSq <= watchSq)) { return false; }
        float nearSq = HCInfectedTuning.Get().Doors.NearRadius * HCInfectedTuning.Get().Doors.NearRadius;
        if (distanceSq <= nearSq) { return true; }
        return facing < 0;
    }

    static bool Expired(float now, float watchUntil, float cooldownUntil)
    {
        return now > watchUntil && now >= cooldownUntil;
    }
}

// Retained index for a nearby building, separate from per-door pressure and
// cooldown. Only MAX_BUILDING_CURSORS rows; expires after WATCH_SECONDS away.
// A large building is revisited in slices until every native index is checked.
class HCInfectedDoorScan
{
    Building m_Building;
    int m_NextIndex;
    float m_WatchUntil;
}

// One watched closed door. Raw entity references become null when deleted.
// No persistence; the table holding these is capped at MAX_DOORS.
class HCInfectedDoorPressure
{
    Building m_Building;
    int m_Index;
    Man m_Player;
    float m_WatchUntil;
    float m_LastHot = -1000;
    float m_Pressure;
    int m_Hits;
    float m_NextHit;
    int m_OpenNeeded = 8;
    int m_HitsNeeded = 5;
    float m_CooldownUntil;
    float m_VisitedAt = -1;

    // kind: strongest qualifying infected at the door this visit (KIND_NONE
    // when none). Returns one ACTION_*; the caller performs native calls.
    int HCAdvance(int kind, int lockState, float now)
    {
        if (now < m_CooldownUntil) { return HCInfectedDoorPolicy.ACTION_NONE; }
        float step = now - m_LastHot;
        if (step > HCInfectedTuning.Get().Doors.Grace)
        {
            m_Pressure = 0;
            m_Hits = 0;
            m_NextHit = now;
            step = 0;
        }
        if (kind == HCInfectedDoorPolicy.KIND_NONE) { return HCInfectedDoorPolicy.ACTION_NONE; }
        // Refused locks cannot refresh the hot-priority timestamp forever and
        // starve other watched doors (HC-8). Claims do not alter lockState.
        if (lockState == HCInfectedDoorPolicy.LOCK_PROTECTED) { return HCInfectedDoorPolicy.ACTION_NONE; }
        if (kind == HCInfectedDoorPolicy.KIND_COMMON && lockState != HCInfectedDoorPolicy.LOCK_NONE) { return HCInfectedDoorPolicy.ACTION_NONE; }
        m_LastHot = now;
        m_Pressure = m_Pressure + Math.Min(step, HCInfectedTuning.Get().Doors.MaxStep);
        if (kind == HCInfectedDoorPolicy.KIND_COMMON)
        {
            if (m_Pressure < m_OpenNeeded) { return HCInfectedDoorPolicy.ACTION_NONE; }
            m_CooldownUntil = now + HCInfectedTuning.Get().Doors.Cooldown;
            m_Pressure = 0;
            return HCInfectedDoorPolicy.ACTION_OPEN;
        }
        if (now < m_NextHit) { return HCInfectedDoorPolicy.ACTION_NONE; }
        m_Hits = m_Hits + 1;
        m_NextHit = now + HCInfectedTuning.Get().Doors.HitInterval;
        if (m_Hits < m_HitsNeeded) { return HCInfectedDoorPolicy.ACTION_HIT; }
        m_CooldownUntil = now + HCInfectedTuning.Get().Doors.Cooldown;
        m_Hits = 0;
        m_Pressure = 0;
        if (lockState == HCInfectedDoorPolicy.LOCK_BREAKABLE) { return HCInfectedDoorPolicy.ACTION_BREAK; }
        return HCInfectedDoorPolicy.ACTION_OPEN;
    }
}
