// HC-17 / #151: construction-specific veto; containers anywhere retain native
// placement/cargo rules, as do tents, fireplaces, gardens, traps and lockpicks.
// Native scripts-1.30.164289 evidence:
// 3_Game/Entities/Object.c:511 IsKindOf;
// 4_World/Classes/Recipes/RecipeBase.c:479/521 CheckRecipe/PerformRecipe;
// Classes/UserActionsComponent/Actions/Continuous/ActionBuildPart.c:
// 89/123/150 condition/continue/server commit; 416/459 hands overrides;
// Actions/Continuous/DeployActions/ActionDeployObject.c:34/55/152/167
// condition/continue/client finish/server finish; ActionDeployBase.c:70 native
// placement transaction; ActionPlaceObject.c:9 inherits ActionDeployObject.
// Entities/ItemBase/BaseBuildingBase/ShelterSite.c:1/33/164 native site/build;
// ActionConstructor.c:187 registers hands building (obsolete ActionBuildShelter
// is unregistered in this snapshot). No deletion/refund of pre-existing bases or kits.
class HCNoConstruction
{
    static bool HCDeniedRecipe(string recipeName)
    {
        return recipeName == "CraftFenceKit" || recipeName == "CraftWatchtowerKit" || recipeName == "CraftTerritoryFlagKit" || recipeName == "CraftShelterKit";
    }

    static bool HCDeniedObject(Object objectToCheck)
    {
        return objectToCheck && (objectToCheck.IsKindOf("Fence") || objectToCheck.IsKindOf("Watchtower") || objectToCheck.IsKindOf("TerritoryFlag") || objectToCheck.IsKindOf("ShelterBase") || objectToCheck.IsKindOf("ShelterSite") || objectToCheck.IsKindOf("FenceKit") || objectToCheck.IsKindOf("WatchtowerKit") || objectToCheck.IsKindOf("TerritoryFlagKit") || objectToCheck.IsKindOf("ShelterKit"));
    }

    static bool HCDeniedTarget(ActionTarget target)
    {
        return target && HCDeniedObject(target.GetObject());
    }
}

modded class RecipeBase
{
    override bool CheckRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (HCNoConstruction.HCDeniedRecipe(ClassName())) { return false; }
        return super.CheckRecipe(item1, item2, player);
    }
    override void PerformRecipe(ItemBase item1, ItemBase item2, PlayerBase player)
    {
        if (HCNoConstruction.HCDeniedRecipe(ClassName())) { Print("[HC Plan] HC-17 construction=refused reason=construction_recipe runtime=PENDING"); return; }
        super.PerformRecipe(item1, item2, player);
    }
}

modded class ActionBuildPart
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (HCNoConstruction.HCDeniedTarget(target)) { return false; }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedTarget(action_data.m_Target)) { return false; }
        return super.ActionConditionContinue(action_data);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedTarget(action_data.m_Target)) { Print("[HC Plan] HC-17 construction=refused reason=missing_action_or_construction_target runtime=PENDING"); return; }
        super.OnFinishProgressServer(action_data);
    }
}

// Native hands subclass has its own conditions; guard those overrides too.
modded class ActionBuildPartHandsGeneric
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (HCNoConstruction.HCDeniedTarget(target)) { return false; }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedTarget(action_data.m_Target)) { return false; }
        return super.ActionConditionContinue(action_data);
    }
}

modded class ActionDeployObject
{
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (HCNoConstruction.HCDeniedObject(item)) { return false; }
        return super.ActionCondition(player, target, item);
    }
    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedObject(action_data.m_MainItem)) { return false; }
        return super.ActionConditionContinue(action_data);
    }
    override void OnFinishProgressClient(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedObject(action_data.m_MainItem)) { Print("[HC Plan] HC-17 construction=refused reason=missing_action_or_construction_deploy runtime=PENDING"); return; }
        super.OnFinishProgressClient(action_data);
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedObject(action_data.m_MainItem)) { Print("[HC Plan] HC-17 construction=refused reason=missing_action_or_construction_deploy runtime=PENDING"); return; }
        super.OnFinishProgressServer(action_data);
    }
}

// Guard the native transaction itself, including non-hologram deploy actions.
modded class ActionDeployBase
{
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data || HCNoConstruction.HCDeniedObject(action_data.m_MainItem)) { Print("[HC Plan] HC-17 construction=refused reason=missing_action_or_construction_deploy runtime=PENDING"); return; }
        super.OnFinishProgressServer(action_data);
    }
}
