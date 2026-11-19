// #144: binds the picker run's house port to the shared HCSearchHouses finite
// reservations (auditsearch_PickerReservations.c). No new supply, cache or timer.
// Membership is rechecked against the live HC-34 trip lease every call, never
// inferred from proximity. Search off/stopped => refusal, the run skips houses.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c Cast; runtime PENDING.
class HCPickHouseAuthority : auditsearch_PickerAuthority
{
    override bool HCValid(PlayerBase actor, string actorId)
    {
        if (!actor || actorId == "") return false;
        HCPickers pickers = HCPickers.Get();
        if (!pickers) return false;
        HCScavengeTrip trip = pickers.HCTrip();
        if (!trip || !trip.m_IO || !trip.m_State) return false;
        HCScavengeInventory io = trip.m_IO;
        if (io.Actor != actor || !io.HCLive()) return false;
        return io.HCActorKey() == actorId && io.HCPartyCurrent(trip.m_State);
    }
}

class HCPickSearchHousePort : HCPickHousePort
{
    protected ref HCPickHouseAuthority m_Authority = new HCPickHouseAuthority;

    override string HCRefusal()
    {
        if (!HCSearchBinding.Houses()) return "PICKER_HOUSE_SEARCH_UNAVAILABLE";
        return "";
    }

    override Class HCReserve(PlayerBase actor, HCPickHouseTarget target, string actorId)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        if (!houses || !target || !target.Dwelling) return null;
        return houses.HCReservePicker(actor, target.Dwelling, target.SiteId, actorId, m_Authority);
    }

    override bool HCCommit(Class token)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCSearchHouseSession session = HCSearchHouseSession.Cast(token);
        if (!houses || !session) return false;
        return houses.HCCommitReservation(session);
    }

    override void HCRelease(Class token)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCSearchHouseSession session = HCSearchHouseSession.Cast(token);
        if (houses && session) houses.HCReleasePicker(session);
    }

    override EntityAI HCItem(Class token)
    {
        HCSearchHouses houses = HCSearchBinding.Houses();
        HCSearchHouseSession session = HCSearchHouseSession.Cast(token);
        if (!houses || !session) return null;
        return houses.HCPickerItem(session);
    }
}
