// Native: 3_Game/Global/Game.c:703 CreateObjectEx, :705 ObjectDelete, :1120 IsServer,
// :1176 SurfaceY; 3_Game/CE/CentralEconomy.c:30 ECE_NOLIFETIME, :31 ECE_NOPERSISTENCY_WORLD,
// :38 ECE_PLACE_ON_SURFACE; 3_Game/Systems/Inventory/Inventory.c:143 CreateEntityInCargo;
// 4_World/Entities/ItemBase/Gear/Containers/containers.c SmallProtectorCase : Container_Base.
// Server-created once per site and session, AFTER the grant is journaled by HCEventRewardLedger.
// ECE_NOPERSISTENCY_WORLD (3_Game/CE/CentralEconomy.c:31 "do not save this object in world") only
// means the case container is not saved in the world. It does not cover character persistence
// (ECE_NOPERSISTENCY_CHAR, :32, deliberately not set: a case a player holds is theirs). Items a
// player takes are ordinary loot and may persist on a character across a restart while the new
// boot replenishes its per-session allowance; that overlap is accepted and bounded by the cap.
// The case keeps ECE_NOLIFETIME and is never deleted by this module once registered, so loot
// a player has dropped is never destroyed. Case cargo capacity is UNOBSERVED: a partial fill is
// kept and logged, an empty case is deleted. Local acceptance of creation is PENDING.
class HCEventCacheSpawner
{
    static HCEventTarget Create(HCEventMission mission)
    {
        if (!mission || !mission.RewardCache || mission.Family != HCEventFamily.RECOVERY) { return null; }
        if (!HCEventSitesGate.Admitted() || !GetGame() || !GetGame().IsServer()) { return null; }
        if (!HCEventRuntimePolicy.MissionValid(mission, mission.WorldName)) { return null; }
        // Ready/observation use a 3D radius around Source; refuse before any journal write
        // when the terrain here is too far from the reviewed height to stay observable.
        float height = GetGame().SurfaceY(mission.Source[0], mission.Source[2]);
        if (height != height || Math.AbsFloat(height - mission.Source[1]) > 6)
        {
            Print("[HC Events] reward cache refused for site " + mission.SiteId + "; terrain height differs from the reviewed height");
            return null;
        }
        HCEventRewardPlan plan = HCEventRewards.Ledger().Commit(mission.SiteId);
        if (!plan) { return null; }
        vector position = Vector(mission.Source[0], height, mission.Source[2]);
        int flags = ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;
        Object created = GetGame().CreateObjectEx(mission.ItemClass, position, flags);
        ItemBase cache = ItemBase.Cast(created);
        if (!cache)
        {
            if (created) { GetGame().ObjectDelete(created); }
            Print("[HC Events] reward cache creation failed; grant stays spent for this session");
            return null;
        }
        int made = 0;
        foreach (string className : plan.Items)
        {
            if (cache.GetInventory() && cache.GetInventory().CreateEntityInCargo(className))
            {
                made = made + 1;
            }
        }
        int wanted = plan.Items.Count();
        if (made < 1)
        {
            GetGame().ObjectDelete(cache);
            Print("[HC Events] reward cache held no content; removed, grant stays spent for this session");
            return null;
        }
        Print("[HC Events] reward cache created site " + mission.SiteId + " items " + made.ToString() + "/" + wanted.ToString());
        HCEventTarget result = new HCEventTarget;
        result.MissionId = mission.Id;
        result.Item = cache;
        result.Presence = cache;
        return result;
    }
    // Only for a cache that could not be registered; never for one a player may hold.
    static void Discard(ItemBase cache)
    {
        if (cache && !cache.IsPendingDeletion() && !cache.GetHierarchyRootPlayer() && !cache.GetHierarchyParent())
        {
            GetGame().ObjectDelete(cache);
        }
    }
}
