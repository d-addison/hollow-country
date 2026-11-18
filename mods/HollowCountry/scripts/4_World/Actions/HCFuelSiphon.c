// #53 production fuel siphon: native ActionFillFuel in reverse.
// Source is only a live car's real tank (Transport); static wrecks are not
// Transport and never offer fuel. The held vessel is the equipment: an open,
// non-ruined liquid container that accepts gasoline and has free space.
// Server steps read the tank, Leak, read it again and credit only the
// observed loss (HCFuelTransferPolicy.SiphonCreditMl). Interruption flushes
// the pending partial step exactly as CAContinuousFillFuel.Cancel does.
// Offline tests prove neither compilation nor native behavior. Execution is
// closed by HCFuelSiphonQualification until local-server acceptance.
// Fuel admission defaults closed until local-server acceptance is recorded;
// flipping Qualified() is a source change, never an operator setting.
// A server operator may create the marker file below for a local acceptance
// run only; it is probed once per server process and logged as EXPERIMENTAL.
class HCFuelSiphonQualification
{
    protected static bool s_Checked;
    protected static bool s_OptIn;

    // Evidence required: accepted local-server transfer, interruption and restart run.
    static bool Qualified()
    {
        return false;
    }

    static bool LocalAcceptanceOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/fuel_siphon.disable");
    }

    static bool Admitted()
    {
        if (Qualified())
            return true;
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
                Print("[HollowCountry] V1 admission feature=FuelSiphon preference=on gate=fuel_siphon qualified=0 result=admitted unverified: fuel_siphon has no recorded native verdict; opt out with acceptance/fuel_siphon.disable; EXPERIMENTAL; runtime acceptance PENDING");
            else
                Print("[HollowCountry] V1 admission feature=FuelSiphon preference=off gate=fuel_siphon qualified=0 result=off: operator opt-out acceptance/fuel_siphon.disable; not admitted; runtime acceptance PENDING");
        }
        return s_OptIn;
    }
}

class HCFuelSiphon
{
    static float TankLiters(CarScript car)
    {
        if (!car)
            return 0;
        return car.GetFluidCapacity(CarFluid.FUEL) * car.GetFluidFraction(CarFluid.FUEL);
    }

    // Server admission: core started, crafting definitions validated and the
    // crafting preference on (HCCraftingGate), AND explicit fuel admission.
    static bool ServerEnabled()
    {
        if (!GetGame() || !GetGame().IsServer())
            return false;
        return HCCraftingGate.CanPreviewOrCraft() && HCFuelSiphonQualification.Admitted();
    }

    static bool Allowed(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (!player || !target || !item || player.IsInVehicle())
            return false;
        if (player.GetItemInHands() != item)
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
        // Revalidate on every debit, including the Cancel flush after an
        // interruption: an invalid state drops the pending step, never debits.
        ItemBase vessel = action_data.m_MainItem;
        if (!HCFuelSiphon.ServerEnabled() || !HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, vessel))
        {
            m_Stopped = true;
            return;
        }
        CarScript car = CarScript.Cast(action_data.m_Target.GetObject());
        float beforeLiters = HCFuelSiphon.TankLiters(car);
        float vesselBeforeMl = vessel.GetQuantity();
        float stepMl = HCFuelTransferPolicy.SiphonStepMl(beforeLiters, vesselBeforeMl, vessel.GetQuantityMax(), requestMl, remainingMl);
        if (stepMl <= 0)
        {
            m_Stopped = true;
            return;
        }
        car.Leak(CarFluid.FUEL, stepMl * 0.001);
        float afterLiters = HCFuelSiphon.TankLiters(car);
        float creditMl = HCFuelTransferPolicy.SiphonCreditMl(stepMl, beforeLiters, afterLiters, vesselBeforeMl, vessel.GetQuantityMax());
        if (creditMl <= 0)
        {
            m_Stopped = true;
            return;
        }
        Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl);
        if (!HCFuelTransferPolicy.SiphonReceiptOk(creditMl, vesselBeforeMl, vessel.GetQuantity()))
        {
            Print("[HollowCountry] Fuel siphon receipt mismatch; stopped without retry or refund");
            m_Stopped = true;
            return;
        }
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
        AddAction(HCActionSiphonFuelFromCar);
    }
}
