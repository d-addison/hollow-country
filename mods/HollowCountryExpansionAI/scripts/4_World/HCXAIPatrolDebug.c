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
        int visited = 0;
        int memberSlots = 0;
        int routes = 0;
        foreach (HCXAISiteState state : states)
        {
            if (visited >= 66 || memberSlots >= 64 || routes >= 2) { break; }
            visited++;
            if (!state || !state.Qualified || !state.Patrol) { continue; }
            eAIGroup group = state.Patrol.m_Group;
            if (!group || group.Count() == 0) { continue; }
            string faction = HCXFactions.Id(group.GetFaction());
            if (faction == "") { faction = state.Site.Faction; }
            string activity = "patrol";
            if (group.IsInCombat()) { activity = "combat"; }
            string detail = "faction=" + faction + " state=" + activity + " kind=" + state.Site.Kind;
            int memberIndex = 0;
            while (memberIndex < group.Count() && memberSlots < 64)
            {
                DayZPlayerImplement member = group.GetMember(memberIndex);
                memberSlots++;
                if (member && member.IsAlive())
                {
                    snapshot.AddPoint("ai", state.Site.Id + ":" + memberIndex.ToString(), member.GetPosition(), state.Site.Id, detail);
                }
                memberIndex++;
            }
            if (state.PatrolPoints.Count() > 0 && state.PatrolPoints.Count() <= 128)
            {
                snapshot.AddRoute("ai", state.Site.Id, state.PatrolPoints, state.Site.Id + " " + detail);
            }
            routes++;
        }
    }
}
