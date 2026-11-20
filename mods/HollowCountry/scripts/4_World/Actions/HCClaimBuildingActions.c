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
        // #239: the client shows Claim only to a group owner or officer whose group holds no
        // claim, and Release only on the held building (server hint, HCBuildingClaimHint).
        // The server checks geometry only, so a stale hint ends with HCRequest's message at
        // completion instead of a ring that stops with no reason.
        if (!GetGame().IsServer()) { return HCBuildingClaimHint.Get().HCAllows(building, HCReleaseRequest()); }
        return true;
    }
    override void OnFinishProgressServer(ActionData action_data)
    {
        if (!action_data) { Print("[HC Plan] HC-17 action=refused reason=missing_action_data runtime=PENDING"); return; }
        if (!action_data.m_Player) { Print("[HC Plan] HC-17 action=refused reason=missing_actor runtime=PENDING"); return; }
        // Completion revalidates through HCRequest, so changed ACL/service state
        // keeps its specific reason instead of being hidden by a preview gate.
        string reason = "Claim service unavailable.";
        HCBuildingClaim claims = HCBuildingClaim.HCGet();
        if (claims) { reason = claims.HCRequest(action_data.m_Player, action_data.m_Target, HCReleaseRequest()); }
        if (reason == "")
        {
            reason = "Building claimed for your group.";
            if (HCReleaseRequest()) { reason = "Building claim released."; }
        }
        action_data.m_Player.MessageStatus(reason);
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
