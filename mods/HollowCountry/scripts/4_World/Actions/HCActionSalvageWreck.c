// LC-T203. Installed scripts-1.30.164289 native action APIs:
// 4_World/Classes/UserActionsComponent/ActionConstructor.c:27 RegisterActions;
// 4_World/Classes/UserActionsComponent/ActionBase.c:436,441,1391,1409 conditions/start/end;
// 4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:289 completion;
// 4_World/Classes/UserActionsComponent/ActionComponents/CAContinuousTime.c:9 duration;
// 4_World/Entities/ItemBase/Gear/Tools/Wrench.c:3 SetActions/AddAction;
// 4_World/Entities/ItemBase/Screwdriver.c:18 and Pliers.c:8 SetActions/AddAction.
// Same registration/callback pattern as HCFuelSiphon and HCInteriorAction.
// Client only previews geometry; module, journal, reservations and creation are
// exclusively server-owned. Duration/range/LOS/tool/target rechecked on completion.

class HCWreckSalvageActionData : ActionData
{
    Object Wreck;
    ItemBase Tool;
    string Key;
    int Index = -1;
    int StartedMs;
    bool Completed;
}

class HCActionSalvageWreckCB : ActionContinuousBaseCB
{
    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousTime(8.0);
    }
}

class HCActionSalvageWreck : ActionContinuousBase
{
    void HCActionSalvageWreck()
    {
        m_CallbackClass = HCActionSalvageWreckCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_INTERACT;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_FullBody = true;
        m_Text = "Salvage wreck";
    }

    override ActionData CreateActionData() { return new HCWreckSalvageActionData; }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTCursor(2.0);
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!GetGame().IsServer()) return HCWreckSalvage.Allowed(player, target, item);
        HCWreckSalvageModule module = HCWreckSalvageModule.Get();
        if (module && module.CanStart(player, target, item)) return true;
        // CanStart names its cause on the module; report it through the bounded per-reason window.
        string reason = HCRefusal.SALVAGE;
        if (module) reason = module.StartRefusal();
        if (reason == "") reason = HCRefusal.SALVAGE;
        HCCraftRefusal.WreckTarget(player, target, item, reason);
        return false;
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data) return false;
        if (!GetGame().IsServer()) return HCWreckSalvage.Allowed(action_data.m_Player, action_data.m_Target, action_data.m_MainItem);
        HCWreckSalvageModule module = HCWreckSalvageModule.Get();
        if (module && module.Continuing(HCWreckSalvageActionData.Cast(action_data))) return true;
        HCWreckSalvageActionData data = HCWreckSalvageActionData.Cast(action_data);
        if (data && !data.Completed)
            HCCraftRefusal.WreckAction(action_data, HCRefusal.SALVAGE);
        return false;
    }

    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        HCWreckSalvageModule module = HCWreckSalvageModule.Get();
        HCWreckSalvageActionData data = HCWreckSalvageActionData.Cast(action_data);
        if (data && !data.Completed)
        {
            if (module) module.Begin(data);
            if (!module || !module.Continuing(data))
            {
                string reason = HCRefusal.SALVAGE;
                if (module) reason = module.LastRefusal();
                HCCraftRefusal.WreckAction(action_data, reason);
            }
        }
    }

    override void OnFinishProgressServer(ActionData action_data)
    {
        HCWreckSalvageModule module = HCWreckSalvageModule.Get();
        HCWreckSalvageActionData data = HCWreckSalvageActionData.Cast(action_data);
        if (data && !data.Completed)
        {
            if (!module || !module.Continuing(data) || GetGame().GetTime() - data.StartedMs < 7500)
            {
                HCCraftRefusal.WreckAction(action_data, HCRefusal.SALVAGE);
                return;
            }
            module.Complete(data);
        }
    }

    override void OnEndServer(ActionData action_data)
    {
        HCWreckSalvageModule module = HCWreckSalvageModule.Get();
        if (module) module.End(HCWreckSalvageActionData.Cast(action_data));
        super.OnEndServer(action_data);
    }
}

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionSalvageWreck);
    }
}

modded class Wrench
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionSalvageWreck);
    }
}

modded class Screwdriver
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionSalvageWreck);
    }
}

modded class Pliers
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionSalvageWreck);
    }
}
