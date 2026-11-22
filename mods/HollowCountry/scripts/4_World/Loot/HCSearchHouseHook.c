// House search (HCSearchHouses) rides the existing search action. The action file keeps its
// hooks unchanged: for a House cursor target this override sends the five interior-module
// search calls to the lazy House service; every other target falls to the base module, which
// refuses with a reason. House search needs HCInteriorsModule.Get() (interiors enabled and the
// template pack loaded). Runtime acceptance PENDING.
modded class HCInteriorsModule
{
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
