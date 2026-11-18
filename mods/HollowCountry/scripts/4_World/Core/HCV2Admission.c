// V2 admission line format (LC-T003). Every V2 module logs exactly one Line()
// at start: its operator preference, its Gate experiment and whether the
// experiment register (docs/experiments/v2-experiments.json) records a GO or
// accepted FALLBACK verdict for it. Owner decision 2026-11-17: V2 features are
// on by default, so the preference alone admits a feature (Admitted); a missing
// verdict is logged as unverified, never claimed as accepted. The line is the
// observation an operator greps, not proof of behaviour.
class HCV2Admission
{
    static string OnOff(bool value)
    {
        if (value) { return "on"; }
        return "off";
    }

    static bool Admitted(bool preference)
    {
        return preference;
    }

    static string Line(string feature, bool preference, string gate, bool gateQualified)
    {
        string result = "admitted";
        if (!gateQualified) { result = "admitted unverified: " + gate + " has no recorded native verdict"; }
        if (!preference) { result = "off: operator preference"; }
        string qualified = "0";
        if (gateQualified) { qualified = "1"; }
        return "[HollowCountry] V2 admission feature=" + feature + " preference=" + OnOff(preference) + " gate=" + gate + " qualified=" + qualified + " result=" + result;
    }

    static string Summary(HCSettings settings)
    {
        if (!settings) { return "[HollowCountry] V2 preferences unavailable; runtime acceptance pending"; }
        string prefs = "Grade=" + OnOff(settings.EnableGrade) + " AmbientLife=" + OnOff(settings.EnableAmbientLife) + " SignsOfLife=" + OnOff(settings.EnableSignsOfLife) + " Travel=" + OnOff(settings.EnableTravel);
        prefs = prefs + " World=" + OnOff(settings.EnableWorld) + " Leads=" + OnOff(settings.EnableLeads) + " Camps=" + OnOff(settings.EnableCamps) + " Encounters=" + OnOff(settings.EnableEncounters);
        return "[HollowCountry] V2 preferences " + prefs + "; V2 features on by default, gate verdicts logged per module; runtime acceptance pending";
    }
}
