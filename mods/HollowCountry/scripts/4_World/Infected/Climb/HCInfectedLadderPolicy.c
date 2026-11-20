// Infected ladder climb: detection and variant selection only, DISABLED BY EVIDENCE
// (2026-11-20). Never a fake climb: no script translation, teleport or position write
// stands in for an animation, so this side never moves an infected while
// HC_LADDER_CLIMB_SUPPORTED is false.
//
// Blockers (installed scripts-1.30.164289 and repo state):
//  1. No infected ladder command. Only humans have one: 3_Game/human.c:666
//     HumanCommandLadder, :1510 HumanCommand StartCommand_Ladder(Building, int).
//     3_Game/Entities/DayZInfected.c:108-124 exposes Move/Vault/Death/Hit/Attack/
//     Crawl/Script only; vanilla infected graphs ship no ladder clip.
//  2. The only alternative is a new own-prefix clip carrying root motion up the
//     ladder in the HollowCountryAnims infected graph. That pipeline has never had a
//     clip observed playing in DayZ (docs/ANIMATION_PIPELINE.md:3 playback PENDING)
//     and authors no root motion (ANIMATION_PIPELINE.md:23, :141). Only
//     HC_ZmbM_Sitter uses that graph; CE infected keep the vanilla graph, so ladder
//     variants would also need new graph-bound classes.
//  3. Whether the infected physics controller follows vertical root motion outside
//     the native vault command is unobserved.
// Unblock order: one HC clip observed playing natively -> one root-motion clip
// observed translating an infected -> ladder clip + graph state + variant classes.
//
// While disabled, the reach module runs a shadow discovery at most once per admitted
// slot, reusing the floor-ray hit it already made under the target (no extra ray):
// Building.GetLaddersCount/GetLadderPosTop/GetLadderPosBottom (3_Game/Entities/
// Building.c:23-25). The coordinate space of those positions is unobserved, so both
// raw and ModelToWorld (Object.c:873) readings are scored and the matching space is
// logged. Object.c:467 GetType, :511 IsKindOf; EnConvert.c:196 vector.Distance.
class HCInfectedLadderPolicy
{
    static const bool HC_LADDER_CLIMB_SUPPORTED = false;
    static const string HC_LADDER_REFUSAL = "no_infected_ladder_command";
    // Slow climb for the selected variants once a real clip exists (a player's slow
    // ladder climb is roughly 1 m/s; infected climb at about a third of that).
    static const float HC_LADDER_METRES_PER_SECOND = 0.35;
    // A ladder counts when its top is within this distance of the target's feet and
    // its bottom within the second distance of the infected.
    static const float HC_LADDER_TOP_METRES = 3.0;
    static const float HC_LADDER_BOTTOM_METRES = 12.0;
    static const int HC_LADDER_MAX_SCAN = 8;

    // Lean, light-clothed civilian variants only: no fat, old, armoured, soldier,
    // NBC or crawling infected. Checked by vanilla base class.
    static bool VariantMayClimb(ZombieBase infected)
    {
        if (!infected || infected.IsCrawling()) { return false; }
        if (infected.IsKindOf("ZmbM_HermitSkinny_Base") || infected.IsKindOf("ZmbM_HikerSkinny_Base")) { return true; }
        if (infected.IsKindOf("ZmbM_JoggerSkinny_Base") || infected.IsKindOf("ZmbM_SkaterYoung_Base")) { return true; }
        if (infected.IsKindOf("ZmbM_MechanicSkinny_Base") || infected.IsKindOf("ZmbM_HandymanNormal_Base")) { return true; }
        if (infected.IsKindOf("ZmbM_ConstrWorkerNormal_Base") || infected.IsKindOf("ZmbM_FirefighterNormal_Base")) { return true; }
        if (infected.IsKindOf("ZmbF_HikerSkinny_Base") || infected.IsKindOf("ZmbF_JoggerSkinny_Base")) { return true; }
        return infected.IsKindOf("ZmbF_SkaterYoung_Base") || infected.IsKindOf("ZmbF_MechanicNormal_Base");
    }

    static float ClimbSeconds(float rise)
    {
        if (rise <= 0) { return 0; }
        return rise / HCInfectedLadderPolicy.HC_LADDER_METRES_PER_SECOND;
    }

    // Returns the best ladder index on the building under the target, or -1.
    // modelSpace reports which reading of the native positions matched.
    static int NearestLadder(Building host, vector targetFeet, vector infectedFeet, out vector bottom, out vector top, out bool modelSpace)
    {
        modelSpace = false;
        if (!host) { return -1; }
        int count = host.GetLaddersCount();
        if (count <= 0) { return -1; }
        if (count > HCInfectedLadderPolicy.HC_LADDER_MAX_SCAN) { count = HCInfectedLadderPolicy.HC_LADDER_MAX_SCAN; }
        int best = -1;
        float bestScore = 1000000;
        for (int i = 0; i < count; i++)
        {
            vector rawTop = host.GetLadderPosTop(i);
            vector rawBottom = host.GetLadderPosBottom(i);
            for (int space = 0; space < 2; space++)
            {
                vector candidateTop = rawTop;
                vector candidateBottom = rawBottom;
                if (space == 1)
                {
                    candidateTop = host.ModelToWorld(rawTop);
                    candidateBottom = host.ModelToWorld(rawBottom);
                }
                float topGap = vector.Distance(candidateTop, targetFeet);
                float bottomGap = vector.Distance(candidateBottom, infectedFeet);
                if (topGap > HCInfectedLadderPolicy.HC_LADDER_TOP_METRES || bottomGap > HCInfectedLadderPolicy.HC_LADDER_BOTTOM_METRES) { continue; }
                float score = topGap + bottomGap;
                if (score < bestScore)
                {
                    bestScore = score;
                    best = i;
                    top = candidateTop;
                    bottom = candidateBottom;
                    modelSpace = space == 1;
                }
            }
        }
        return best;
    }
}
