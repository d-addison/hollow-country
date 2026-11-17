// Each reviewed site supplies four authored noncombat assignments and one
// optional provider encounter. No coordinates, loot balance or AI are invented.
class HCEventRoster
{
    static array<ref HCEventMission> Build(HCEventSite site, bool includeAI)
    {
        array<ref HCEventMission> result = new array<ref HCEventMission>();
        if (!site || !site.Reviewed || (!site.Surveyed && !HCEventQualification.Admitted()))
        {
            return result;
        }
        int family = 1;
        while (family <= 7)
        {
            HCEventMission mission = new HCEventMission;
            mission.Id = site.Id + "-" + family.ToString();
            mission.SiteId = site.Id;
            mission.WorldName = site.WorldName;
            mission.Reviewed = site.Reviewed;
            mission.Family = family;
            mission.Source = site.Position;
            mission.Destination = site.Destination;
            mission.ItemClass = site.ItemClass;
            mission.ContainerClass = site.ContainerClass;
            mission.AnchorClass = site.AnchorClass;
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
            if ((family != HCEventFamily.AI_ENCOUNTER || includeAI) && HCEventRuntimePolicy.MissionValid(mission, site.WorldName))
            {
                result.Insert(mission);
            }
            family = family + 1;
        }
        return result;
    }
}
