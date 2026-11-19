// Instance-known pilot preview; house previews keep their existing geometry path.
// Native 1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 4_World/Classes/UserActionsComponent/ActionTargets.c:143-172 GetObject/GetParent/GetComponentIndex.
// Server CanStart/CanContinue and the existing journal remain the inventory authority.
// CAP-09, replication and two-client acceptance remain runtime=PENDING.
modded class HCActionSearchInterior
{
    static bool HCLootPreview(PlayerBase player, ActionTarget target)
    {
        if (target && target.GetObject() && HCInteriorCatalog.SearchType(target.GetObject().GetType()))
        {
            return HCSearchPreviewSites.Get().PilotMatches(player, target);
        }
        return Preview(player, target);
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!GetGame().IsServer()) return !item && HCLootPreview(player, target);
        return super.ActionCondition(player, target, item);
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!GetGame().IsServer()) return HCLootPreview(action_data.m_Player, action_data.m_Target);
        return super.ActionConditionContinue(action_data);
    }
}
