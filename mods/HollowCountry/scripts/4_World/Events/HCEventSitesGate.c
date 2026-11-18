// Native: 1_Core/proto/EnSystem.c:397 FileExist; 1_Core/proto/EnDebug.c:96 Print;
// 3_Game/Global/Game.c IsServer. Server-only; source/translation is not acceptance.
// Marker is probed once per process on the server. It never admits a client.
class HCEventSitesGate
{
    protected static bool s_Checked;
    protected static bool s_OptIn;
    static bool Qualified()
    {
        return false;
    }
    static bool LocalAcceptanceOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/events_sites.disable");
    }
    static bool Admitted()
    {
        if (Qualified()) { return true; }
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            // One shared V1 line (Core/HCV1Admission.c) for both preference states.
            Print(HCV1Admission.Line("EventSites", s_OptIn, "events_sites", Qualified()));
        }
        return s_OptIn;
    }
}
