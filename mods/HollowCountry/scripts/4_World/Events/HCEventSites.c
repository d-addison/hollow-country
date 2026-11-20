// Native: 1_Core/proto/EnMath3D.c:18 Vector; EnScript.c:407 array.Insert.
// Bounded DATA REVIEW, 2026-11-17, of two stock ChernarusPlus placements.
// Source: dayzOffline.chernarusplus/mapgrouppos.xml, SHA-256 below.
// No field survey, clearance, destination-container or loot guarantee exists.
// Police supply lookup is also turned off by events_sites.disable. It borrows
// existing physical cargo within the source-centred mission radius, falling back
// to one journaled HC cache per site. Barrel_Green is an HC cache/delivery class,
// not a promise of CE cargo. Both station origins match stock mapgrouppos rows.
// No field clearance/door/path acceptance is implied; Surveyed stays false.
class HCEventSites
{
    // Reuse only the two exact source-reviewed defaults. Operator coordinates/classes
    // remain authoritative; an edited site does not silently acquire an unreviewed spawn.
    static bool PoliceSupplies(HCEventMission mission)
    {
        if (!mission || mission.RewardCache) { return false; }
        if (mission.Family != HCEventFamily.RECOVERY && mission.Family != HCEventFamily.DELIVERY && mission.Family != HCEventFamily.STATIC_SALVAGE) { return false; }
        array<ref HCEventSite> defaults = ChernarusPlus();
        foreach (HCEventSite site : defaults)
        {
            string wanted = site.ItemClass;
            if (mission.Family == HCEventFamily.DELIVERY) { wanted = site.DeliveryClass; }
            if (mission.Family == HCEventFamily.STATIC_SALVAGE) { wanted = site.SalvageClass; }
            if (mission.SiteId == site.Id && mission.Id == site.Id + "-" + mission.Family.ToString() && mission.WorldName == site.WorldName && mission.Source == site.Position && mission.Destination == site.Destination && mission.ItemClass == wanted && mission.ContainerClass == site.ContainerClass && mission.AnchorClass == site.AnchorClass)
            {
                return true;
            }
        }
        return false;
    }
    static array<ref HCEventSite> ChernarusPlus()
    {
        array<ref HCEventSite> sites = new array<ref HCEventSite>();
        HCEventSite coastal = new HCEventSite;
        coastal.Id = "coastal-police-source";
        coastal.WorldName = "chernarusplus";
        coastal.Reviewed = true;
        coastal.Surveyed = false;
        coastal.Position = Vector(3569.727783, 13.309641, 2431.353027);
        coastal.Destination = coastal.Position;
        coastal.AnchorClass = "Land_Village_PoliceStation";
        coastal.ItemClass = "BandageDressing";
        coastal.DeliveryClass = "SodaCan_Cola";
        coastal.SalvageClass = "MetalWire";
        coastal.ContainerClass = "Barrel_Green";
        coastal.Provenance = "stock-mapgrouppos-source-review";
        coastal.SourceSha256 = "3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4";
        sites.Insert(coastal);
        HCEventSite inland = new HCEventSite;
        inland.Id = "inland-police-source";
        inland.WorldName = "chernarusplus";
        inland.Reviewed = true;
        inland.Surveyed = false;
        inland.Position = Vector(3421.308105, 199.735687, 13019.891602);
        inland.Destination = inland.Position;
        inland.AnchorClass = "Land_Village_PoliceStation";
        inland.ItemClass = "BandageDressing";
        inland.DeliveryClass = "SodaCan_Cola";
        inland.SalvageClass = "MetalWire";
        inland.ContainerClass = "Barrel_Green";
        inland.Provenance = "stock-mapgrouppos-source-review";
        inland.SourceSha256 = coastal.SourceSha256;
        sites.Insert(inland);
        return sites;
    }
}
