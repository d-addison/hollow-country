// Haven census (wh-nav-a, 2026-11-22). Observation only: when an infected that already targets a
// player gives up on an elevated target, one aggregated row records WHAT the player stands on, so the
// owner's "elevation is always safe" report becomes a class table instead of a guess. Nothing here
// moves, steers, targets or damages anything; the infected's own native state is never touched.
//
// A give-up is: the Reach back-off starting, a pack member's first stuck strike, or the Reach probe
// declining an engaged infected that sits just outside the admission window (admit_far).
// Per event (budgeted at 8 per tick through HCWorkBudget, one event per player per 5 s): one downward
// ray under the player's feet (floor class) and one navmesh sample at the player's height (mesh=on
// when the outdoor walk filter has a poly there, mesh=off when it does not).
// Lines (formats are fixed):
//   [HC Nav] haven class=<cls> dy=<m> mesh=<on|off> n=<count>   first sighting of a class (2 s apart),
//        then the top-12 table at most every 600 s and only when a count changed.
//   [HC Use] module=NavInf feature=haven_seen count=<n>
// Bounds: 64 class rows plus one "other" row (a full map counts under other), 8 weak player slots,
// 4 listeners. Runtime only, never persisted, so there is no stored format to migrate.
//
// OnGiveUp is also the public hook for later systems (a siege module): HCSubscribe a listener and it
// receives every give-up (infected, native target, anchor, reason) without the Reach or Navigation
// files changing. With no subscriber the notify loop is empty.
// Native evidence, installed scripts-1.30.164289: 3_Game/Global/DayZPhysics.c:199 RaycastRV;
// 3_Game/constants.c:35 ObjIntersectGeom; 3_Game/AI/AIWorld.c:122 SampleNavmeshPosition;
// 3_Game/Entities/DayZInfected.c:107 GetInputController; DayZInfectedInputController.c:10
// GetTargetEntity; Object.c:287 GetPosition, :467 GetType, :517 IsAlive; human.c:1528
// GetCommand_Vehicle; EnScript.c array/set Count/Get/Insert/Find/RemoveOrdered; EnMath.c Round,
// AbsFloat; Game.c:914 GetTickTime, :1120 IsServer; 1_Core/proto/EnDebug.c:96 Print.
// Managed: s_Listeners holds weak handles; a subscriber freed without
// HCUnsubscribe (e.g. a second OnStart) auto-nulls and is pruned in OnGiveUp.
class HCNavGiveUpListener : Managed
{
    void OnGiveUp(DayZInfected infected, EntityAI target, vector anchor, string reason) {}
}

class HCNavHavenRow
{
    string Cls;
    int Count;
    int Printed;
    int DyTenths;
    bool MeshOn;
}

class HCNavHavenCensus
{
    static const int CAPACITY = 64;   // classes; the "other" row is the 65th
    static const int TABLE_ROWS = 12;
    static const int EVENTS_PER_TICK = 8;
    static const int MAX_LISTENERS = 4;
    static const int TARGET_SLOTS = 8;
    static const float TABLE_SECONDS = 600;
    static const float TARGET_SECONDS = 5;
    static const float FIRST_LINE_GAP_SECONDS = 2;
    static const float MESH_SAMPLE_METRES = 1.5;
    static const float MESH_HEIGHT_TOLERANCE_METRES = 0.7;
    static const string CLASS_TERRAIN = "terrain";
    static const string CLASS_OTHER = "other";

    protected static ref array<ref HCNavHavenRow> s_Rows = new array<ref HCNavHavenRow>;
    protected static ref array<HCNavGiveUpListener> s_Listeners = new array<HCNavGiveUpListener>;
    protected static ref array<Object> s_Targets = new array<Object>;
    protected static ref array<float> s_TargetUntil = new array<float>;
    protected static ref set<Object> s_Hits = new set<Object>;
    protected static ref HCWorkBudget s_Budget;
    protected static float s_BudgetAt = -1;
    protected static float s_NextTable;
    protected static float s_LastFirstLine = -100;
    protected static int s_TargetNext;

    // Later systems subscribe once; at most MAX_LISTENERS, duplicates ignored. Returns false when refused.
    static bool HCSubscribe(HCNavGiveUpListener listener)
    {
        if (!listener) { return false; }
        if (s_Listeners.Find(listener) >= 0) { return true; }
        if (s_Listeners.Count() >= MAX_LISTENERS) { return false; }
        s_Listeners.Insert(listener);
        return true;
    }

    static void HCUnsubscribe(HCNavGiveUpListener listener)
    {
        int index = s_Listeners.Find(listener);
        if (index >= 0) { s_Listeners.RemoveOrdered(index); }
    }

    // The infected's own retained native target (never chosen or changed here); null without one.
    static EntityAI HCNativeTarget(DayZInfected infected)
    {
        if (!infected) { return null; }
        DayZInfectedInputController controller = infected.GetInputController();
        if (!controller) { return null; }
        return controller.GetTargetEntity();
    }

    // Public hook. `target` may be null (a pack member stuck on a clue route has no player): the census
    // then records nothing and subscribers still hear the event. `anchor` is where the infected wanted
    // to go (the player's position, or the pack route end).
    static void OnGiveUp(DayZInfected infected, EntityAI target, vector anchor, string reason)
    {
        if (!infected || !GetGame() || !GetGame().IsServer()) { return; }
        HCRecord(infected, target);
        for (int index = s_Listeners.Count() - 1; index >= 0; index--)
        {
            HCNavGiveUpListener listener = s_Listeners[index];
            if (!listener)
            {
                s_Listeners.RemoveOrdered(index);
                continue;
            }
            listener.OnGiveUp(infected, target, anchor, reason);
        }
    }

    protected static void HCRecord(DayZInfected infected, EntityAI target)
    {
        PlayerBase player = PlayerBase.Cast(target);
        if (!player || !player.IsAlive() || player.GetCommand_Vehicle()) { return; }
        float now = GetGame().GetTickTime();
        vector aim = player.GetPosition();
        float dy = aim[1] - infected.GetPosition()[1];
        if (dy < HCInfectedTuning.Get().Reach.ElevatedMin) { return; }
        if (!HCTargetDue(player, now)) { return; }
        if (!HCTakeEvent(now)) { return; }
        HCTargetMark(player, now);
        string cls = HCFloorClass(player);
        bool mesh = HCMeshAt(aim);
        int tenths = Math.Round(dy * 10);
        HCCount(cls, tenths, mesh, now);
        HCModuleReadiness.HCUseGuarded("NavInf", "haven_seen", player);
        HCFlushAt(now);
    }

    // One unit of the per-tick event budget (GetTickTime is fixed inside a tick, so a new value is a new tick).
    protected static bool HCTakeEvent(float now)
    {
        if (!s_Budget) { s_Budget = new HCWorkBudget; }
        if (now != s_BudgetAt)
        {
            s_BudgetAt = now;
            s_Budget.HCReset(EVENTS_PER_TICK, 1);
        }
        return s_Budget.HCContinue();
    }

    protected static bool HCTargetDue(Object player, float now)
    {
        int index = s_Targets.Find(player);
        if (index < 0) { return true; }
        return now >= s_TargetUntil[index];
    }

    protected static void HCTargetMark(Object player, float now)
    {
        int index = s_Targets.Find(player);
        if (index >= 0)
        {
            s_TargetUntil.Set(index, now + TARGET_SECONDS);
            return;
        }
        if (s_Targets.Count() < TARGET_SLOTS)
        {
            s_Targets.Insert(player);
            s_TargetUntil.Insert(now + TARGET_SECONDS);
            return;
        }
        s_Targets.Set(s_TargetNext, player);
        s_TargetUntil.Set(s_TargetNext, now + TARGET_SECONDS);
        s_TargetNext = (s_TargetNext + 1) % TARGET_SLOTS;
    }

    // One ray from just above the player's feet down to 1.2 m below them against collision geometry.
    // No hit, terrain only, or a creature/item is reported by a fixed token; anything else by its type.
    protected static string HCFloorClass(PlayerBase player)
    {
        vector origin = player.GetPosition() + "0 0.3 0";
        vector finish = player.GetPosition() + "0 -1.2 0";
        vector contact;
        vector normal;
        int component;
        s_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, s_Hits, null, player, true, false, ObjIntersectGeom);
        if (!hit || s_Hits.Count() == 0) { return CLASS_TERRAIN; }
        Object surface = s_Hits.Get(0);
        if (!surface) { return CLASS_TERRAIN; }
        if (DayZCreature.Cast(surface) || Man.Cast(surface)) { return "creature"; }
        if (ItemBase.Cast(surface)) { return "item"; }
        string typeName = surface.GetType();
        if (typeName == "") { return "unnamed"; }
        if (typeName.Length() > 64) { typeName = typeName.Substring(0, 64); }
        return typeName;
    }

    // mesh=on: the outdoor walk filter has a poly within 1.5 m at the player's height. A refused
    // sample (or no AI world) is mesh=off.
    protected static bool HCMeshAt(vector position)
    {
        if (!GetGame().GetWorld() || !GetGame().GetWorld().GetAIWorld()) { return false; }
        vector sampled;
        if (!GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(position, MESH_SAMPLE_METRES, HCNavFilters.HCFor(HCNavFilters.PROFILE_OUTDOOR), sampled)) { return false; }
        return Math.AbsFloat(sampled[1] - position[1]) <= MESH_HEIGHT_TOLERANCE_METRES;
    }

    protected static int HCIndexOf(string cls)
    {
        for (int index = 0; index < s_Rows.Count(); index++)
        {
            if (s_Rows[index].Cls == cls) { return index; }
        }
        return -1;
    }

    // Rows stay ordered by count (highest first): the changed row moves up past smaller counts, so the
    // table is the first rows and needs no scan.
    protected static void HCRaise(int start)
    {
        int at = start;
        while (at > 0 && s_Rows[at - 1].Count < s_Rows[at].Count)
        {
            ref HCNavHavenRow above = s_Rows[at - 1];
            s_Rows.Set(at - 1, s_Rows[at]);
            s_Rows.Set(at, above);
            at--;
        }
    }

    protected static void HCCount(string cls, int tenths, bool mesh, float now)
    {
        int slot = HCIndexOf(cls);
        bool created = false;
        if (slot < 0)
        {
            // A full class map counts under "other" (a single extra row).
            if (s_Rows.Count() >= CAPACITY) { slot = HCIndexOf(CLASS_OTHER); }
            if (slot < 0)
            {
                HCNavHavenRow fresh = new HCNavHavenRow;
                fresh.Cls = cls;
                if (s_Rows.Count() >= CAPACITY) { fresh.Cls = CLASS_OTHER; }
                s_Rows.Insert(fresh);
                slot = s_Rows.Count() - 1;
                created = true;
            }
        }
        HCNavHavenRow row = s_Rows[slot];
        if (row.Count < 2147483647) { row.Count = row.Count + 1; }
        row.DyTenths = tenths;
        row.MeshOn = mesh;
        HCRaise(slot);
        if (s_NextTable <= 0) { s_NextTable = now + TABLE_SECONDS; }
        if (created && now - s_LastFirstLine >= FIRST_LINE_GAP_SECONDS)
        {
            s_LastFirstLine = now;
            HCPrintRow(row);
        }
    }

    protected static string HCTenths(int tenths)
    {
        string sign = "";
        int magnitude = tenths;
        if (magnitude < 0)
        {
            sign = "-";
            magnitude = -magnitude;
        }
        int whole = magnitude / 10;
        int fraction = magnitude - whole * 10;
        return sign + whole.ToString() + "." + fraction.ToString();
    }

    protected static void HCPrintRow(HCNavHavenRow row)
    {
        string mesh = "off";
        if (row.MeshOn) { mesh = "on"; }
        row.Printed = row.Count;
        Print("[HC Nav] haven class=" + row.Cls + " dy=" + HCTenths(row.DyTenths) + " mesh=" + mesh + " n=" + row.Count.ToString());
    }

    protected static bool HCChanged()
    {
        for (int index = 0; index < s_Rows.Count(); index++)
        {
            if (s_Rows[index].Count != s_Rows[index].Printed) { return true; }
        }
        return false;
    }

    // Time-gated table: at most one every 600 s, only when a count changed since it last printed.
    static void HCFlush()
    {
        if (!GetGame()) { return; }
        HCFlushAt(GetGame().GetTickTime());
    }

    protected static void HCFlushAt(float now)
    {
        if (s_NextTable <= 0 || now < s_NextTable) { return; }
        s_NextTable = now + TABLE_SECONDS;
        if (!HCChanged()) { return; }
        int shown = s_Rows.Count();
        if (shown > TABLE_ROWS) { shown = TABLE_ROWS; }
        for (int line = 0; line < shown; line++)
        {
            HCPrintRow(s_Rows[line]);
        }
        // Rows below the top 12 are not printed; mark them seen so only a later count change re-arms the table.
        for (int seen = shown; seen < s_Rows.Count(); seen++)
        {
            s_Rows[seen].Printed = s_Rows[seen].Count;
        }
    }
}

// The use summary already runs on a timer; ride it for the table so no extra schedule exists.
modded class HCModuleReadiness
{
    override static void HCSummary()
    {
        super.HCSummary();
        HCNavHavenCensus.HCFlush();
    }
}
