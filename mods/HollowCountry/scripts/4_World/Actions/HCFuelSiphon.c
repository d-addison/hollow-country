// #53 production fuel siphon: native ActionFillFuel in reverse.
// Source is only a live CarScript tank; boats and static wrecks are refused.
// The held vessel is the equipment: an open,
// non-ruined liquid container that accepts gasoline and has free space.
// Server steps read the tank, Leak, read it again and credit only the
// observed loss (HCFuelTransferPolicy.SiphonCreditMl). Interruption flushes
// the pending partial step exactly as CAContinuousFillFuel.Cancel does.
// Offline tests prove neither compilation nor native behavior. Qualification
// remains false. Existing experimental admission is on unless the operator
// creates fuel_siphon.disable; the marker is probed once per server process.
// HC-3 native evidence (snapshot paths relative to scripts-1.30.164289):
// 3_Game/Vehicles/Car.c:355,363,366 tank capacity/fraction/Leak in liters;
// 3_Game/Vehicles/Transport.c:462,467,472 fuel selection/reach/refill point;
// 4_World/Static/Liquid.c:160,235 fill/readiness; ItemBase.c:3439,3490 quantities in ml;
// 4_World/Classes/UserActionsComponent/ActionComponents/CAContinuousFillFuel.c:22,50,86,121
// Setup/Execute/Cancel/ml-to-liter conversion; Actions/ActionContinuousBase.c:110 cancellation;
// 4_World/Classes/UserActionsComponent/ActionComponents/CAContinuousBase.c:8 completion hook.
// 4_World/Classes/UserActionsComponent/ActionBase.c:240,1409 action data/end lifecycle.
// 3_Game/Entities/EntityAI.c:4019 and 4_World/Entities/Vehicles/CarScript.c:385 throughput.
// 4_World/Entities/Vehicles/CarScript.c:2221 IsMoving (not a stationary check).
// 4_World/Entities/ManBase/PlayerBase.c:2131 native use of GetItemInHands.
// 4_World/Classes/UserActionsComponent/ActionTargets.c:142,147,159 object/parent/component.
// 1_Core/proto/EnSystem.c:397 FileExist; 1_Core/proto/EnDebug.c:96,108 Print/PrintFormat.
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

    // A normal end is distinct from failed eligibility. Only the current native
    // endpoints are read; invalid/NaN/negative quantities do not mean exhaustion.
    static bool Exhausted(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target || !action_data.m_MainItem)
            return false;
        CarScript car = CarScript.Cast(action_data.m_Target.GetObject());
        if (!car)
            return false;
        ItemBase vessel = action_data.m_MainItem;
        float quantity = vessel.GetQuantity();
        float maximum = vessel.GetQuantityMax();
        return TankLiters(car) == 0 || (HCFuelTransferPolicy.FiniteNonNegative(quantity) && maximum > 0 && maximum <= 1048576.0 && quantity == maximum);
    }

    static bool Allowed(PlayerBase player, ActionTarget target, ItemBase item, HCRefusalResult refusal = null)
    {
        // Parameters are weak refs (boot 047 native compile error); a strong
        // local owns the fallback result for the whole call.
        HCRefusalResult ownedRefusal = null;
        if (!refusal)
        {
            ownedRefusal = new HCRefusalResult;
            refusal = ownedRefusal;
        }
        refusal.Refuse(HCRefusal.SIPHON);
        if (GetGame() && GetGame().IsServer() && !ServerEnabled())
            return refusal.Refuse(HCRefusal.SIPHON_OFF);
        if (!player || !target || !item || player.IsInVehicle())
            return false;
        if (target.GetParent() || target.GetComponentIndex() < 0)
            return false;
        if (player.IsRestrained())
            return refusal.Refuse(HCRefusal.SIPHON_RESTRAINED);
        if (player.GetItemInHands() != item)
            return false;
        CarScript car = CarScript.Cast(target.GetObject());
        if (!car || car.IsDamageDestroyed())
            return false;
        if (car.EngineIsOn() || car.IsMoving())
            return refusal.Refuse(HCRefusal.SIPHON_MOVING);
        float capacity = car.GetFluidCapacity(CarFluid.FUEL);
        float fraction = car.GetFluidFraction(CarFluid.FUEL);
        if (!HCFuelTransferPolicy.SiphonDonorValid(capacity, fraction))
            return false;
        if (!item.IsLiquidContainer() || item.IsDamageDestroyed())
            return false;
        if (!item.IsOpen())
            return refusal.Refuse(HCRefusal.SIPHON_CLOSED);
        if (item.GetQuantity() >= item.GetQuantityMax())
            return refusal.Refuse(HCRefusal.SIPHON_FULL);
        if (item.GetQuantity() > 0 && item.GetLiquidType() != LIQUID_GASOLINE)
            return refusal.Refuse(HCRefusal.SIPHON_LIQUID);
        if (!Liquid.CanFillContainer(item, LIQUID_GASOLINE))
            return refusal.Refuse(HCRefusal.SIPHON_LIQUID);
        float reach = car.GetActionDistanceFuel();
        if (vector.DistanceSq(car.GetRefillPointPosWS(), player.GetPosition()) >= reach * reach)
            return refusal.Refuse(HCRefusal.SIPHON_RANGE);
        TStringArray selections = new TStringArray();
        car.GetActionComponentNameList(target.GetComponentIndex(), selections);
        int count = selections.Count();
        if (count > 32)
            return false;
        bool fuelSelection = false;
        for (int i = 0; i < count; i++)
        {
            if (selections.Get(i) == car.GetActionCompNameFuel())
                fuelSelection = true;
        }
        if (!fuelSelection)
            return false;
        // All donor, vessel, custody and selection checks precede physics work.
        return HCActionSiphonFuel.ProductionRecipientReady(player, target, item, refusal);
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
        {
            HCRefuse(action_data);
            return;
        }
        CarScript car = CarScript.Cast(action_data.m_Target.GetObject());
        ItemBase vessel = action_data.m_MainItem;
        if (!car || !vessel)
        {
            HCRefuse(action_data);
            return;
        }
        m_AdjustedRate = m_RatePerSecond * Math.Min(vessel.GetLiquidThroughputCoef(), car.GetLiquidThroughputCoef());
        m_SessionMl = HCFuelTransferPolicy.SiphonSessionMl(HCFuelSiphon.TankLiters(car), vessel.GetQuantity(), vessel.GetQuantityMax());
        if (GetGame().IsServer() && !HCActionSiphonFuel.ProductionBegin(action_data))
            HCRefuse(action_data);
    }

    override int Execute(ActionData action_data)
    {
        if (!action_data.m_Player)
        {
            HCRefuse(action_data);
            return UA_ERROR;
        }
        if (m_Stopped)
            return UA_FINISHED;
        if (m_SessionMl <= 0 || m_AdjustedRate <= 0)
        {
            HCRefuse(action_data);
            return UA_FINISHED;
        }
        if (GetGame().IsServer() && (!HCFuelSiphon.ServerEnabled() || !HCActionSiphonFuel.ProductionOwns(action_data)))
        {
            HCRefuse(action_data);
            return UA_FINISHED;
        }
        if (HCFinishIfExhausted(action_data))
            return UA_FINISHED;
        if (m_MovedMl + m_PendingMl >= m_SessionMl)
        {
            CalcAndSetQuantity(action_data);
            HCComplete(action_data);
            return UA_FINISHED;
        }
        float delta = action_data.m_Player.GetDeltaT();
        if (!HCFuelTransferPolicy.FiniteNonNegative(delta) || !HCFuelTransferPolicy.FiniteNonNegative(m_AdjustedRate))
        {
            HCRefuse(action_data);
            return UA_ERROR;
        }
        if (delta > m_StepSeconds)
            delta = m_StepSeconds;
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
        {
            HCRefuse(action_data);
            return UA_ERROR;
        }
        CalcAndSetQuantity(action_data);
        HCStop(action_data);
        return UA_CANCEL;
    }

    void HCRefuse(ActionData action_data, HCRefusalResult refusal = null)
    {
        // Parameters are weak refs (boot 047 native compile error); a strong
        // local owns the fallback result for the whole call.
        HCRefusalResult ownedRefusal = null;
        if (!refusal)
        {
            ownedRefusal = new HCRefusalResult;
            refusal = ownedRefusal;
            if (!HCFuelSiphon.ServerEnabled())
                refusal.Refuse(HCRefusal.SIPHON_OFF);
            else
                HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, action_data.m_MainItem, refusal);
        }
        if (refusal.Reason == "")
            refusal.Refuse(HCRefusal.SIPHON);
        HCStop(action_data);
        HCRefusalReport.ActionRefusalMessage(action_data, refusal.Reason, HCRefusal.SiphonMessage(refusal.Reason));
    }

    void HCComplete(ActionData action_data)
    {
        if (m_Stopped)
            return;
        HCStop(action_data);
        if (GetGame().IsServer())
            HCActionSiphonFuel.ProductionComplete(action_data);
        OnCompletePogress(action_data);
    }

    bool HCFinishIfExhausted(ActionData action_data)
    {
        if (m_Stopped)
            return false;
        if ((m_SessionMl > 0 && m_SessionMl - m_MovedMl <= 1.0) || HCFuelSiphon.Exhausted(action_data))
        {
            HCComplete(action_data);
            return true;
        }
        return false;
    }

    void HCStop(ActionData action_data)
    {
        m_Stopped = true;
        m_PendingMl = 0;
        if (GetGame() && GetGame().IsServer())
            HCActionSiphonFuel.ProductionEnd(action_data);
    }

    override float GetProgress()
    {
        if (m_SessionMl <= 0)
            return 1;
        return -(m_MovedMl / m_SessionMl);
    }

    void CalcAndSetQuantity(ActionData action_data)
    {
        if (m_Stopped)
            return;
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
        if (HCFinishIfExhausted(action_data))
            return;
        // Revalidate on every debit, including the Cancel flush after an
        // interruption: an invalid state drops the pending step, never debits.
        ItemBase vessel = action_data.m_MainItem;
        if (!HCFuelSiphon.ServerEnabled() || !HCActionSiphonFuel.ProductionOwns(action_data) || !HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, vessel))
        {
            // The shared refusal check obtains the live cause on this failure path.
            HCRefuse(action_data);
            return;
        }
        CarScript car = CarScript.Cast(action_data.m_Target.GetObject());
        float capacity = car.GetFluidCapacity(CarFluid.FUEL);
        float beforeLiters = HCFuelSiphon.TankLiters(car);
        float vesselBeforeMl = vessel.GetQuantity();
        float stepMl = HCFuelTransferPolicy.SiphonStepMl(beforeLiters, vesselBeforeMl, vessel.GetQuantityMax(), requestMl, remainingMl);
        if (stepMl <= 0)
        {
            HCRefuse(action_data);
            return;
        }
        // Consume the step BEFORE native writes. A VM abort or reentrant cancel
        // leaves this component stopped; never replay/refund an uncertain write.
        m_Stopped = true;
        car.Leak(CarFluid.FUEL, stepMl * 0.001);
        if (!car || !vessel || !HCActionSiphonFuel.ProductionOwns(action_data) || !HCFuelSiphon.ServerEnabled())
        {
            Print("[HollowCountry] Fuel siphon endpoint/admission/lease lost after debit; no credit/replay/refund; runtime=PENDING");
            HCRefuse(action_data);
            return;
        }
        float afterLiters = HCFuelSiphon.TankLiters(car);
        HCRefusalResult refusal = new HCRefusalResult;
        if (car.GetFluidCapacity(CarFluid.FUEL) != capacity || vessel.GetQuantity() != vesselBeforeMl || !HCActionSiphonFuel.ProductionRecipientReady(action_data.m_Player, action_data.m_Target, vessel, refusal))
        {
            Print("[HollowCountry] Fuel siphon recipient changed after debit; no credit/replay/refund; runtime=PENDING");
            HCRefuse(action_data, refusal);
            return;
        }
        float creditMl = HCFuelTransferPolicy.SiphonCreditMl(stepMl, beforeLiters, afterLiters, vesselBeforeMl, vessel.GetQuantityMax());
        if (creditMl <= 0)
        {
            if (afterLiters < beforeLiters && afterLiters == 0)
            {
                m_Stopped = false;
                HCComplete(action_data);
                return;
            }
            Print("[HollowCountry] Fuel siphon debit readback refused; no credit/replay/refund; runtime=PENDING");
            HCRefuse(action_data);
            return;
        }
        Liquid.FillContainer(vessel, LIQUID_GASOLINE, creditMl);
        if (!car || !vessel || !HCActionSiphonFuel.ProductionOwns(action_data))
        {
            Print("[HollowCountry] Fuel siphon endpoint/lease lost after credit; no replay/refund; runtime=PENDING");
            HCRefuse(action_data);
            return;
        }
        if (car.GetFluidCapacity(CarFluid.FUEL) != capacity || HCFuelSiphon.TankLiters(car) != afterLiters || vessel.GetLiquidType() != LIQUID_GASOLINE || !HCFuelTransferPolicy.SiphonReceiptOk(creditMl, vesselBeforeMl, vessel.GetQuantity()))
        {
            // Ambiguous native receipt: no retry or refund.
            HCStop(action_data);
            HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON_RECEIPT, "Fuel siphon receipt mismatch; stopped without retry or refund.");
            return;
        }
        m_MovedMl += creditMl;
        m_Stopped = false;
        HCFinishIfExhausted(action_data);
    }
}

class HCActionSiphonFuelFromCarCB : ActionContinuousBaseCB
{

    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousHCSiphonFuel(UAQuantityConsumed.FUEL, HCFuelSiphonConfig.Get().RepeatSeconds);
    }
}

class HCActionSiphonFuelFromCar extends ActionContinuousBase
{
    override ActionData CreateActionData()
    {
        return new HCSiphonDiagnosticData;
    }

    override void OnEndServer(ActionData action_data)
    {
        HCActionSiphonFuel.ProductionEnd(action_data);
        super.OnEndServer(action_data);
    }

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
        HCRefusalResult refusal = new HCRefusalResult;
        refusal.Refuse(HCRefusal.SIPHON);
        bool allowed = HCFuelSiphon.Allowed(player, target, item, refusal);
        if (!GetGame().IsServer()) return allowed;
        if (allowed && HCFuelSiphon.ServerEnabled()) return true;
        HCRefusalReport.TargetRefusalMessage(player, target, item, refusal.Reason, HCRefusal.SiphonMessage(refusal.Reason));
        return false;
    }

    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        if (!action_data) return;
        HCRefusalResult refusal = new HCRefusalResult;
        refusal.Refuse(HCRefusal.SIPHON);
        if (!HCFuelSiphon.Allowed(action_data.m_Player, action_data.m_Target, action_data.m_MainItem, refusal) || !HCFuelSiphon.ServerEnabled())
        {
            if (refusal.Reason == "")
                refusal.Refuse(HCRefusal.SIPHON_OFF);
            HCRefusalReport.ActionRefusalMessage(action_data, refusal.Reason, HCRefusal.SiphonMessage(refusal.Reason));
        }
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        if (!action_data) return false;
        HCSiphonDiagnosticData data = HCSiphonDiagnosticData.Cast(action_data);
        if (data && data.ProductionStarted && (data.ProductionFinished || (data.LockHeld && HCFuelSiphon.Exhausted(action_data))))
        {
            HCActionSiphonFuel.ProductionComplete(action_data);
            return false;
        }
        if (!ActionCondition(action_data.m_Player, action_data.m_Target, action_data.m_MainItem))
            return false;
        if (!GetGame().IsServer() || HCActionSiphonFuel.ProductionOwns(action_data))
            return true;
        HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON, HCRefusal.SiphonMessage(HCRefusal.SIPHON));
        return false;
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
