// #53 explicit diagnostic only, unregistered and disabled by default.
// Installed 1.30.164289: Car.c:355-372 GetFluidCapacity/GetFluidFraction,
// void Leak/Fill; Liquid.c:160-169 FillContainer sets type then AddQuantity;
// CanFillContainer:235-275 checks live mask/fullness/mixing. Native
// CAContinuousFillFuel converts container ml to car liters with quantity*0.001.
// Separate writes have no joint crash transaction or debit attribution.
// No snapshot rollback/refund is safe; native/save/client qualification pending.
// Transport.c fuel selection/refill point; DayZPhysics.c:199 RaycastRV;
// MiscGameplayFunctions.c:778 head position; CAContinuousTime cancellation.
// Native035 metadata: 7389 classes; 32 Car config-family entries INCLUDING
// templates;22 liquid-mask entries ALL CT_STRING expressions, not eligibility.
// Live casts/masks inspect all families without pilot whitelist or wreck fuel.
// Script/config ancestry differ. Refill geometry/tools need full runtime audit.

class HCSiphonDiagnosticData : ActionData
{
    CarScript Donor;
    ItemBase Vessel;
    bool LockHeld;
    bool Sampled;
    bool TransferAttempted;
    bool TrustedDiagnosticActor;
    int StartedMs;
    float ObservedDonorLiters;
    float ObservedVesselMl;
    float PlannedMl;
    float RequestedDebitMl;
    float RequestedCreditMl;
    float ObservedDonorAfterLiters;
    float ObservedVesselAfterMl;
    string DiagnosticStatus = "not_started";
}

class HCSiphonDiagnosticLocks
{
    static const int MAX_SESSIONS = 96;
    static const int MAX_LEASE_MS = 10000;
    protected ref array<ref HCSiphonDiagnosticData> m_Sessions = new array<ref HCSiphonDiagnosticData>;

    static bool LeaseLive(int startedMs, int nowMs)
    {
        if (startedMs < 0 || nowMs < startedMs)
            return false;
        return nowMs - startedMs <= MAX_LEASE_MS;
    }

    void Purge(int nowMs)
    {
        for (int index = m_Sessions.Count() - 1; index >= 0; index--)
        {
            HCSiphonDiagnosticData data = m_Sessions[index];
            if (!data || !data.m_Player || !data.Donor || !data.Vessel || !LeaseLive(data.StartedMs, nowMs))
            {
                m_Sessions.Remove(index);
                if (data)
                    data.LockHeld = false;
            }
        }
    }

    bool Acquire(HCSiphonDiagnosticData data, int nowMs)
    {
        Purge(nowMs);
        if (!data || !data.m_Player || !data.Donor || !data.Vessel || !LeaseLive(nowMs, nowMs))
            return false;
        if (m_Sessions.Count() >= MAX_SESSIONS)
            return false;
        for (int index = m_Sessions.Count() - 1; index >= 0; index--)
        {
            HCSiphonDiagnosticData active = m_Sessions[index];
            if (active == data || active.m_Player == data.m_Player || active.Donor == data.Donor || active.Vessel == data.Vessel)
                return false;
        }
        m_Sessions.Insert(data);
        data.StartedMs = nowMs;
        data.LockHeld = true;
        return true;
    }

    bool Owns(HCSiphonDiagnosticData data, int nowMs)
    {
        if (!data || !data.LockHeld || !data.m_Player || !data.Donor || !data.Vessel)
            return false;
        return LeaseLive(data.StartedMs, nowMs) && m_Sessions.Find(data) >= 0;
    }

    void Release(HCSiphonDiagnosticData data)
    {
        int index = m_Sessions.Find(data);
        if (index >= 0)
            m_Sessions.Remove(index);
        if (data)
            data.LockHeld = false;
    }

    void Clear()
    {
        for (int index = m_Sessions.Count() - 1; index >= 0; index--)
        {
            HCSiphonDiagnosticData data = m_Sessions[index];
            if (data)
                data.LockHeld = false;
        }
        m_Sessions.Clear();
    }
}

class HCActionSiphonFuelCB : ActionContinuousBaseCB
{
    override void CreateActionComponent()
    {
        m_ActionData.m_ActionComponent = new CAContinuousTime(1.0);
    }
}

class HCActionSiphonFuel : ActionContinuousBase
{
    protected static bool s_DiagnosticEnabled = false;
    protected static bool s_TrustedTransferEnabled = false;
    protected static float s_RateMl;
    protected static float s_MaxStepSeconds;
    protected static float s_CapMl;
    protected static ref HCSiphonDiagnosticLocks s_Locks = new HCSiphonDiagnosticLocks;

    void HCActionSiphonFuel()
    {
        m_CallbackClass = HCActionSiphonFuelCB;
        m_CommandUID = DayZPlayerConstants.CMD_ACTIONFB_INTERACT;
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        m_FullBody = true;
        m_Text = "Inspect siphon proposal (diagnostic)";
    }

    override ActionData CreateActionData()
    {
        return new HCSiphonDiagnosticData;
    }

    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINonRuined;
        m_ConditionTarget = new CCTNone;
    }

    // Hard experiment bounds; not measured gameplay rates or tool policy.
    static bool DiagnosticLimits(float rateMl, float maxStepSeconds, float capMl)
    {
        if (!HCFuelTransferPolicy.FiniteNonNegative(rateMl) || !HCFuelTransferPolicy.FiniteNonNegative(maxStepSeconds) || !HCFuelTransferPolicy.FiniteNonNegative(capMl))
            return false;
        return rateMl > 0 && rateMl <= 10000 && maxStepSeconds > 0 && maxStepSeconds <= 1 && capMl > 0 && capMl <= 1000;
    }

    // Trusted transfer is a ONE-SHOT owned-fixture permit, consumed BEFORE the
    // debit so an aborted callback cannot leave a globally armed write path.
    static bool ConfigureDiagnostic(bool enabled, float rateMl, float maxStepSeconds, float capMl, bool trustedTransfer = false)
    {
        if (!GetGame() || !GetGame().IsServer())
            return false;
        s_DiagnosticEnabled = false;
        s_TrustedTransferEnabled = false;
        s_Locks.Clear();
        if (enabled && !DiagnosticLimits(rateMl, maxStepSeconds, capMl))
            return false;
        s_RateMl = rateMl;
        s_MaxStepSeconds = maxStepSeconds;
        s_CapMl = capMl;
        s_DiagnosticEnabled = enabled;
        s_TrustedTransferEnabled = enabled && trustedTransfer;
        return true;
    }

    static bool FiniteVector(vector point)
    {
        return point[0] >= -float.MAX && point[0] <= float.MAX && point[1] >= -float.MAX && point[1] <= float.MAX && point[2] >= -float.MAX && point[2] <= float.MAX;
    }

    protected static bool ClearRay(PlayerBase player, CarScript donor, vector origin, vector endpoint, int geometry)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(origin, endpoint, contact, normal, component, hits, null, player, true, false, geometry);
        if (!hit)
            return true;
        if (hits.Count() != 1 || hits[0] != donor || !FiniteVector(contact))
            return false;
        return vector.DistanceSq(contact, endpoint) <= 0.25;
    }

    protected static bool ReachAndVisible(PlayerBase player, CarScript donor, ActionTarget target)
    {
        vector endpoint = donor.GetRefillPointPosWS();
        vector origin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        float reach = donor.GetActionDistanceFuel();
        if (!FiniteVector(endpoint) || !FiniteVector(origin) || !HCFuelTransferPolicy.FiniteNonNegative(reach) || reach <= 0)
            return false;
        if (reach > 2.0)
            reach = 2.0;
        if (!(vector.DistanceSq(player.GetPosition(), endpoint) <= reach * reach && vector.DistanceSq(origin, endpoint) <= 4.0))
            return false;
        return ClearRay(player, donor, origin, endpoint, ObjIntersectView) && ClearRay(player, donor, origin, endpoint, ObjIntersectFire);
    }

    static bool ValidateLive(PlayerBase player, ActionTarget target, ItemBase vessel)
    {
        if (!GetGame() || !GetGame().IsServer() || !s_DiagnosticEnabled)
            return false;
        if (!player || !player.IsAlive() || player.IsUnconscious() || player.IsRestrained() || player.IsInVehicle())
            return false;
        if (!player.GetIdentity() && !s_TrustedTransferEnabled)
            return false;
        if (!target || target.GetParent() || target.GetComponentIndex() < 0 || !vessel || player.GetItemInHands() != vessel)
            return false;
        CarScript donor = CarScript.Cast(target.GetObject());
        if (!donor || donor.IsDamageDestroyed() || donor.EngineIsOn())
            return false;
        float speed = donor.GetSpeedometerAbsolute();
        if (!HCFuelTransferPolicy.FiniteNonNegative(speed) || speed != 0)
            return false;
        if (vessel.IsDamageDestroyed() || !vessel.IsOpen() || !vessel.HasQuantity() || !vessel.IsLiquidContainer())
            return false;
        float quantity = vessel.GetQuantity();
        float maximum = vessel.GetQuantityMax();
        float capacity = donor.GetFluidCapacity(CarFluid.FUEL);
        float fraction = donor.GetFluidFraction(CarFluid.FUEL);
        if (!HCFuelTransferPolicy.FiniteNonNegative(quantity) || !HCFuelTransferPolicy.FiniteNonNegative(maximum) || !(quantity < maximum))
            return false;
        if (!HCFuelTransferPolicy.FiniteNonNegative(capacity) || !HCFuelTransferPolicy.FiniteNonNegative(fraction) || !(capacity > 0 && fraction > 0 && fraction <= 1))
            return false;
        if ((quantity > 0 && vessel.GetLiquidType() != LIQUID_GASOLINE) || !Liquid.CanFillContainer(vessel, LIQUID_GASOLINE))
            return false;
        array<string> selections = new array<string>;
        donor.GetActionComponentNameList(target.GetComponentIndex(), selections);
        if (selections.Count() > 64)
            return false;
        foreach (string selection : selections)
        {
            if (selection == donor.GetActionCompNameFuel())
                return ReachAndVisible(player, donor, target);
        }
        return false;
    }

    // No client offer/RPC or normal registration; explicit server probe only.
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        if (ValidateLive(player, target, item)) return true;
        HCRefusalReport.TargetRefusalMessage(player, target, item, HCRefusal.SIPHON_DIAGNOSTIC, "Siphon diagnostic refused; the server gate or live target is unavailable.");
        return false;
    }

    override bool ActionConditionContinue(ActionData action_data)
    {
        HCSiphonDiagnosticData data = HCSiphonDiagnosticData.Cast(action_data);
        if (!GetGame() || !GetGame().IsServer() || !s_DiagnosticEnabled || !data || data.Sampled)
            return false;
        if (!s_Locks.Owns(data, GetGame().GetTime()) || !data.m_Target || data.m_Target.GetObject() != data.Donor || data.m_MainItem != data.Vessel)
            return false;
        return ValidateLive(data.m_Player, data.m_Target, data.Vessel);
    }

    override void OnStartServer(ActionData action_data)
    {
        super.OnStartServer(action_data);
        HCSiphonDiagnosticData data = HCSiphonDiagnosticData.Cast(action_data);
        if (data && !data.Sampled && !data.LockHeld)
        {
            if (!ValidateLive(data.m_Player, data.m_Target, data.m_MainItem))
            {
                HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON_DIAGNOSTIC, "Siphon diagnostic refused; the server gate or live target is unavailable.");
                return;
            }
            data.Donor = CarScript.Cast(data.m_Target.GetObject());
            data.Vessel = data.m_MainItem;
            data.DiagnosticStatus = "reservation_rejected";
            if (s_Locks.Acquire(data, GetGame().GetTime()))
                data.DiagnosticStatus = "observing";
            else
            {
                HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON_DIAGNOSTIC, "Siphon diagnostic refused; the target or player is already reserved.");
            }
        }
    }

    override void OnFinishProgressServer(ActionData action_data)
    {
        HCSiphonDiagnosticData data = HCSiphonDiagnosticData.Cast(action_data);
        if (!GetGame() || !GetGame().IsServer()) return;
        if (data && !data.Sampled)
        {
            if (!s_DiagnosticEnabled)
            {
                HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON_DIAGNOSTIC, "Siphon diagnostic refused; the server diagnostic is disabled.");
                return;
            }
            if (!s_Locks.Owns(data, GetGame().GetTime()) || !data.m_Target || data.m_Target.GetObject() != data.Donor || data.m_MainItem != data.Vessel || !ValidateLive(data.m_Player, data.m_Target, data.Vessel))
            {
                s_Locks.Release(data);
                data.DiagnosticStatus = "sample_rejected";
                HCRefusalReport.ActionRefusalMessage(action_data, HCRefusal.SIPHON_DIAGNOSTIC, "Siphon diagnostic stopped; the reservation or live target changed.");
                return;
            }
            data.Sampled = true;
            float capacity = data.Donor.GetFluidCapacity(CarFluid.FUEL);
            float fraction = data.Donor.GetFluidFraction(CarFluid.FUEL);
            data.ObservedDonorLiters = capacity * fraction;
            data.ObservedVesselMl = data.Vessel.GetQuantity();
            float elapsedSeconds = (GetGame().GetTime() - data.StartedMs) * 0.001;
            data.PlannedMl = HCFuelTransferPolicy.PlanQuantum(capacity, fraction, data.ObservedVesselMl, data.Vessel.GetQuantityMax(), s_RateMl, elapsedSeconds, s_MaxStepSeconds, s_CapMl, s_CapMl);
            data.DiagnosticStatus = "proposal_only_nonatomic_observation";
            if (s_TrustedTransferEnabled)
                TransferDiagnostic(data);
            s_Locks.Release(data);
        }
    }

    override void OnEndServer(ActionData action_data)
    {
        HCSiphonDiagnosticData data = HCSiphonDiagnosticData.Cast(action_data);
        s_Locks.Release(data);
        super.OnEndServer(action_data);
    }

    // No donor-fuel-positive check here: the debit may legitimately empty it.
    // Revalidate the actor/held destination, native compatibility and geometry.
    protected static bool RecipientReady(HCSiphonDiagnosticData data)
    {
        if (!data || !data.m_Player || !data.Donor || !data.Vessel || !data.m_Target)
            return false;
        PlayerBase player = data.m_Player;
        if (!player.IsAlive() || player.IsUnconscious() || player.IsRestrained() || player.IsInVehicle())
            return false;
        if (!player.GetIdentity() && !data.TrustedDiagnosticActor)
            return false;
        if (player.GetItemInHands() != data.Vessel || data.m_MainItem != data.Vessel || data.m_Target.GetObject() != data.Donor || data.m_Target.GetParent() || data.m_Target.GetComponentIndex() < 0)
            return false;
        if (data.Donor.IsDamageDestroyed() || data.Donor.EngineIsOn() || data.Donor.GetSpeedometerAbsolute() != 0)
            return false;
        if (data.Vessel.IsDamageDestroyed() || !data.Vessel.IsOpen() || !data.Vessel.HasQuantity() || !data.Vessel.IsLiquidContainer())
            return false;
        float quantity = data.Vessel.GetQuantity();
        float maximum = data.Vessel.GetQuantityMax();
        if (!HCFuelTransferPolicy.FiniteNonNegative(quantity) || !HCFuelTransferPolicy.FiniteNonNegative(maximum) || !(quantity < maximum))
            return false;
        if ((quantity > 0 && data.Vessel.GetLiquidType() != LIQUID_GASOLINE) || !Liquid.CanFillContainer(data.Vessel, LIQUID_GASOLINE))
            return false;
        return ReachAndVisible(player, data.Donor, data.m_Target);
    }

    protected static void ReportDiagnostic(HCSiphonDiagnosticData data)
    {
        PrintFormat("[HC SIPHON DIAGNOSTIC NONDURABLE] %1 planMl=%2 debitMl=%3 creditMl=%4 donorBeforeL=%5 donorAfterL=%6 vesselBeforeMl=%7 vesselAfterMl=%8", data.DiagnosticStatus, data.PlannedMl, data.RequestedDebitMl, data.RequestedCreditMl, data.ObservedDonorLiters, data.ObservedDonorAfterLiters, data.ObservedVesselMl, data.ObservedVesselAfterMl);
    }

    protected static bool StopTransfer(HCSiphonDiagnosticData data, string reason)
    {
        s_TrustedTransferEnabled = false;
        data.DiagnosticStatus = reason;
        ReportDiagnostic(data);
        return false;
    }

    // Trusted disposable-fixture seam, not a production transaction. This
    // coordinates our own actions only; damage/other mods and cross-save order
    // remain unproven. Never replay/refund a failed or interrupted native write.
    static bool TransferDiagnostic(HCSiphonDiagnosticData data)
    {
        if (!GetGame() || !GetGame().IsServer() || !s_DiagnosticEnabled || !s_TrustedTransferEnabled || !data || !data.Sampled || data.TransferAttempted)
            return false;
        if (!s_Locks.Owns(data, GetGame().GetTime()) || !data.m_Target || data.m_Target.GetObject() != data.Donor || data.m_MainItem != data.Vessel || !ValidateLive(data.m_Player, data.m_Target, data.Vessel))
            return false;
        if (!HCFuelTransferPolicy.FiniteNonNegative(data.PlannedMl) || data.PlannedMl <= 0 || data.PlannedMl > s_CapMl)
            return false;
        float capacity = data.Donor.GetFluidCapacity(CarFluid.FUEL);
        float fraction = data.Donor.GetFluidFraction(CarFluid.FUEL);
        data.ObservedDonorLiters = capacity * fraction;
        data.ObservedVesselMl = data.Vessel.GetQuantity();
        data.RequestedDebitMl = HCFuelTransferPolicy.PlanQuantum(capacity, fraction, data.ObservedVesselMl, data.Vessel.GetQuantityMax(), s_RateMl, s_MaxStepSeconds, s_MaxStepSeconds, data.PlannedMl, s_CapMl);
        if (data.RequestedDebitMl <= 0)
            return StopTransfer(data, "fresh_plan_rejected_no_write");
        data.TransferAttempted = true;
        data.TrustedDiagnosticActor = true;
        s_TrustedTransferEnabled = false;
        data.DiagnosticStatus = "debit_issued_unconfirmed";
        ReportDiagnostic(data);
        data.Donor.Leak(CarFluid.FUEL, data.RequestedDebitMl * 0.001);
        if (!data.Donor || !data.Vessel || !s_Locks.Owns(data, GetGame().GetTime()))
            return StopTransfer(data, "lost_endpoint_or_lease_after_debit_no_credit");
        data.ObservedDonorAfterLiters = data.Donor.GetFluidCapacity(CarFluid.FUEL) * data.Donor.GetFluidFraction(CarFluid.FUEL);
        if (data.Donor.GetFluidCapacity(CarFluid.FUEL) != capacity || data.Vessel.GetQuantity() != data.ObservedVesselMl || !RecipientReady(data))
            return StopTransfer(data, "endpoint_changed_after_debit_no_credit");
        data.RequestedCreditMl = HCFuelTransferPolicy.CreditQuantum(data.RequestedDebitMl, data.ObservedDonorLiters, data.ObservedDonorAfterLiters, data.Vessel.GetQuantity(), data.Vessel.GetQuantityMax());
        if (data.RequestedCreditMl <= 0)
            return StopTransfer(data, "debit_readback_mismatch_no_credit");
        data.DiagnosticStatus = "credit_issued_unconfirmed";
        ReportDiagnostic(data);
        Liquid.FillContainer(data.Vessel, LIQUID_GASOLINE, data.RequestedCreditMl);
        return VerifyDiagnosticReceipt(data);
    }

    protected static bool VerifyDiagnosticReceipt(HCSiphonDiagnosticData data)
    {
        if (!data.Donor || !data.Vessel)
            return StopTransfer(data, "endpoint_lost_after_credit_no_replay");
        if (!s_Locks.Owns(data, GetGame().GetTime()))
            return StopTransfer(data, "reservation_lost_after_credit_no_replay");
        float finalDonorLiters = data.Donor.GetFluidCapacity(CarFluid.FUEL) * data.Donor.GetFluidFraction(CarFluid.FUEL);
        data.ObservedVesselAfterMl = data.Vessel.GetQuantity();
        if (finalDonorLiters != data.ObservedDonorAfterLiters || data.Vessel.GetLiquidType() != LIQUID_GASOLINE)
            return StopTransfer(data, "native_state_changed_after_credit_no_replay");
        if (!HCFuelTransferPolicy.ReceiptConserves(data.ObservedDonorLiters, finalDonorLiters, data.ObservedVesselMl, data.ObservedVesselAfterMl, data.RequestedCreditMl))
            return StopTransfer(data, "receipt_nonconserving_no_replay");
        if (data.ObservedVesselAfterMl - data.ObservedVesselMl != data.RequestedCreditMl)
            return StopTransfer(data, "credit_partial_no_replay");
        float removedMl = HCFuelTransferPolicy.ExactMilliliters(data.ObservedDonorLiters - finalDonorLiters);
        if (removedMl != data.RequestedCreditMl)
            return StopTransfer(data, "debit_credit_difference_no_replay");
        data.DiagnosticStatus = "observed_exact_transfer_nondurable";
        ReportDiagnostic(data);
        return true;
    }
}
