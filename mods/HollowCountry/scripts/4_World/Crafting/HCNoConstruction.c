// HC-17 / #304: restore native construction, recipes, hologram collision,
// materials, locks, damage and persistence. Claim ACLs only admit NEW work;
// dismantling, destruction and forced entry remain native.
modded class PluginRecipesManager
{
    // Native PluginRecipesManager.c:457. HCRecipeRegistration still requests
    // these removals; preserve the originals without registering duplicate IDs.
    override protected void UnregisterRecipe(string clasname)
    {
        if (clasname == "CraftFenceKit" || clasname == "CraftWatchtowerKit" || clasname == "CraftTerritoryFlagKit" || clasname == "CraftShelterKit") { return; }
        super.UnregisterRecipe(clasname);
    }
}

modded class ActionBuildPart
{
    protected bool m_HCInvalidConstructionLogged;
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (target && target.GetObject() && !HCBuildingClaim.HCConstructionAllowed(player, target.GetObject().GetPosition())) { return false; }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_Target.GetObject()) { return false; }
        if (!HCBuildingClaim.HCConstructionAllowed(action_data.m_Player, action_data.m_Target.GetObject().GetPosition())) { return false; }
        return super.ActionConditionContinue(action_data);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_Target.GetObject())
        {
            if (!m_HCInvalidConstructionLogged) { Print("[HC Plan] HC-17 build=refused reason=missing_action_target runtime=PENDING"); m_HCInvalidConstructionLogged = true; }
            return;
        }
        if (!HCBuildingClaim.HCConstructionAllowed(action_data.m_Player, action_data.m_Target.GetObject().GetPosition()))
        {
            if (action_data.m_Player) { action_data.m_Player.MessageStatus("Building refused: claim ownership or group access changed."); }
            return;
        }
        super.OnFinishProgressServer(action_data);
    }
}

// Native hands subclass overrides both conditions; the commit above is shared.
modded class ActionBuildPartHandsGeneric
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (target && target.GetObject() && !HCBuildingClaim.HCConstructionAllowed(player, target.GetObject().GetPosition())) { return false; }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_Target.GetObject()) { return false; }
        if (!HCBuildingClaim.HCConstructionAllowed(action_data.m_Player, action_data.m_Target.GetObject().GetPosition())) { return false; }
        return super.ActionConditionContinue(action_data);
    }
}

modded class ActionDeployBase
{
    // Native ActionDeployBase.c:70/88 uses this server-validated placement DTO.
    // Only building kits get the ACL; tents, containers etc. retain native rules.
    override void OnFinishProgressServer(ActionData action_data)
    {
        PlaceObjectActionData placement = PlaceObjectActionData.Cast(action_data);
        if (placement && placement.m_MainItem)
        {
            ItemBase kit = placement.m_MainItem;
            if (kit.IsKindOf("FenceKit") || kit.IsKindOf("WatchtowerKit") || kit.IsKindOf("TerritoryFlagKit") || kit.IsKindOf("ShelterKit"))
            {
                if (!HCBuildingClaim.HCConstructionAllowed(placement.m_Player, placement.m_Position))
                {
                    if (placement.m_Player) { placement.m_Player.MessageStatus("Kit placement refused: this building is claimed by another group or claim access is unavailable."); }
                    return;
                }
            }
        }
        super.OnFinishProgressServer(action_data);
    }
}
