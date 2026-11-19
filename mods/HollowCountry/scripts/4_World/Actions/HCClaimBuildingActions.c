// HC-17. Native evidence scripts-1.30.164289:
// 4_World/Classes/UserActionsComponent/ActionConstructor.c:27 RegisterActions;
// ActionBase.c:245/436/1290 condition setup/condition/IsInReach;
// Actions/ActionContinuousBase.c:289 OnFinishProgressServer;
// Actions/Continuous/ActionLockDoors.c:16-36 native stance/animation/components;
// ActionComponents/CAContinuousTime.c:9; TargetConditionsComponents/CCTCursor.c:11;
// ItemConditionComponents/CCINone.c:1; ActionTargets.c:142/147/159 object/parent/component;
// Entities/ManBase/PlayerBase.c:1695 SetActions(out TInputActionMap), :1705 AddAction;
// 3_Game/Entities/Building.c:28 GetDoorIndex; Global/Game.c:1120 IsServer.
// Entities/ManBase/PlayerBase.c:6911-6926 Message/MessageStatus routes server
// status text to the actor's client; conditions remain quiet per-frame previews.
// Server re-reads actual building/transform, current group and role at finish.
// UI preview does not assert ownership. Door locking remains native lockpick.
class HCClaimBuildingCB : ActionContinuousBaseCB
{
    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousTime(UATimeSpent.LOCK);
    }
}

class HCClaimBuildingAction : ActionContinuousBase
{
    void HCClaimBuildingAction()
    {
        m_CallbackClass = HCClaimBuildingCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_INTERACT;
        m_FullBody = true;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_Text = "Claim building for group";
    }
    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTCursor(UAMaxDistances.DEFAULT);
    }
    bool HCReleaseRequest() { return false; }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!HCBuildingClaim.HCActor(player) || !target || target.GetParent() || !IsInReach(player, target, UAMaxDistances.DEFAULT)) { return false; }
        Building building = Building.Cast(target.GetObject());
        if (!building || !HCBuildingClaim.HCDoor(building, building.GetDoorIndex(target.GetComponentIndex()))) { return false; }
        if (GetGame().IsServer())
        {
            HCBuildingClaim claims = HCBuildingClaim.HCGet();
            if (!claims) { return false; }
            HCGroupService groups = HCGroupService.Get();
            if (!groups) { return false; }
            int groupId = groups.HCClaimActorGroup(player, true);
            if (groupId < 1) { return false; }
            if (HCReleaseRequest()) { return claims.HCHoldsClaim(groupId, HCBuildingClaim.HCIdentity(building)); }
            return true;
        }
        return true;
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data) { Print("[HC Plan] HC-17 action=refused reason=missing_action_data runtime=PENDING"); return; }
        if (!ActionCondition(action_data.m_Player, action_data.m_Target, action_data.m_MainItem))
        {
            if (action_data.m_Player) { action_data.m_Player.MessageStatus("Building claim refused: you must manage your group and release only its claimed building, within door reach."); }
            else { Print("[HC Plan] HC-17 action=refused reason=missing_actor runtime=PENDING"); }
            return;
        }
        HCBuildingClaim claims = HCBuildingClaim.HCGet();
        if (!claims || !claims.HCRequest(action_data.m_Player, action_data.m_Target, HCReleaseRequest()))
        {
            action_data.m_Player.MessageStatus("Building claim refused: service unavailable, claim conflict, changed group access or persistence fault.");
        }
    }
}

class HCReleaseBuildingAction : HCClaimBuildingAction
{
    void HCReleaseBuildingAction() { m_Text = "Release group's building claim"; }
    override bool HCReleaseRequest() { return true; }
}

// New registrations only; existing action blocks stay untouched. Native player
// action admission avoids adding InteractActions to every building config.
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCClaimBuildingAction);
        actions.Insert(HCReleaseBuildingAction);
    }
}
modded class PlayerBase
{
    override void SetActions(out TInputActionMap InputActionMap)
    {
        super.SetActions(InputActionMap);
        AddAction(HCClaimBuildingAction, InputActionMap);
        AddAction(HCReleaseBuildingAction, InputActionMap);
    }
}
