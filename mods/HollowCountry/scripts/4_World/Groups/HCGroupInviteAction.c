// Native 1.30.164289: 4_World/Classes/UserActionsComponent/
// Actions/ActionInteractBase.c:41-60 interact command/conditions;
// AnimatedActionBase.c:179,198-203 server execution hook;
// TargetConditionsComponents/CCTMan.c:6-23 living man/reach condition;
// ActionConstructor.c:27 RegisterActions; ActionTargets.c:142 GetObject;
// Entities/ManBase/PlayerBase.c:1695 SetActions (AddAction calls within it).
// 3_Game/Entities/Object.c:287,517 GetPosition/IsAlive;
// 4_World/Entities/ManBase/PlayerBase.c:6926 MessageStatus.
// Native action supplies the server target; server resolves its identity and
// rechecks life/reach plus every existing INVITE rule in the shared transaction.
class HCGroupInviteAction : ActionInteractBase
{
    void HCGroupInviteAction()
    {
        m_Text = "Invite to group";
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTMan(3.0);
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!player || !player.IsAlive() || !target) return false;
        PlayerBase other = PlayerBase.Cast(target.GetObject());
        if (!other || other == player || !other.IsAlive()) return false;
        vector reach = other.GetPosition() - player.GetPosition();
        if (reach[0] * reach[0] + reach[1] * reach[1] + reach[2] * reach[2] > 9.0) return false;
        if (GetGame().IsServer()) return true;
        return HCGroupInviteBridge.Client && HCGroupInviteBridge.Client.HCAllowsInvite(other);
    }

    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data || !action_data.m_Player) return;
        PlayerBase target;
        if (action_data.m_Target) target = PlayerBase.Cast(action_data.m_Target.GetObject());
        int result = HCGroupCode.DISABLED;
        HCGroupService service = HCGroupService.Get();
        if (service) result = service.HCInviteNearby(action_data.m_Player, target);
        string message = "Group invitation not sent.";
        if (result == HCGroupCode.OK) message = "Group invitation sent. Your friend can accept from the group map.";
        else if (result == HCGroupCode.DENIED) message = "Group invitation not sent: only the owner or an officer can invite, within 3 m.";
        else if (result == HCGroupCode.LIMIT) message = "Group invitation not sent: the group or invite list is full.";
        else if (result == HCGroupCode.RATE) message = "Group invitation not sent: wait a moment and try again.";
        else if (result == HCGroupCode.CONFLICT) message = "Group invitation not sent: that player is already invited or in a group.";
        action_data.m_Player.MessageStatus(message);
    }
}

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCGroupInviteAction);
    }
}

modded class PlayerBase
{
    override void SetActions(out TInputActionMap InputActionMap)
    {
        super.SetActions(InputActionMap);
        AddAction(HCGroupInviteAction, InputActionMap);
    }
}
