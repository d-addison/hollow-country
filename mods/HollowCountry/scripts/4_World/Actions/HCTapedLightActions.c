// #56: weapon held, owned loose light + tape in inventory. Native flashlight
// actions already registered by Weapon_Base continue to handle switching.
class HCActionMountTapedLight extends ActionSingleUseBase
{
    void HCActionMountTapedLight()
    {
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_ATTACHITEM;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_Text = "Tape light to held item";
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
        HCRefusalReport.RefusalMessage(player, HCRefusal.TAPED_LIGHT_MOUNT, item, "Cannot tape this light now; check the held item, light and tape.");
        return false;
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data) return;
        int result = HCTapedLightRuntime.Execute(action_data.m_Player, action_data.m_MainItem, true);
        if (result != HCTapedLightCode.OK)
        {
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.TAPED_LIGHT_MOUNT, "Cannot tape this light now; check the held item, light and tape.");
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
        HCRefusalReport.RefusalMessage(player, HCRefusal.TAPED_LIGHT_REMOVE, item, "Cannot remove this taped light now; check the held item and inventory space.");
        return false;
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data) return;
        int result = HCTapedLightRuntime.Execute(action_data.m_Player, action_data.m_MainItem, false);
        if (result != HCTapedLightCode.OK)
        {
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.TAPED_LIGHT_REMOVE, "Cannot remove this taped light now; check the held item and inventory space.");
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
        actions.Insert(HCActionToggleTapedPackLight);
        actions.Insert(HCActionToggleTapedHelmetLight);
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

// Native scripts-1.30.164289: ItemBase.c:246 SetActions; TortillaBag.c:1
// exact backpack class. PlayerBase.c:1695 SetActions(out TInputActionMap),
// :1817 AddAction. EntityAI.c:1897 FindAttachmentBySlotName.
// SingleUse/ActionTurnOnWhileInHands.c:19-22,46-48 supplies native prone
// exception and ITEM_ON/FB_ITEM_ON commands; 3_Game/dayzplayer.c:639 ALL stance.
// Native mount/remove stay held-only, so the shared custody and LOS checks
// apply unchanged. No ground target, remote owner or AI inventory access.
modded class TortillaBag
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionMountTapedLight);
        AddAction(HCActionRemoveTapedLight);
    }
}

modded class Mich2001Helmet
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionMountTapedLight);
        AddAction(HCActionRemoveTapedLight);
    }
}

// Separate player actions allow either worn light to be switched when both
// are present. Selection is revalidated on the server at execution. The native
// energy manager retains all battery/wetness/light-lifetime behaviour.
class HCActionToggleTapedPackLight : ActionSingleUseBase
{
    void HCActionToggleTapedPackLight()
    {
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_ITEM_ON;
        m_CommandUIDProne = DayZPlayerConstants.CMD_ACTIONFB_ITEM_ON;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ALL;
        m_Text = "Toggle backpack light";
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTNone;
    }

    override bool HasTarget() { return false; }
    override bool UseMainItem() { return false; }
    override bool HasProneException() { return true; }
    string HCWearSlot() { return "Back"; }

    ItemBase HCHost(PlayerBase player)
    {
        if (!player) { return null; }
        ItemBase heldHost = player.GetItemInHands();
        if (HCWearSlot() == "Back" && heldHost && heldHost.GetType() == "TortillaBag") { return heldHost; }
        if (HCWearSlot() == "Headgear" && heldHost && heldHost.GetType() == "Mich2001Helmet") { return heldHost; }
        return ItemBase.Cast(player.FindAttachmentBySlotName(HCWearSlot()));
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (GetGame().IsServer() && !HCTapedLightAdmission.Admitted()) { return false; }
        return HCTapedLightRuntime.HCToggleCandidate(player, HCHost(player)) != null;
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data) { return; }
        if (!HCTapedLightRuntime.HCToggle(action_data.m_Player, HCHost(action_data.m_Player)))
        {
            HCRefusalReport.ActionRefusalMessage(action_data, "taped_light_switch_unavailable", "Cannot switch this light now; check the mounted light and battery.");
        }
    }
}

class HCActionToggleTapedHelmetLight : HCActionToggleTapedPackLight
{
    void HCActionToggleTapedHelmetLight() { m_Text = "Toggle helmet light"; }
    override string HCWearSlot() { return "Headgear"; }
}

modded class PlayerBase
{
    override void SetActions(out TInputActionMap InputActionMap)
    {
        super.SetActions(InputActionMap);
        AddAction(HCActionToggleTapedPackLight, InputActionMap);
        AddAction(HCActionToggleTapedHelmetLight, InputActionMap);
    }
}
