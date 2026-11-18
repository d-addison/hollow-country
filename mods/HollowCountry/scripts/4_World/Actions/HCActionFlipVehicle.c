// #127. Native scripts-1.30.164289:
// 4_World/Classes/UserActionsComponent/ActionConstructor.c:27 RegisterActions;
// ActionBase.c:245 CreateConditionComponents, :436 ActionCondition;
// Actions/ActionContinuousBase.c:289 OnFinishProgressServer;
// ActionComponents/CAContinuousTime.c:9; Entities/Vehicles/CarScript.c:2313 SetActions.
// ActionTargets.c:142/147 GetObject/GetParent; ItemConditionComponents/CCINone.c:1;
// TargetConditionsComponents/CCTCursor.c:11; 3_Game/gameplay.c:636 GetGame;
// 3_Game/Global/Game.c:1120 IsServer; Entity casting: 1_Core/proto/EnScript.c:94.
// Player/target access uses ActionData and ActionTarget exactly as native actions.
// No tick or world enumeration here; server module rechecks people/vehicle before
// every impulse. UI shows a request, not a claim that recovery will succeed.
class HCActionFlipVehicleCB : ActionContinuousBaseCB
{
    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousTime(6);
    }
}
class HCActionFlipVehicle : ActionContinuousBase
{
    void HCActionFlipVehicle()
    {
        m_CallbackClass = HCActionFlipVehicleCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_INTERACT;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_FullBody = true;
        m_Text = "Try to right vehicle (3 people or crowbar)";
    }
    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTCursor(3);
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        bool allowed = target && !target.GetParent();
        if (allowed) allowed = HCVehicleFlipModule.HCCandidate(player, CarScript.Cast(target.GetObject()));
        if (!GetGame().IsServer()) return allowed;
        if (allowed && HCVehicleFlipModule.Get()) return true;
        HCRefusalReport.TargetRefusalMessage(player, target, item, HCRefusal.FLIP, "Cannot right this vehicle now; check clearance, helpers or crowbar, and cooldown.");
        return false;
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        HCVehicleFlipModule module = HCVehicleFlipModule.Get();
        if (!action_data) { return; }
        if (!module || !action_data.m_Target || !module.HCQueue(action_data.m_Player, CarScript.Cast(action_data.m_Target.GetObject())))
        {
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.FLIP, "Cannot right this vehicle now; check clearance, helpers or crowbar, and cooldown.");
        }
    }
}
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionFlipVehicle);
    }
}
modded class CarScript
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(HCActionFlipVehicle);
    }
}
