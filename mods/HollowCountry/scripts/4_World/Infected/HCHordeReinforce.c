// #246 source contract: target 30..40, 4 x 40 = 160 tracked by default.
// Cost: one round-robin pack sweep charges its reserved members (<=MAX_PACK)
// through HCServer.HCTickWork, plus <=2 native creates globally per tick.
// Hidden checks: <=8 observers x 3 samples x 2 geometries per attempt;
// <=2 cleanup leases per tick. HCPerfConfig.SliceMs is cooperative, not a
// measured native-call deadline. 160 members x actor sampling/pack work must
// still be benchmarked with the intended 3-6 players; 12/256 are hard ceilings.
//
// Installed scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:691 CreateObject (init_ai), :703 CreateObjectEx,
// :705 ObjectDelete, :1176 SurfaceY; CE/CentralEconomy.c:18 ECE_INITAI,
// :38 ECE_PLACE_ON_SURFACE, :32 ECE_NOPERSISTENCY_WORLD (no world save).
// No ECE_EQUIP flags, inventory writes, or class substitutions. Native class
// initialization alone decides its starting equipment.
// Object.c:287 GetPosition, :467 GetType; Global/DayZPhysics.c:199 RaycastRV.
// HCInfectedLOD.Occluded reuses the existing view/fire geometry helper with
// the shared HCPerfPlayers sample. Unknown eyes, parents or sight veto creation.
//
// Only memory leases (entity handles, no persisted IDs) authorize deletion.
// Crash/restart: no scripted cleanup receipt is claimed. ECE_NOPERSISTENCY_WORLD
// requests no restoration from world persistence; on an in-process script reload
// a surviving body is ordinary CE-less population until native cleanup, which
// is NOT established by the script declarations. Never recover/delete it by type
// or position. Supplemented journals deliberately have no recovery identity list
// and remain unresolved after restart. DayZDiag/PBO + two-client acceptance pending.
class HCHordeLimits
{
    static const int MAX_PACK = 40;
    static const int MIN_PATROL = 8;
}

class HCHordeSpawnLease
{
    ZombieBase Body;
    ref HCNativeInfectedPack Pack;
}

class HCHordeReinforce
{
    protected static ref array<ref HCHordeSpawnLease> s_Leases = new array<ref HCHordeSpawnLease>;
    protected static ref HCWorkBudget s_SpawnWork = new HCWorkBudget;
    protected static ref HCWorkBudget s_CleanupWork = new HCWorkBudget;
    protected static int s_Cursor;

    static bool HCHidden(vector point, Object body)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() > 8 || !HCInfectedStore.ValidPosition(point)) { return false; }
        float nearest = HCInfectedLOD.NearestDistance(players, point);
        if (nearest < 300) { return false; }
        HCLODSightBudget sight = new HCLODSightBudget;
        sight.HCReset(8 * HCInfectedLOD.RAYS_PER_OBSERVER);
        // Every player, including dead observers; no visibility-range shortcut.
        foreach (Man player : players)
        {
            if (!player || !HCInfectedStore.ValidPosition(player.GetPosition())) { return false; }
            if (!HCInfectedLOD.Occluded(player, point, body, sight)) { return false; }
        }
        return true;
    }

    static ZombieBase HCCreate(string type, vector entry, HCNativeInfectedPack pack)
    {
        if (!GetGame().IsServer() || !pack || s_Leases.Count() >= 256 || !s_SpawnWork.HCContinue()) { return null; }
        entry[1] = GetGame().SurfaceY(entry[0], entry[2]);
        if (!HCHordeReinforce.HCHidden(entry, null)) { return null; }
        Object created = GetGame().CreateObjectEx(type, entry, ECE_INITAI | ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD);
        ZombieBase body = ZombieBase.Cast(created);
        if (!body)
        {
            if (created) { GetGame().ObjectDelete(created); }
            return null;
        }
        HCHordeSpawnLease lease = new HCHordeSpawnLease;
        lease.Body = body;
        lease.Pack = pack;
        s_Leases.Insert(lease);
        return body;
    }

    static void HCBeginTick()
    {
        s_SpawnWork.HCReset(2, HCPerfConfig.HCGet().SliceMs);
        s_CleanupWork.HCReset(2, HCPerfConfig.HCGet().SliceMs);
        HCUnitBudget shared = HCServer.HCTickWork();
        // Retain leases when visibility or budget is unknown. No global actor
        // scan, CE deletion, or shutdown burst; normal ticks drain the cursor.
        int inspected = 0;
        while (s_Leases.Count() > 0 && inspected < 2 && s_CleanupWork.HCContinue() && shared.HCTakeFor(HCUnitBudget.HC_WORK_HORDE_REINFORCE, 1))
        {
            if (s_Cursor >= s_Leases.Count()) { s_Cursor = 0; }
            HCHordeSpawnLease lease = s_Leases[s_Cursor];
            inspected++;
            if (!lease.Body)
            {
                s_Leases.Remove(s_Cursor);
                continue;
            }
            if (!lease.Pack.HCReinforceActive() && HCHordeReinforce.HCHidden(lease.Body.GetPosition(), lease.Body))
            {
                GetGame().ObjectDelete(lease.Body);
                s_Leases.Remove(s_Cursor);
                continue;
            }
            s_Cursor++;
        }
    }
}
