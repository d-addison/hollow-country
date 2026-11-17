// Native: 1_Core/proto/EnSystem.c:397 FileExist; 1_Core/proto/EnDebug.c:96 Print.
// Source/translation is not native acceptance. Marker probed once per process.
class HCEventQualification
{
    protected static bool s_Checked;
    protected static bool s_OptIn;
    static bool Qualified()
    {
        return false;
    }
    static bool LocalAcceptanceOptIn()
    {
        return FileExist("$profile:HollowCountry/acceptance/events.enable");
    }
    static bool Admitted()
    {
        if (Qualified()) { return true; }
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
            {
                Print("[HC Events] EXPERIMENTAL local acceptance opt-in; native objectives, journal, sites and presentation PENDING");
            }
            else
            {
                Print("[HC Events] native gameplay not admitted; runtime acceptance PENDING");
            }
        }
        return s_OptIn;
    }
}
