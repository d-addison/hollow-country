// #267: request-local group facts; never discover targets or retain player state.
class HCCampAllegianceContext
{
    string GroupId;
    ref map<string, bool> Members = new map<string, bool>;
    ref array<PlayerBase> OnlineMembers = new array<PlayerBase>;
}

// Optional adapters must explicitly establish safety. Unknown is dangerous.
class HCCampAllegianceProvider
{
    bool IsDanger(PlayerBase actor, HCCampAllegianceContext camp) { return true; }
}

class HCCampAllegianceHook
{
    protected static ref HCCampAllegianceProvider s_Provider;

    static void Install(HCCampAllegianceProvider provider) { s_Provider = provider; }

    static bool IsDanger(PlayerBase actor, HCCampAllegianceContext camp)
    {
        if (!actor || !camp || camp.GroupId == "" || !camp.Members || camp.Members.Count() < 1 || camp.Members.Count() > 90) { return true; }
        if (!camp.OnlineMembers || camp.OnlineMembers.Count() > 32 || !s_Provider) { return true; }
        return s_Provider.IsDanger(actor, camp);
    }
}
