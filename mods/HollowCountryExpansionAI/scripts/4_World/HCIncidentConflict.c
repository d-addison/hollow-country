// E1: the existing HCXFactionCombatAdapter records a witnessed live fight or
// changed deceased count in HCDisengaged. Publish on that first observation,
// never from HCOffer, a territory outcome, or a town's ledger coordinates.
// Shared policy has no faction_clash kind: use its existing visual scene kind.
// Expansion xref/ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:1139 GetMember,
// :1185 Count. Native scripts-1.30.164289: 3_Game/Entities/Object.c:287 GetPosition.
// m_Groups (group ids, resolved live) is capped at HCXFactionCombatAdapter.MAX_RECORDED_GROUPS (2); no
// polling beyond the existing conflict tick. HCSurveyed resets m_SeenCombat for
// the next encounter. Default ON; acceptance/world_incidents.disable opts out.
// Actual native combat, sight and replication remain runtime=PENDING.
modded class HCXFactionCombatAdapter
{
    override bool HCDisengaged(string encounter)
    {
        bool seenBefore = m_SeenCombat;
        bool disengaged = super.HCDisengaged(encounter);
        if (!seenBefore && m_SeenCombat)
        {
            array<int> groupIds = m_Groups;
            foreach (int groupId : groupIds)
            {
                eAIGroup group = HCXExpansionBridge.HCGroupById(groupId);
                if (!group || HCXExpansionBridge.HCGroupCount(group) < 1) { continue; }
                DayZPlayerImplement participant = HCXExpansionBridge.HCGroupGetMember(group, 0);
                if (!participant) { continue; }
                HCIncidentEmissions.HCPublish("scene", participant.GetPosition(), null);
                break;
            }
        }
        return disengaged;
    }
}
