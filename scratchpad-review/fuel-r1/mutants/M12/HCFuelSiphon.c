// #53 production fuel siphon: native ActionFillFuel in reverse.
// Source is only a live car's real tank (Transport); static wrecks are not
// Transport and never offer fuel. The held vessel is the equipment: an open,
// non-ruined liquid container that accepts gasoline and has free space.
// Server steps read the tank, Leak, read it again and credit only the
// observed loss (HCFuelTransferPolicy.SiphonCreditMl). Interruption flushes
// the pending partial step exactly as CAContinuousFillFuel.Cancel does.
// Offline tests prove neither compilation nor native behavior; DayZDiag and
// local-server acceptance remain pending before the README calls it shipped.
class HCFuelSiphon
{
    static float TankLiters(CarScript car)
    {
        if (!car)
            return 0;
        return car.GetFluidCapacity(CarFluid.FUEL) * car.GetFluidFraction(CarFluid.FUEL);
    }

    static bool ServerEnabled()
    {
        if (!GetGame() || !GetGame().IsServer())
            return false;
        HCServer server = HCServer.Get();
        if (!server || !server.IsStarted())
            return false;
        HCSettings settings = server.GetSettings();
        return settings && settings.EnableCrafting;
    }

    static bool Allowed(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!player || !target || !item || player.IsInVehicle())
            return false;
        CarScript car = CarScript.Cast(target.GetObject());
        if (!car || car.IsDamageDestroyed() || car.EngineIsOn() || car.IsMoving())
            return false;
        if (car.GetFluidFraction(CarFluid.FUEL) <= 0)
            return false;
        if (!item.IsLiquidContainer() || item.IsDamageDestroyed())
            return false;
        if (item.GetQuantity() >= item.GetQuantityMax())
            return false;
        if (item.GetQuantity() > 0 && item.GetLiquidType() != LIQUID_GASOLINE)
            return false;
        if (!Liquid.CanFillContainer(item, LIQUID_GASOLINE))
            return false;
        float reach = car.GetActionDistanceFuel();
        if (vector.DistanceSq(car.GetRefillPointPosWS(), player.GetPosition()) >= reach * reach)
            return false;
        TStringArray selections = new TStringArray();
        car.GetActionComponentNameList(target.GetComponentIndex(), selections);
        int count = selections.Count();
        if (count > 32)
            count = 32;
        for (int i = 0; i < count; i++)
        {
            if (selections.Get(i) == car.GetActionCompNameFuel())
                return true;
        }
        return false;
    }
}

class CAContinuousHCSiphonFuel extends CAContinuousBase
{
    protected float m_RatePerSecond;
    protected float m_AdjustedRate;
    protected float m_StepSeconds;
    protected float m_Elapsed;
    protected float m_PendingMl;
    protected float m_SessionMl;
    protected float m_MovedMl;
    protected bool m_Stopped;

    void CAContinuousHCSiphonFuel(float rate_per_second, float step_seconds)
    {
        m_RatePerSecond = rate_per_second;
        m_StepSeconds = step_seconds;
    }

    override void Setup(ActionData action_data)
    {
        m_Elapsed = 0;
        m_PendingMl = 0;
        m_MovedMl = 0;
        m_SessionMl = 0;
        m_AdjustedRate = 0;
        m_Stopped = false;
        if (!action_data.m_Target)
            return;
        CarScript car = CarScript.Cast(action_data.m_Target.GetObject());
        ItemBase vessel = action_data.m_MainItem;
        if (!car || !vessel)
            return;
        m_AdjustedRate = m_RatePerSecond * Math.Min(vessel.GetLiquidThroughputCoef(), car.GetLiquidThroughputCoef());
        m_SessionMl = HCFuelTransferPolicy.SiphonSessionMl(HCFuelSiphon.TankLiters(car), vessel.GetQuantity(), vessel.GetQuantityMax());
    }

    override int Execute(ActionData action_data)
    {
        if (!action_data.m_Player)
            return UA_ERROR;
        if (m_Stopped || m_SessionMl <= 0 || m_AdjustedRate <= 0)
            return UA_FINISHED;
        if (m_MovedMl + m_PendingMl >= m_SessionMl)
        {
            CalcAndSetQuantity(action_data);
            OnCompletePogress(action_data);
            return UA_FINISHED;
        }
        float delta = action_data.m_Player.GetDeltaT();
        m_PendingMl += m_AdjustedRate * delta;
        m_Elapsed += delta;
        if (m_Elapsed >= m_StepSeconds)
        {
            CalcAndSetQuantity(action_data);
            m_Elapsed = 0;
        }
        return UA_PROCESSING;
    }

    override int Cancel(ActionData action_data)
    {
        if (!action_data.m_Player)
            return UA_ERROR;
        CalcAndSetQuantity(action_data);
        return UA_CANCEL;
    }

    override float GetProgress()
    {
        if (m_SessionMl <= 0)
            return 1;
        return -(m_MovedMl / m_SessionMl);
    }

    void CalcAndSetQuantity(ActionData action_data)
    {
        float requestMl = m_PendingMl;
        m_PendingMl = 0;
        float remainingMl = m_SessionMl - m_MovedMl;
        if (requestMl <= 0 || remainingMl <= 0)
            return;
        if (!GetGame().IsServer())
        {
            if (requestMl > remainingMl)
                requestMl = remainingMl;
            m_MovedMl += requestMl;
            return;
        }
        CarScript car;
        if (action_data.m_Target)
            car = CarScript.Cast(action_data.m_Target.GetObject());
        ItemBase vessel = action_data.m_MainItem;
        if (!car || !vessel || !Liquid.CanFillContainer(vessel, LIQUID_GASOLINE))
        {
            m_Stopped = true;
            return;
        }
        float beforeLiters = HCFuelSiphon.TankLiters(car);
        float stepMl = HCFuelTransferPolicy.SiphonStepMl(beforeLiters, vessel.GetQuantity(), vessel.GetQuantityMax(), requestMl, remainingMl);
        if (stepMl <= 0)
        {
            m_Stopped = true;
            return;
        }
        car.Leak(CarFluid.FUEL, stepMl * 0.001);
        float afterLiters = HCFuelSiphon.TankLiters(car);
        float creditMl = HCFuelTransferPolicy.SiphonCreditMl(stepMl, beforeLiters, afterLiters);
        if (creditMl <= 0)
        {
            m_Stopped = true;
            return;
        }
        Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl);
        m_MovedMl += creditMl;
    }
}

class HCActionSiphonFuelFromCarCB : ActionContinuousBaseCB
{
    private const float TIME_TO_REPEAT = 0.5;

    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousHCSiphonFuel(UAQuantityConsumed.FUEL, TIME_TO_REPEAT);
    }
}

class HCActionSiphonFuelFromCar extends ActionContinuousBase
{
    void HCActionSiphonFuelFromCar()
    {
        m_CallbackClass = HCActionSiphonFuelFromCarCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_FILLBOTTLEPOND;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_FullBody = true;
        m_SpecialtyWeight = UASoftSkillsWeight.PRECISE_LOW;
        m_LockTargetOnUse = false;
        m_Text = "Siphon fuel";
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTNone;
    }

    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!HCFuelSiphon.Allowed(player, target, item))
            return false;
        if (!GetGame().IsServer())
            return true;
        return HCFuelSiphon.ServerEnabled();
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, action_data.m_MainItem))
            return false;
        if (!GetGame().IsServer())
            return true;
        return HCFuelSiphon.ServerEnabled();
    }
}

modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionSiphonFuelFromCar);
    }
}

modded class Bottle_Base
{
    override void SetActions()
    {
        super.SetActions();
        AddAction(ActionFillFuel);
    }
}
