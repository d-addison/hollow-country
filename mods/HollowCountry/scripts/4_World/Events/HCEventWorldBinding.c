// Native: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D; EntityAI.c:882/885 hierarchy.
// Native: 3_Game/Entities/Object.c:215/287/467/517/1219 deletion/pose/type/life/ruin.
// Native 1.30.164289: 1_Core/proto/EnScript.c:380/394/407 Count/Find/Insert;
// array index writes use Set (EnScript.c:389).
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:1120/1176 IsServer/SurfaceY;
// 1_Core/proto/EnString.c:171 ToLower; EnConvert.c:210 DistanceSq;
// 1_Core/proto/EnEntity.c:518 GetID. HCEventEconomyCandidate is an HC hook.
// 1_Core/proto/EnMath3D.c:18 Vector; EnDebug.c:96 Print.
// Query is local, never GetPlayers/world traversal. The native API allocates its
// result before our refusal; this is not an engine-side query cap. The 15 m item
// lookup keeps 128 objects; the 60 m infected scan keeps the same object density
// (128 per 15 m sphere, scaled by volume: 128 * (60/15)^3 = 8192). Release 020
// logged query_overflow for both police -7 missions because a town-centre 60 m
// sphere returns every building, tree, bush, fence and prop under the old 128 cap.
// 1_Core/proto/EnMath.c:427 Floor.
// No create/move/delete/CE replenishment call is used by this adapter; the reward
// cache is created by HCEventCacheSpawner (4_World/Events/HCEventRewardCache.c).
class HCEventWorldBinding
{
    // Bind diagnostics: the last Select/Query refusal and the last reported
    // reason per mission (at most 64), so retries log only state changes.
    protected static string s_FailReason;
    protected static string s_FailDetails;
    protected static bool s_StartupReported;
    protected static ref array<string> s_BindReported;
    protected static ref array<string> s_BindReasons;
    static void BindSites(HCEventNativeObserver observer, HCEventSettings settings, string world)
    {
        if (!observer || !settings || !HCEventRuntimePolicy.SettingsValid(settings)) { return; }
        string current = world;
        current.ToLower();
        int checked = 0;
        int unbindable = 0;
        foreach (HCEventSite site : settings.Sites)
        {
            string siteWorld = site.WorldName;
            siteWorld.ToLower();
            if (siteWorld == current)
            {
                array<ref HCEventMission> roster = HCEventRoster.Build(site, false);
                foreach (HCEventMission mission : roster)
                {
                    // Only static PRESENCE anchors can be preflighted. Infected and
                    // ordinary CE items may appear later; absence is never permanent.
                    if (!s_StartupReported && mission.Family == HCEventFamily.PRESENCE)
                    {
                        checked = checked + 1;
                        array<Object> anchors = QueryBounded(mission.Source, 60);
                        string constraint = AnchorConstraint(anchors, mission);
                        if (!anchors)
                        {
                            Print("[HC Events] startup anchor unresolved; " + mission.Id + "; constraint=" + constraint + s_FailDetails + "; probe_radius_m=60; retryable=1");
                        }
                        else
                        {
                            if (constraint != "")
                            {
                                unbindable = unbindable + 1;
                                Print("[HC Events] startup anchor unbindable; " + mission.Id + "; constraint=" + constraint + s_FailDetails + "; probe_radius_m=60; retryable=1");
                            }
                        }
                    }
                    Bind(observer, mission);
                }
            }
        }
        if (!s_StartupReported)
        {
            s_StartupReported = true;
            Print("[HC Events] startup anchors checked=" + checked.ToString() + " unbindable=" + unbindable.ToString());
        }
    }
    // Native: EnMath.c:305 Sqrt; distances cover only observed query results,
    // never a claim to know the nearest object outside our bounded local probe.
    static string CandidateDetails(string wanted, float nearestSq, float radius)
    {
        string distance = "none_within_" + radius.ToString();
        if (nearestSq >= 0)
        {
            float metres = Math.Sqrt(nearestSq);
            distance = metres.ToString();
        }
        return "; wanted=" + wanted + "; nearest_candidate_m=" + distance + "; radius_m=" + radius.ToString();
    }
    static string AnchorConstraint(array<Object> objects, HCEventMission mission)
    {
        s_FailDetails = "; wanted=" + mission.AnchorClass + "; nearest_candidate_m=unknown_query_refused; radius_m=15";
        if (!objects) { return "anchor_query_unavailable"; }
        float nearestSq = -1;
        int inside = 0;
        foreach (Object anchor : objects)
        {
            if (anchor && !anchor.IsPendingDeletion() && anchor.GetType() == mission.AnchorClass)
            {
                float distanceSq = vector.DistanceSq(anchor.GetPosition(), mission.Source);
                if (nearestSq < 0 || distanceSq < nearestSq) { nearestSq = distanceSq; }
                if (distanceSq <= 225) { inside = inside + 1; }
            }
        }
        s_FailDetails = CandidateDetails(mission.AnchorClass, nearestSq, 60) + "; bind_radius_m=15";
        if (nearestSq < 0) { return "anchor_class_absent_within_probe"; }
        if (inside == 0) { return "anchor_outside_bind_radius"; }
        if (inside > 1) { return "anchor_ambiguous"; }
        return "";
    }
    static array<Object> Query(vector anchor, float radius)
    {
        // Ordinary item/presence lookups keep their existing local query cap.
        if (radius > 30) { return null; }
        return QueryBounded(anchor, radius);
    }
    // Object cap at the 15 m lookup's density: 128 objects per 15 m sphere, by volume.
    static int ScanCap(float radius)
    {
        if (radius <= 15) { return 128; }
        float scale = radius / 15;
        int cap = Math.Floor(128 * scale * scale * scale);
        if (cap > 8192) { return 8192; }
        return cap;
    }
    static array<Object> QueryBounded(vector anchor, float radius)
    {
        if (!HCEventQualification.Admitted() || !GetGame() || !GetGame().IsServer() || radius != radius || radius < 1 || radius > 60 || !HCEventRuntimePolicy.PositionValid(anchor)) { return null; }
        array<Object> objects = new array<Object>();
        array<CargoBase> proxies = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(anchor, radius, objects, proxies);
        if (objects.Count() > ScanCap(radius))
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
        Print("[HC Events] bind failed; " + mission.Id + "; reason=" + reason + s_FailDetails);
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
        s_FailDetails = "";
        if (!observer || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName) || !HCEventQualification.Admitted()) { return false; }
        if (mission.Family == HCEventFamily.INVESTIGATION) { return true; }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER) { return false; }
        if (mission.RewardCache) { return BindCache(observer, mission); }
        if (HCEventSites.PoliceSupplies(mission)) { return BindPolice(observer, mission); }
        if (!observer.ResetUnleasedTarget(mission.Id)) { return true; }
        s_FailReason = "";
        vector origin = mission.Source;
        float radius = 15;
        string wanted = mission.ItemClass;
        if (mission.Family == HCEventFamily.PRESENCE) { wanted = mission.AnchorClass; }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            wanted = "ZombieBase";
            radius = 60;
        }
        s_FailDetails = "; wanted=" + wanted + "; nearest_candidate_m=unknown_query_refused; radius_m=" + radius.ToString();
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            // Native: 3_Game/Global/Game.c:1176 SurfaceY(x, z). A police source is a model
            // origin standing about 7 m above its ground, so a sphere centred on it reaches
            // only about 13 m on the ground. Centre on the ground and search 60 m;
            // the density-scaled (8192-object) overflow refusal remains authoritative.
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
            float nearestCandidateSq = -1;
            int infectedCount = 0;
            int liveCount = 0;
            foreach (Object candidate : nearby)
            {
                ZombieBase infected = ZombieBase.Cast(candidate);
                if (infected && !infected.IsPendingDeletion())
                {
                    infectedCount = infectedCount + 1;
                    float candidateSq = vector.DistanceSq(infected.GetPosition(), origin);
                    if (nearestCandidateSq < 0 || candidateSq < nearestCandidateSq) { nearestCandidateSq = candidateSq; }
                    if (infected.IsAlive()) { liveCount = liveCount + 1; }
                }
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
                s_FailReason = "no_candidate; constraint=no_ce_infected_in_radius";
                if (liveCount == 0) { s_FailReason = "no_candidate; constraint=no_live_infected_in_radius"; }
                if (infectedCount == 0) { s_FailReason = "no_candidate; constraint=no_infected_in_radius"; }
                s_FailDetails = CandidateDetails(wanted, nearestCandidateSq, radius);
                return BindFailed(mission);
            }
            if (!observer.RegisterInfected(mission.Id, selected))
            {
                s_FailReason = "registration_refused";
                return BindFailed(mission);
            }
            return true;
        }
        bool economy = true;
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            wanted = mission.AnchorClass;
            economy = false;
        }
        HCEventTarget target = Select(nearby, wanted, economy);
        if (!target)
        {
            float nearestItemSq = -1;
            foreach (Object localCandidate : nearby)
            {
                if (localCandidate && !localCandidate.IsPendingDeletion() && localCandidate.GetType() == wanted)
                {
                    float itemDistanceSq = vector.DistanceSq(localCandidate.GetPosition(), origin);
                    if (nearestItemSq < 0 || itemDistanceSq < nearestItemSq) { nearestItemSq = itemDistanceSq; }
                }
            }
            s_FailDetails = CandidateDetails(wanted, nearestItemSq, radius);
            return BindFailed(mission);
        }
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            return observer.RegisterPresence(mission.Id, target.Presence);
        }
        HCEventTarget destination;
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            destination = Select(Query(mission.Destination, 15), mission.ContainerClass, true);
            if (!destination || destination.Item == target.Item)
            {
                // Name the container that failed; a refused query leaves no Select reason.
                string destinationReason = s_FailReason;
                if (destinationReason == "") { destinationReason = "query_unavailable"; }
                if (destination) { destinationReason = "same_item"; }
                s_FailReason = "destination_" + destinationReason;
                s_FailDetails = "; wanted=" + mission.ContainerClass + "; radius_m=15";
                return BindFailed(mission);
            }
        }
        if (!observer.RegisterTarget(mission.Id, target.Item)) { return false; }
        if (destination) { return observer.RegisterContainer(mission.Id, destination.Item); }
        return true;
    }
}
