// Row cursor native evidence: 1_Core/proto/EnScript.c:380 Count, :399 Get.
// W5 #122: shared snapshot contributor; no tick or player enumeration. Describe
// visits <=66 site states, <=64 member slots, and <=2 routes of <=128 points.
// No allocations when stopped or snapshot preference is off (shared caller).
// Native scripts-1.30.164289/3_Game/Entities/Object.c:287 GetPosition, :517
// IsAlive; 1_Core/proto/EnConvert.c:30 int.ToString. Read-only installed
// ai_scripts.pbo/4_World/DayZExpansion_AI/Classes/eAIGroup.c:671 GetFaction,
// :1123 IsInCombat,
// :1139 GetMember, :1185 Count. HC API: HCDebugSnapshot supplied by base mod.
class HCXAIPatrolDebug : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run" || !snapshot) { return; }
        array<ref HCXAISiteState> states = director.States();
        while (snapshot.HCRow < states.Count())
        {
            if (snapshot.HCRow >= 66 || (snapshot.HCShown >= 64 && snapshot.HCSubRow == 0) || snapshot.HCTotal >= 2) { break; }
            HCXAISiteState state = states[snapshot.HCRow];
            if (!state || !state.Qualified || !state.Patrol)
            {
                if (!snapshot.HCRowStep()) { return; }
                snapshot.HCSubRow = 0;
                continue;
            }
            eAIGroup group = HCXExpansionBridge.HCHoldResolve(state.Patrol.HCGroupHold());
            if (!group || HCXExpansionBridge.HCGroupCount(group) == 0)
            {
                if (!snapshot.HCRowStep()) { return; }
                snapshot.HCSubRow = 0;
                continue;
            }
            string faction = HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(group));
            if (faction == "") { faction = state.Site.Faction; }
            string activity = "patrol";
            if (HCXExpansionBridge.HCGroupIsInCombat(group)) { activity = "combat"; }
            string detail = "faction=" + faction + " state=" + activity + " kind=" + state.Site.Kind;
            int memberIndex = snapshot.HCSubRow;
            while (memberIndex < HCXExpansionBridge.HCGroupCount(group) && snapshot.HCShown < 64)
            {
                // RowStep advances the outer index; keep it until this group ends.
                if (!snapshot.HCRowStep()) { return; }
                snapshot.HCRow--;
                snapshot.HCShown++;
                DayZPlayerImplement member = HCXExpansionBridge.HCGroupGetMember(group, memberIndex);
                if (member && member.IsAlive())
                {
                    snapshot.AddPoint("ai", state.Site.Id + ":" + memberIndex.ToString(), member.GetPosition(), state.Site.Id, detail);
                }
                memberIndex++;
                snapshot.HCSubRow = memberIndex;
            }
            if (!snapshot.HCRowStep()) { return; }
            snapshot.HCRow--;
            if (state.PatrolPoints.Count() > 0 && state.PatrolPoints.Count() <= 128)
            {
                snapshot.AddRoute("ai", state.Site.Id, state.PatrolPoints, state.Site.Id + " " + detail);
            }
            snapshot.HCRow++;
            snapshot.HCSubRow = 0;
            snapshot.HCTotal++;
        }
    }
}
