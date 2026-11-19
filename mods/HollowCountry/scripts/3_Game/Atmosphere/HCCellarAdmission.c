// HC-31 shared server/client admission. Wave 16 owner decision (2026-11-19):
// "enable all features by default". Geometry probes, selection, preferences and
// EXP-A3 are still not native cellar qualification: no qualification receipt
// exists, so this gate is ADMITTED UNVERIFIED (the HCV2Admission pattern), never
// accepted. The reason below keeps the pending wording on every log line.
// Operator opt-outs stay the existing ones: the server module is gated by
// EnableAmbientLife (HCCellarsModule.IsEnabled) and the client heuristic by the
// HollowCountryDarkCellars profile preference (HCCellarsClient.HCPreferenceEnabled).
// No file probe here: the client calls HCAdmitted() every sample.
class HCCellarAdmission
{
    static bool HCAdmitted() { return true; }
    static string HCReason() { return "admitted_unverified_native_cellar_qualification_pending"; }
}
