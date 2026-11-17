class HCInteriorActionData : ActionData
{
    HCInteriorSite Site;
}

class HCActionSearchInteriorCB : ActionContinuousBaseCB
{
    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousTime(6.0);
    }
}

class HCActionSearchInterior : ActionContinuousBase
{
    void HCActionSearchInterior()
    {
        m_CallbackClass = HCActionSearchInteriorCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_INTERACT;
        m_FullBody = true;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
        m_Text = "Search storage";
    }

    override ActionData CreateActionData()
    {
        return new HCInteriorActionData;
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTCursor(1.8);
    }

    // Client-only feasibility preview: no server config or profile reads.
    // The registered action may be rejected by the authoritative server.
    static bool Preview(PlayerBase player, ActionTarget target)
    {
        if (!player || !player.IsAlive() || !target || target.GetComponentIndex() < 0) return false;
        Object object = target.GetObject();
        // Templates are server profile data, so any House cursor target previews; the server
        // decides (HCSearchHouses) and a refusal only logs. Baked-geometry targeting is CAP-09.
        if (!object || (!HCInteriorCatalog.SearchType(object.GetType()) && !House.Cast(object) && !House.Cast(target.GetParent()))) return false;
        return vector.DistanceSq(MiscGameplayFunctions.GetPlayerHeadPosition(player), target.GetCursorHitPos()) <= 3.24;
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (item) return false;
        if (!GetGame().IsServer()) return Preview(player, target);
        HCInteriorsModule module = HCInteriorsModule.Get();
        return module && module.CanStart(player, target);
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!GetGame().IsServer()) return Preview(action_data.m_Player, action_data.m_Target);
        HCInteriorsModule module = HCInteriorsModule.Get();
        return module && module.CanContinue(action_data);
    }

    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        HCInteriorsModule module = HCInteriorsModule.Get();
        if (module) module.BeginSearch(action_data);
    }

    override void OnFinishProgressServer(ActionData action_data)
    {
        int phaseBefore = HCSearchNoise.PhaseOf(action_data);
        HCInteriorsModule module = HCInteriorsModule.Get();
        if (module) module.CommitSearch(action_data);
        // One native AI noise only if this commit completed the search.
        HCSearchNoise.OnCommitted(action_data, phaseBefore);
    }

    override void OnEndServer(ActionData action_data)
    {
        HCInteriorsModule module = HCInteriorsModule.Get();
        if (module) module.EndSearch(action_data);
        super.OnEndServer(action_data);
    }
}

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionSearchInterior);
    }
}

modded class PlayerBase
{
    override void SetActions(out TInputActionMap InputActionMap)
    {
        super.SetActions(InputActionMap);
        AddAction(HCActionSearchInterior, InputActionMap);
    }
}
