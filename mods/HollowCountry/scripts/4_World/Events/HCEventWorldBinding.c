// Native: 3_Game/Global/Game.c:930 GetObjectsAtPosition3D; EntityAI.c:882/885 hierarchy.
// Native: 3_Game/Entities/Object.c:215/287/467/517/1219 deletion/pose/type/life/ruin.
// Query is local, never GetPlayers/world traversal. The native API allocates its
// result before our 128-entry refusal; this is not an engine-side query cap.
// No create/move/delete/CE replenishment call is used by this adapter.
class HCEventWorldBinding
{
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
        if (objects.Count() > 128) { return null; }
        return objects;
    }
    static HCEventTarget Select(array<Object> objects, string className, bool economy)
    {
        // This DTO preserves the exact native handle; no substitute loot.
        if (!objects || objects.Count() > 128) { return null; }
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
                    if (found) { return null; }
                    found = new HCEventTarget;
                    found.Presence = candidate;
                    found.Item = item;
                }
            }
        }
        return found;
    }
    static bool Bind(HCEventNativeObserver observer, HCEventMission mission)
    {
        if (!observer || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName) || !HCEventQualification.Admitted()) { return false; }
        if (mission.Family == HCEventFamily.INVESTIGATION) { return true; }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER) { return false; }
        if (!observer.ResetUnleasedTarget(mission.Id)) { return true; }
        array<Object> nearby = Query(mission.Source, 15);
        if (!nearby) { return false; }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            ZombieBase selected;
            foreach (Object candidate : nearby)
            {
                ZombieBase infected = ZombieBase.Cast(candidate);
                if (infected && infected.HCEventEconomyCandidate() && infected.IsAlive() && !infected.IsPendingDeletion())
                {
                    if (selected) { return false; }
                    selected = infected;
                }
            }
            return selected && observer.RegisterInfected(mission.Id, selected);
        }
        string wanted = mission.ItemClass;
        bool economy = true;
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            wanted = mission.AnchorClass;
            economy = false;
        }
        HCEventTarget target = Select(nearby, wanted, economy);
        if (!target) { return false; }
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            return observer.RegisterPresence(mission.Id, target.Presence);
        }
        HCEventTarget destination;
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            destination = Select(Query(mission.Destination, 15), mission.ContainerClass, true);
            if (!destination || destination.Item == target.Item) { return false; }
        }
        if (!observer.RegisterTarget(mission.Id, target.Item)) { return false; }
        if (destination) { return observer.RegisterContainer(mission.Id, destination.Item); }
        return true;
    }
}
