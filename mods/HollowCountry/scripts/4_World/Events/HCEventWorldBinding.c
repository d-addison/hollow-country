// Native: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D; EntityAI.c:882/885 hierarchy.
// Native: 3_Game/Entities/Object.c:215/287/467/517/1219 deletion/pose/type/life/ruin.
// Native 1.30.164289: 1_Core/proto/EnScript.c:380/394/407 Count/Find/Insert;
// array index writes use Set (EnScript.c:389).
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:1120/1176 IsServer/SurfaceY;
// 1_Core/proto/EnString.c:171 ToLower; EnConvert.c:210 DistanceSq;
// 1_Core/proto/EnEntity.c:518 GetID. HCEventEconomyCandidate is an HC hook.
// 1_Core/proto/EnMath3D.c:18 Vector; EnDebug.c:96 Print.
// Query is local, never GetPlayers/world traversal. The native API allocates its
// result before our 128-entry refusal; this is not an engine-side query cap.
// No create/move/delete/CE replenishment call is used by this adapter; the reward
// cache is created by HCEventCacheSpawner (4_World/Events/HCEventRewardCache.c).
class HCEventWorldBinding
{
    // Bind diagnostics: the last Select/Query refusal and the last reported
    // reason per mission (at most 64), so retries log only state changes.
    protected static string s_FailReason;
    protected static ref array<string> s_BindReported;
    protected static ref array<string> s_BindReasons;
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
        // Ordinary item/presence lookups keep their existing local query cap.
        if (radius > 30) { return null; }
        return QueryBounded(anchor, radius);
    }
    static array<Object> QueryBounded(vector anchor, float radius)
    {
        if (!HCEventQualification.Admitted() || !GetGame() || !GetGame().IsServer() || radius != radius || radius < 1 || radius > 60 || !HCEventRuntimePolicy.PositionValid(anchor)) { return null; }
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
    // Logs once per reason change, retaining at most 64 mission entries.
    static bool BindFailed(HCEventMission mission)
    {
        string reason = s_FailReason;
        s_FailReason = "";
        if (reason == "") { return false; }
        if (!s_BindReported)
        {
            s_BindReported = new array<string>();
            s_BindReasons = new array<string>();
        }
        int index = s_BindReported.Find(mission.Id);
        if (index >= 0)
        {
            if (s_BindReasons[index] == reason) { return false; }
            s_BindReasons[index] = reason;
        }
        else
        {
            if (s_BindReported.Count() >= 64) { return false; }
            s_BindReported.Insert(mission.Id);
            s_BindReasons.Insert(reason);
        }
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
        bool bound = BindCandidate(observer, mission);
        if (bound && s_BindReported)
        {
            int index = s_BindReported.Find(mission.Id);
            if (index >= 0 && s_BindReasons[index] != "")
            {
                s_BindReasons[index] = "";
                Print("[HC Events] bind recovered; " + mission.Id);
            }
        }
        return bound;
    }
    static bool BindCandidate(HCEventNativeObserver observer, HCEventMission mission)
    {
        if (!observer || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName) || !HCEventQualification.Admitted()) { return false; }
        if (mission.Family == HCEventFamily.INVESTIGATION) { return true; }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER) { return false; }
        if (mission.RewardCache) { return BindCache(observer, mission); }
        if (HCEventSites.PoliceSupplies(mission)) { return BindPolice(observer, mission); }
        if (!observer.ResetUnleasedTarget(mission.Id)) { return true; }
        s_FailReason = "";
        vector origin = mission.Source;
        float radius = 15;
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            // Native: 3_Game/Global/Game.c:1176 SurfaceY(x, z). A police source is a model
            // origin standing about 7 m above its ground, so a sphere centred on it reaches
            // only about 13 m on the ground. Centre on the ground and search 60 m;
            // the 128-object overflow refusal remains authoritative.
            float groundY = GetGame().SurfaceY(mission.Source[0], mission.Source[2]);
            if (groundY != groundY)
            {
                s_FailReason = "ground_unavailable";
                return BindFailed(mission);
            }
            origin = Vector(mission.Source[0], groundY, mission.Source[2]);
            radius = 60;
        }
        array<Object> nearby = null;
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            nearby = QueryBounded(origin, radius);
        }
        else
        {
            nearby = Query(origin, radius);
        }
        if (!nearby) { return BindFailed(mission); }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            // Native: EnConvert.c:210 DistanceSq; EnEntity.c:518 unique GetID.
            // Query order is unspecified: nearest to the ground centre first, native entity id breaks ties.
            ZombieBase selected;
            float nearest = 0;
            foreach (Object candidate : nearby)
            {
                ZombieBase infected = ZombieBase.Cast(candidate);
                if (infected && infected.HCEventEconomyCandidate() && infected.IsAlive() && !infected.IsPendingDeletion())
                {
                    float distance = vector.DistanceSq(infected.GetPosition(), origin);
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
            if (!observer.RegisterInfected(mission.Id, selected))
            {
                s_FailReason = "registration_refused";
                return BindFailed(mission);
            }
            return true;
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
