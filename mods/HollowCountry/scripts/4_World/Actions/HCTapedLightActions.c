// #56: weapon held, owned loose light + tape in inventory. Native flashlight
// actions already registered by Weapon_Base continue to handle switching.
class HCActionMountTapedLight extends ActionSingleUseBase
{
    void HCActionMountTapedLight()
    {
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_ATTACHITEM;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_Text = "Tape light to weapon";
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTNone;
    }

    override bool HasTarget()
    {
        return false;
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!GetGame().IsServer()) { return HCTapedLightRuntime.PreviewHint(player, item, true); }
        if (HCTapedLightRuntime.CanExecute(player, item, true)) return true;
        HCRefusalReport.RefusalMessage(player, HCRefusal.TAPED_LIGHT_MOUNT, item, "Cannot tape this light now; check the weapon, light and tape.");
        return false;
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data) return;
        int result = HCTapedLightRuntime.Execute(action_data.m_Player, action_data.m_MainItem, true);
        if (result != HCTapedLightCode.OK)
        {
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.TAPED_LIGHT_MOUNT, "Cannot tape this light now; check the weapon, light and tape.");
        }
    }
}

class HCActionRemoveTapedLight extends ActionSingleUseBase
{
    void HCActionRemoveTapedLight()
    {
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_ATTACHITEM;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_Text = "Remove taped light";
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTNone;
    }

    override bool HasTarget()
    {
        return false;
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!GetGame().IsServer()) { return HCTapedLightRuntime.PreviewHint(player, item, false); }
        if (HCTapedLightRuntime.CanExecute(player, item, false)) return true;
        HCRefusalReport.RefusalMessage(player, HCRefusal.TAPED_LIGHT_REMOVE, item, "Cannot remove this taped light now; check the weapon and inventory space.");
        return false;
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data) return;
        int result = HCTapedLightRuntime.Execute(action_data.m_Player, action_data.m_MainItem, false);
        if (result != HCTapedLightCode.OK)
        {
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.TAPED_LIGHT_REMOVE, "Cannot remove this taped light now; check the weapon and inventory space.");
        }
    }
}

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionMountTapedLight);
        actions.Insert(HCActionRemoveTapedLight);
    }
}

modded class Weapon_Base
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionMountTapedLight);
        AddAction(HCActionRemoveTapedLight);
    }
}
