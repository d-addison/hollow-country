// Native: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D; EntityAI.c:882/885 hierarchy.
// Native: 3_Game/Entities/Object.c:215/287/467/517/1219 deletion/pose/type/life/ruin.
// Query is local, never GetPlayers/world traversal. The native API allocates its
// result before our 128-entry refusal; this is not an engine-side query cap.
// No create/move/delete/CE replenishment call is used by this adapter; the reward
// cache is created by HCEventCacheSpawner (4_World/Events/HCEventRewardCache.c).
class HCEventWorldBinding
{
    // Bind diagnostics: why the last Select/Query refused, and the bounded set of
    // (mission, reason) pairs already logged, so a retrying roster never spams.
    protected static string s_FailReason;
    protected static ref array<string> s_BindReported;
    static void BindSites(HCEventNativeObserver observer, HCEventSettings settings, string world)
    {
        if (!observer || !settings || !HCEventRuntimePolicy.SettingsValid(settings)) { return; }
        string current = world;
        current.ToLower();
        foreach (HCEventSite site : settings.Sites)
        {
            string siteWorld = site.WorldName;
            siteWorld.ToLower();
            if (siteWorld == current)
            {
                array<ref HCEventMission> roster = HCEventRoster.Build(site, false);
                foreach (HCEventMission mission : roster) { Bind(observer, mission); }
            }
        }
    }
    static array<Object> Query(vector anchor, float radius)
    {
        if (!HCEventQualification.Admitted() || !GetGame() || !GetGame().IsServer() || radius != radius || radius < 1 || radius > 30 || !HCEventRuntimePolicy.PositionValid(anchor)) { return null; }
        array<Object> objects = new array<Object>();
        array<CargoBase> proxies = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(anchor, radius, objects, proxies);
        if (objects.Count() > 128)
        {
            s_FailReason = "query_overflow";
            return null;
        }
        return objects;
    }
    static HCEventTarget Select(array<Object> objects, string className, bool economy)
    {
        // This DTO preserves the exact native handle; no substitute loot.
        if (!objects) { return null; }
        if (objects.Count() > 128)
        {
            s_FailReason = "query_overflow";
            return null;
        }
        HCEventTarget found;
        foreach (Object candidate : objects)
        {
            if (candidate && !candidate.IsPendingDeletion() && candidate.GetType() == className)
            {
                ItemBase item = ItemBase.Cast(candidate);
                bool eligible = !economy;
                if (economy && item)
                {
                    eligible = item.HCEventEconomyCandidate() && !item.IsRuined() && !item.GetHierarchyRootPlayer() && !item.GetHierarchyParent();
                }
                if (eligible)
                {
                    if (found)
                    {
                        s_FailReason = "ambiguous";
                        return null;
                    }
                    found = new HCEventTarget;
                    found.Presence = candidate;
                    found.Item = item;
                }
            }
        }
        if (!found) { s_FailReason = "no_candidate"; }
        return found;
    }
    // Logs once per (mission, reason), at most 64 pairs; always returns false.
    static bool BindFailed(HCEventMission mission)
    {
        string reason = s_FailReason;
        s_FailReason = "";
        if (reason == "") { return false; }
        if (!s_BindReported) { s_BindReported = new array<string>(); }
        string key = mission.Id + "|" + reason;
        if (s_BindReported.Count() >= 64 || s_BindReported.Find(key) >= 0) { return false; }
        s_BindReported.Insert(key);
        Print("[HC Events] bind failed; " + mission.Id + "; reason=" + reason);
        return false;
    }
    // Reviewed-site reward cache: created at most once per site and session by the
    // journaled spawner, then registered like any recovery target. An existing
    // registration is kept untouched, so a lease, carrier or player drop is never reset.
    static bool BindCache(HCEventNativeObserver observer, HCEventMission mission)
    {
        if (mission.Family != HCEventFamily.RECOVERY || !HCEventSitesGate.Admitted()) { return false; }
        if (observer.Target(mission.Id)) { return true; }
        HCEventTarget created = HCEventCacheSpawner.Create(mission);
        if (!created) { return false; }
        if (!observer.RegisterTarget(mission.Id, created.Item))
        {
            HCEventCacheSpawner.Discard(created.Item);
            return false;
        }
        return true;
    }
    // Stable native references survive retries, pickup/drop and existing leases.
    // Shared barrel cargo is never discarded or replenished after registration failure.
    static bool BindPolice(HCEventNativeObserver observer, HCEventMission mission)
    {
        if (!HCEventSitesGate.Admitted()) { return false; }
        HCEventTarget current = observer.Target(mission.Id);
        if (current)
        {
            if (mission.Family == HCEventFamily.DELIVERY && !current.DeliveryContainer)
            {
                HCEventTarget pending = HCEventCacheSpawner.PoliceTarget(mission.Id);
                return pending && observer.RegisterContainer(mission.Id, pending.DeliveryContainer);
            }
            return true;
        }
        HCEventTarget supply = HCEventCacheSpawner.CreatePolice(mission);
        if (!supply)
        {
            s_FailReason = "police_supply_unavailable";
            return BindFailed(mission);
        }
        if (!observer.RegisterTarget(mission.Id, supply.Item)) { return false; }
        if (mission.Family == HCEventFamily.DELIVERY && !observer.RegisterContainer(mission.Id, supply.DeliveryContainer)) { return false; }
        Print("[HC Events] police supply bound; " + mission.Id);
        return true;
    }
    static bool Bind(HCEventNativeObserver observer, HCEventMission mission)
    {
        if (!observer || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName) || !HCEventQualification.Admitted()) { return false; }
        if (mission.Family == HCEventFamily.INVESTIGATION) { return true; }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER) { return false; }
        if (mission.RewardCache) { return BindCache(observer, mission); }
        if (HCEventSites.PoliceSupplies(mission)) { return BindPolice(observer, mission); }
        if (!observer.ResetUnleasedTarget(mission.Id)) { return true; }
        s_FailReason = "";
        array<Object> nearby = Query(mission.Source, 15);
        if (!nearby) { return BindFailed(mission); }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            // Native: EnConvert.c:210 DistanceSq; EnEntity.c:518 unique GetID.
            // Query order is unspecified: nearest first, native entity id breaks ties.
            ZombieBase selected;
            float nearest = 0;
            foreach (Object candidate : nearby)
            {
                ZombieBase infected = ZombieBase.Cast(candidate);
                if (infected && infected.HCEventEconomyCandidate() && infected.IsAlive() && !infected.IsPendingDeletion())
                {
                    float distance = vector.DistanceSq(infected.GetPosition(), mission.Source);
                    if (!selected || distance < nearest || (distance == nearest && infected.GetID() < selected.GetID()))
                    {
                        selected = infected;
                        nearest = distance;
                    }
                }
            }
            if (!selected)
            {
                s_FailReason = "no_candidate";
                return BindFailed(mission);
            }
            return observer.RegisterInfected(mission.Id, selected);
        }
        string wanted = mission.ItemClass;
        bool economy = true;
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            wanted = mission.AnchorClass;
            economy = false;
        }
        HCEventTarget target = Select(nearby, wanted, economy);
        if (!target) { return BindFailed(mission); }
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            return observer.RegisterPresence(mission.Id, target.Presence);
        }
        HCEventTarget destination;
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            destination = Select(Query(mission.Destination, 15), mission.ContainerClass, true);
            if (!destination || destination.Item == target.Item) { return BindFailed(mission); }
        }
        if (!observer.RegisterTarget(mission.Id, target.Item)) { return false; }
        if (destination) { return observer.RegisterContainer(mission.Id, destination.Item); }
        return true;
    }
}
