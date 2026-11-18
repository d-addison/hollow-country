// V2 gate verdicts compiled into the mod. QUALIFIED mirrors the GO and accepted
// FALLBACK entries of docs/experiments/v2-experiments.json (validated by
// tools/validate/experiments.py); it is empty until a native session records a
// verdict. A V2 module runs only when HCV2Admission.Line(...) reports admitted:
//   bool admitted = settings.EnableCamps && HCV2Gates.Qualified("EXP-L7");
//   Print(HCV2Admission.Line("Camps", settings.EnableCamps, "EXP-L7", HCV2Gates.Qualified("EXP-L7")));
class HCV2Gates
{
    // Space-separated ids with a leading and trailing space, for example " EXP-A1 EXP-T3 ".
    static const string QUALIFIED = " ";

    static bool Qualified(string id)
    {
        if (id == "") { return false; }
        return QUALIFIED.Contains(" " + id + " ");
    }
}
