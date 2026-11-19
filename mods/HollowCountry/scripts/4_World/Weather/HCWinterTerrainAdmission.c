// HC-50 / #150: white terrain feasibility remains OPEN; runtime acceptance pending.
// One bounded receipt, called by the existing weather owner after HC-6 start.
// No module, tick, texture mutation, dependency loader or second season clock.
// config/hollow-country-winter-terrain.json is a research record, NOT a live
// setting or qualification receipt. No verified terrain dependency exists in
// HC-60; editing that record cannot enable this policy. HC-62 owns acquisition,
// exact package receipts and stopped-server ordering after permitted selection.
// Consumes HCVisualSeasons.HCActive()/HCSeason(), never a default phase while off.
// Native scripts-1.30.164289 (root ~/.cache/hollow-country/native-scripts/scripts-1.30.164289):
// 3_Game/gameplay.c:636 GetGame; 3_Game/Global/Game.c:1120 IsServer;
// 1_Core/proto/EnDebug.c:96 Print. No other engine calls.
class HCWinterTerrainAdmission
{
    static string HCLine(HCVisualSeasons seasons)
    {
        string state = "pending";
        string reason = "NO_VERIFIED_TERRAIN_SOURCE_OR_RIGHTS";
        string season = "unavailable";
        if (!seasons)
        {
            state = "refused";
            reason = "HC6_UNAVAILABLE";
        }
        else
        {
            if (!seasons.HCActive())
            {
                state = "refused";
                reason = "HC6_NOT_ADMITTED";
            }
            else
            {
                season = seasons.HCSeason();
            }
        }
        string line = "[HC Plan] HC-50 white_terrain=" + state + " dependency=none boundary=stopped-server-restart";
        line = line + " season=" + season + " reason=" + reason;
        line = line + " refusal=DYNAMIC_TERRAIN_API_UNPROVEN";
        return line + " effective=off admitted=0 observed=unknown runtime=PENDING missing_part=native_terrain_whitening_unavailable native_snowfall=retained";
    }

    static void HCReport(HCVisualSeasons seasons)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        Print(HCLine(seasons));
    }
}
