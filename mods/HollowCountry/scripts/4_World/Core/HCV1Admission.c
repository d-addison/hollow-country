// V1 admission line format, mirroring HCV2Admission. Owner decision 2026-11-18:
// every V1 feature is on by default. The operator preference (no
// $profile:HollowCountry/acceptance/<gate>.disable opt-out file) admits the
// feature; a missing native verdict is logged "admitted unverified", never
// claimed accepted. True safety gates (invalid config, missing native API,
// budget caps, no-teleport/no-omniscient-AI/no-duplicate-loot rules, server
// authority) stay in each feature and log their own refusal. The line is the
// observation an operator greps, not proof of behaviour.
// Each feature keeps its own literal opt-out probe (FileExist, 1_Core/proto/
// EnSystem.c:397 in scripts-1.30.164289) so the acceptance checklist can trace it.
class HCV1Admission
{
    static string Line(string feature, bool preference, string gate, bool gateQualified)
    {
        string result = "admitted";
        if (!gateQualified) { result = "admitted unverified: " + gate + " has no recorded native verdict; opt out with acceptance/" + gate + ".disable"; }
        if (!preference) { result = "off: operator opt-out acceptance/" + gate + ".disable"; }
        string qualified = "0";
        if (gateQualified) { qualified = "1"; }
        string prefer = "off";
        if (preference) { prefer = "on"; }
        return "[HollowCountry] V1 admission feature=" + feature + " preference=" + prefer + " gate=" + gate + " qualified=" + qualified + " result=" + result;
    }

    // A preference-admitted feature refused by a true safety gate.
    static string Refused(string feature, string gate, string reason)
    {
        return "[HollowCountry] V1 admission feature=" + feature + " preference=on gate=" + gate + " qualified=0 result=refused: " + reason;
    }
}
