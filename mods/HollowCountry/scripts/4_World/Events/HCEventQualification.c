// Native: 1_Core/proto/EnSystem.c:397 FileExist; 1_Core/proto/EnDebug.c:96 Print. HCV1Admission is an HC hook.
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
        return !FileExist("$profile:HollowCountry/acceptance/events.disable");
    }
    static bool Admitted()
    {
        if (Qualified()) { return true; }
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            // One shared V1 line (Core/HCV1Admission.c) for both preference states.
            Print(HCV1Admission.Line("Events", s_OptIn, "events", Qualified()));
        }
        return s_OptIn;
    }
}
