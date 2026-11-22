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
    // The fortification check lives in the conditions, not only in the finish: a pack's
    // own finish override can replace the native one without calling super, and the
    // finish chain then depends on mod load order. The conditions are not replaced that way.
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (target && target.GetObject())
        {
            if (!HCBuildingClaim.HCConstructionAllowed(player, target.GetObject().GetPosition())) { return false; }
            string fortifyReason = HCFortifyBridge.HCBuildReason(player, target.GetObject());
            if (fortifyReason != "")
            {
                HCFortifyBridge.HCRefuseTo(player, fortifyReason);
                return false;
            }
        }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_Target.GetObject()) { return false; }
        if (!HCBuildingClaim.HCConstructionAllowed(action_data.m_Player, action_data.m_Target.GetObject().GetPosition())) { return false; }
        if (HCFortifyBridge.HCBuildReason(action_data.m_Player, action_data.m_Target.GetObject()) != "") { return false; }
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
        // Fortification packs: claim members only (or unclaimed ground by setting).
        // Checked again here for load orders where this finish runs before a pack's own.
        string fortifyReason = HCFortifyBridge.HCBuildReason(action_data.m_Player, action_data.m_Target.GetObject());
        if (fortifyReason != "")
        {
            HCFortifyBridge.HCRefuseTo(action_data.m_Player, fortifyReason);
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
        if (target && target.GetObject())
        {
            if (!HCBuildingClaim.HCConstructionAllowed(player, target.GetObject().GetPosition())) { return false; }
            string fortifyReason = HCFortifyBridge.HCBuildReason(player, target.GetObject());
            if (fortifyReason != "")
            {
                HCFortifyBridge.HCRefuseTo(player, fortifyReason);
                return false;
            }
        }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_Target.GetObject()) { return false; }
        if (!HCBuildingClaim.HCConstructionAllowed(action_data.m_Player, action_data.m_Target.GetObject().GetPosition())) { return false; }
        if (HCFortifyBridge.HCBuildReason(action_data.m_Player, action_data.m_Target.GetObject()) != "") { return false; }
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
        bool packKit = false;
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
            string fortifyReason = HCFortifyBridge.HCPlacementReason(placement.m_Player, kit, placement.m_Position);
            if (fortifyReason != "")
            {
                HCFortifyBridge.HCRefuseTo(placement.m_Player, fortifyReason);
                return;
            }
            packKit = HCFortifyBridge.HCActive() && HCFortifyBridge.HCIsPackKit(kit);
        }
        super.OnFinishProgressServer(action_data);
        // The kit may delete itself on placement; the flag was read before the commit.
        if (packKit && placement.m_AlreadyPlaced) { HCFortifyBridge.HCPlaced(); }
    }
}

// The native hologram deploy action overrides both conditions without calling the base
// ones, so the fortification kit check sits here too. The server's condition rejects the
// start (and every continue tick) before the client's local placement can complete; the
// finish check above stays as the last gate.
modded class ActionDeployObject
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!super.ActionCondition(player, target, item)) { return false; }
        string fortifyReason = HCFortifyBridge.HCDeployReason(player, item);
        if (fortifyReason != "")
        {
            HCFortifyBridge.HCRefuseTo(player, fortifyReason);
            return false;
        }
        return true;
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!super.ActionConditionContinue(action_data)) { return false; }
        if (!action_data.m_MainItem) { return true; }
        return HCFortifyBridge.HCDeployReason(action_data.m_Player, action_data.m_MainItem) == "";
    }
}
