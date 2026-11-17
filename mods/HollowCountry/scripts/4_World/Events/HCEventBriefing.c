// Native: 1_Core/proto/EnConvert.c:30 int.ToString, :138 vector.ToString.
class HCEventBriefing
{
    static string Describe(HCEventMission mission)
    {
        string location = "Site " + mission.SiteId + " at " + mission.Source.ToString();
        string task = "Reach the area and remain for " + mission.DwellSeconds.ToString() + " seconds.";
        if (mission.Family == HCEventFamily.RECOVERY) { task = "Collect the existing " + mission.ItemClass + "."; }
        if (mission.Family == HCEventFamily.STATIC_SALVAGE) { task = "Collect the existing " + mission.ItemClass + " at the site."; }
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            task = "Carry the existing " + mission.ItemClass + ", then place it directly inside the " + mission.ContainerClass;
            task = task + " at " + mission.Destination.ToString() + ". Carrying it nearby does not complete delivery.";
        }
        if (mission.Family == HCEventFamily.PRESENCE) { task = "Reach and confirm the existing " + mission.AnchorClass + "."; }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR) { task = "Eliminate the bound local infected after joining. Environmental deaths do not count."; }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER) { task = "Optional Expansion AI encounter. Only the provider's observed objective counts."; }
        return location + "\n" + task + "\nNo additional reward. Collected supplies remain ordinary finite world items.";
    }
}
