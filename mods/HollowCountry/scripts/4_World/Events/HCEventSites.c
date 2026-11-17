// Native: 1_Core/proto/EnMath3D.c:18 Vector; EnScript.c:407 array.Insert.
// Bounded DATA REVIEW, 2026-11-17, of two stock ChernarusPlus placements.
// Source: dayzOffline.chernarusplus/mapgrouppos.xml, SHA-256 below.
// No field survey, clearance, destination-container or loot guarantee exists.
// These candidates require events.enable and in-world validation. No spawning.
class HCEventSites
{
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
