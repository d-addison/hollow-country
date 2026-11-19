// HC-31 shared server/client admission. Geometry probes, selection, preferences
// and EXP-A3 are not native cellar qualification. No qualification receipt
// exists yet; keep both the module and the retained client heuristic refused.
class HCCellarAdmission
{
    static bool HCAdmitted() { return false; }
    static string HCReason() { return "native_cellar_qualification_pending"; }
}
