// Each reviewed site supplies four authored noncombat assignments and one
// optional provider encounter. No coordinates, loot balance or AI are invented.
// A RewardCache site (on unless events_sites.disable) offers only reach-the-site (INVESTIGATION)
// and recover-the-cache (RECOVERY); the cache is created at bind time, never here.
// Native 1.30.164289: 1_Core/proto/EnScript.c:407 array Insert;
// 1_Core/proto/EnString.c:171 ToLower; EnConvert.c:30 int.ToString.
class HCEventRoster
{
    static array<ref HCEventMission> Build(HCEventSite site, bool includeAI)
    {
        array<ref HCEventMission> result = new array<ref HCEventMission>();
        if (!site || !site.Reviewed || (!site.Surveyed && !HCEventQualification.Admitted()))
        {
            return result;
        }
        if (site.RewardCache && !HCEventSitesGate.Admitted())
        {
            return result;
        }
        // Vanilla lowercases the engine world name; stored identity is canonical lowercase.
        string world = site.WorldName;
        world.ToLower();
        int family = 1;
        while (family <= 7)
        {
            HCEventMission mission = new HCEventMission;
            mission.Id = site.Id + "-" + family.ToString();
            mission.SiteId = site.Id;
            mission.WorldName = world;
            mission.Reviewed = site.Reviewed;
            mission.Family = family;
            mission.Source = site.Position;
            mission.Destination = site.Destination;
            mission.ItemClass = site.ItemClass;
            mission.ContainerClass = site.ContainerClass;
            mission.AnchorClass = site.AnchorClass;
            mission.RewardCache = site.RewardCache && family == HCEventFamily.RECOVERY;
            bool offered = !site.RewardCache || family == HCEventFamily.RECOVERY || family == HCEventFamily.INVESTIGATION;
            if (family == HCEventFamily.DELIVERY && site.DeliveryClass != "")
            {
                mission.ItemClass = site.DeliveryClass;
            }
            if (family == HCEventFamily.STATIC_SALVAGE && site.SalvageClass != "")
            {
                mission.ItemClass = site.SalvageClass;
            }
            if (family == HCEventFamily.AI_ENCOUNTER)
            {
                mission.ActorBudget = 2;
            }
            if (family == HCEventFamily.INFECTED_CLEAR)
            {
                // Bind searches a 60 m ground-centred sphere; include a small
                // station model-origin height margin in native Ready/Observe.
                mission.Radius = 65;
            }
            if (offered && (family != HCEventFamily.AI_ENCOUNTER || includeAI) && HCEventRuntimePolicy.MissionValid(mission, world))
            {
                result.Insert(mission);
            }
            family = family + 1;
        }
        return result;
    }
}
