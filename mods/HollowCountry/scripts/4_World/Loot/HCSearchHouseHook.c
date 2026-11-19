// House search (HCSearchHouses) rides the existing search action. The action file keeps its
// hooks unchanged: for a House cursor target this override sends the five interior-module
// search calls to the lazy House service, and every other target still takes the pilot path.
// Like the pilot, House search therefore needs HCInteriorsModule.Get() (interiors enabled and
// started). Runtime acceptance PENDING.
modded class HCInteriorsModule
{
    // Membership/health only. The action still validates geometry, locks, revisit age
    // and a finite supply on the server before any journal claim or transfer.
    HCInteriorSite HCLootKnownPilotSite(PlayerBase player, Object cabinet)
    {
        if (!m_Ready || !m_SearchProof || !m_Store || !m_Store.Healthy() || !m_Economy || !m_Economy.Serving()) return null;
        HCInteriorSite site = FindSite(cabinet);
        if (!site) return null;
        if (SearchGate(player, site)) return site;
        HCSearchRefreshPilotHouses refresh = HCSearchRefreshModule.Pilot();
        HCSearchRefreshPilotSite reviewed = HCSearchRefreshPilotCatalog.Find(site.Id);
        if (refresh && reviewed && reviewed.Site == site && refresh.Gate(player)) return site;
        return null;
    }

    override bool CanStart(PlayerBase player, ActionTarget target)
    {
        if (HCSearchHouses.IsHouseTarget(target))
        {
            HCSearchHouses houses = HCSearchBinding.Houses();
            return houses && houses.CanStart(player, target);
        }
        return super.CanStart(player, target);
    }

    override bool CanContinue(ActionData data)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        if (houses && houses.OwnsAction(data)) return houses.CanContinue(data);
        return super.CanContinue(data);
    }

    override void BeginSearch(ActionData data)
    {
        if (data && HCSearchHouses.IsHouseTarget(data.m_Target))
        {
            HCSearchHouses houses = HCSearchBinding.Houses();
            if (houses) houses.Begin(data);
            return;
        }
        super.BeginSearch(data);
    }

    override void CommitSearch(ActionData data)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        if (houses && houses.OwnsAction(data))
        {
            houses.Commit(data);
            return;
        }
        super.CommitSearch(data);
    }

    override void EndSearch(ActionData data)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        if (houses && houses.OwnsAction(data))
        {
            houses.End(data);
            return;
        }
        super.EndSearch(data);
    }
}
