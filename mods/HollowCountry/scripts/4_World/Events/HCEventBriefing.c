// HC-38: factual environmental clue only, never an instruction, objective,
// acceptance prompt, progress, participant identity or reward promise.
// Native scripts-1.30.164289: 1_Core/proto/EnConvert.c:138 vector.ToString.
class HCEventBriefing
{
    static string Describe(HCEventMission mission)
    {
        if (!mission) { return ""; }
        return "Signs of activity at " + mission.SiteId + " (" + mission.Source.ToString() + ").";
    }
}
