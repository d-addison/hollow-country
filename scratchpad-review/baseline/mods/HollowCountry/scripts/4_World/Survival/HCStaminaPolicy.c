// #31 scalar server policy contract only; no handler, settings, HUD or RPC hooks.
// Not production enabled. Installed reference: scripts-1.30.164289,
// StaminaHandler.c, CfgGameplayHandler.c, EntityAI.c and PlayerBase.c.
// Prefer validated native cfggameplay fields for max/cap/weight configuration.
// Future integration must preserve native prediction/replay, consumer gates,
// sync, condition multipliers, sound, inertia, player stats and reset semantics.
//
// Units: weight is native GetWeightEx() GRAMS (already includes hands, quantity,
// wetness, attachments and cargo). Capacity/current/cost are stamina UNITS, not
// percentages or seconds; 100 is the native baseline. Rates are units/second.
// Times are simulation seconds; no wall clock, implicit catch-up or looping.
// All scalar -1 results mean REJECT: never write them into player state. Reject
// leaves the whole proposed policy transaction unapplied. Boolean rejection is
// conservative. Caller supplies settings; ranges are implementation safety limits,
// not measured/approved tuning. Both settings groups must pass before any commit.
class HCStaminaPolicy
{
    // Both comparisons intentionally reject NaN and infinities without assuming
    // an unverified native finite-number API. Bounds below are finite literals
    // or already validated values; this helper is not a general bounds validator.
    static bool Within(float value, float low, float high)
    {
        return value >= low && value <= high;
    }

    // Extended maximum 100..500 units; floor 1..max; free load 0..100 kg;
    // loss 0..20 UNITS per additional kg. Zero explicitly disables weight loss.
    static bool ValidCapacitySettings(float maximumUnits, float minimumUnits, float freeWeightGrams, float lossUnitsPerKg)
    {
        return HCStaminaPolicy.Within(maximumUnits, 100.0, 500.0) && HCStaminaPolicy.Within(minimumUnits, 1.0, maximumUnits) && HCStaminaPolicy.Within(freeWeightGrams, 0.0, 100000.0) && HCStaminaPolicy.Within(lossUnitsPerKg, 0.0, 20.0);
    }

    // Policy factors 0.05..5; ordinary recovery delay 0..10 s; exhaustion delay
    // 0..30 s; release exhaustion at 0.01..1 of CURRENT capacity. Native factors
    // remain separate, including legitimate zero from epinephrine or drowning.
    static bool ValidDynamicsSettings(float exertionScale, float recoveryScale, float recoveryDelaySeconds, float exhaustionDelaySeconds, float restartFraction)
    {
        return HCStaminaPolicy.Within(exertionScale, 0.05, 5.0) && HCStaminaPolicy.Within(recoveryScale, 0.05, 5.0) && HCStaminaPolicy.Within(recoveryDelaySeconds, 0.0, 10.0) && HCStaminaPolicy.Within(exhaustionDelaySeconds, 0.0, 30.0) && HCStaminaPolicy.Within(restartFraction, 0.01, 1.0);
    }

    // Native cached authoritative weight only; do not rescan/add hands twice.
    // Reject negative/unavailable/>1000 kg observations.
    static float CapacityUnits(float weightGrams, float maximumUnits, float minimumUnits, float freeWeightGrams, float lossUnitsPerKg)
    {
        if (!HCStaminaPolicy.ValidCapacitySettings(maximumUnits, minimumUnits, freeWeightGrams, lossUnitsPerKg) || !HCStaminaPolicy.Within(weightGrams, 0.0, 1000000.0))
        {
            return -1.0;
        }
        float excessGrams = weightGrams - freeWeightGrams;
        if (excessGrams < 0.0)
        {
            excessGrams = 0.0;
        }
        float capacity = maximumUnits - excessGrams / 1000.0 * lossUnitsPerKg;
        if (capacity < minimumUnits)
        {
            capacity = minimumUnits;
        }
        return capacity;
    }

    // Candidate REPLACEMENT native scalar step, never an extra update on top.
    // Native signed rate includes category settings/gain bonus, but NOT native
    // condition factors or policy factors yet. Event cost is category-adjusted
    // native cost, similarly unscaled, consumed ONCE (also for zero-dt events).
    // Keep native modifier-specific cooldowns; supply their maximum together with
    // policy cooldown. Positive event spend suppresses recovery this frame.
    // Prior cooldown subtracts only recovery time, never exertion.
    //
    // Protocol: validate BOTH settings sets; calculate capacity; StepUnits;
    // NextCooldownSeconds; IsExhausted; commit ALL results atomically on authority
    // only if accepted. Record actual requested scaled exertion (event + negative
    // rate * dt) for cooldown, even when current is already zero. A transition to
    // exhaustion means positive clipped current -> zero result ONLY.
    // dt >1 s is rejected; integration must explicitly handle long frames without
    // inventing elapsed time, silently dropping events or unbounded catch-up.
    static float StepUnits(bool serverAuthority, bool enabled, float currentUnits, float capacityUnits, float elapsedSeconds, float nativeRateUnitsPerSecond, float nativeEventCostUnits, float nativeDepletionFactor, float nativeRecoveryFactor, float exertionScale, float recoveryScale, float cooldownSeconds)
    {
        if (!serverAuthority || !enabled)
        {
            return -1.0;
        }
        if (!HCStaminaPolicy.Within(currentUnits, 0.0, 500.0) || !HCStaminaPolicy.Within(capacityUnits, 1.0, 500.0) || !HCStaminaPolicy.Within(elapsedSeconds, 0.0, 1.0) || !HCStaminaPolicy.Within(nativeRateUnitsPerSecond, -100.0, 100.0) || !HCStaminaPolicy.Within(nativeEventCostUnits, 0.0, 500.0))
        {
            return -1.0;
        }
        if (!HCStaminaPolicy.Within(nativeDepletionFactor, 0.0, 16.0) || !HCStaminaPolicy.Within(nativeRecoveryFactor, 0.0, 16.0) || !HCStaminaPolicy.Within(exertionScale, 0.05, 5.0) || !HCStaminaPolicy.Within(recoveryScale, 0.05, 5.0) || !HCStaminaPolicy.Within(cooldownSeconds, 0.0, 30.0))
        {
            return -1.0;
        }
        if (currentUnits > capacityUnits)
        {
            currentUnits = capacityUnits;
        }
        float eventSpend = nativeEventCostUnits * nativeDepletionFactor * exertionScale;
        float nextUnits = currentUnits - eventSpend;
        if (nativeRateUnitsPerSecond < 0.0)
        {
            nextUnits = nextUnits + nativeRateUnitsPerSecond * elapsedSeconds * nativeDepletionFactor * exertionScale;
        }
        else
        {
            float recoverySeconds = elapsedSeconds - cooldownSeconds;
            if (recoverySeconds > 0.0 && eventSpend == 0.0)
            {
                nextUnits = nextUnits + nativeRateUnitsPerSecond * recoverySeconds * nativeRecoveryFactor * recoveryScale;
            }
        }
        if (nextUnits < 0.0)
        {
            nextUnits = 0.0;
        }
        if (nextUnits > capacityUnits)
        {
            nextUnits = capacityUnits;
        }
        return nextUnits;
    }

    // After StepUnits: spentUnits is actual requested exertion after BOTH factors
    // (<=48000 per accepted step), not clamped old-current minus new. Attempted
    // exertion at zero therefore retains cooldown. Rest at zero must pass false
    // for becameExhausted, allowing recovery without a perpetual cooldown loop.
    // Keep larger existing/native delays; never replace them with shorter ones.
    static float NextCooldownSeconds(float previousSeconds, float elapsedSeconds, float spentUnits, bool becameExhausted, float recoveryDelaySeconds, float exhaustionDelaySeconds)
    {
        if (!HCStaminaPolicy.Within(previousSeconds, 0.0, 30.0) || !HCStaminaPolicy.Within(elapsedSeconds, 0.0, 1.0) || !HCStaminaPolicy.Within(spentUnits, 0.0, 50000.0) || !HCStaminaPolicy.Within(recoveryDelaySeconds, 0.0, 10.0) || !HCStaminaPolicy.Within(exhaustionDelaySeconds, 0.0, 30.0))
        {
            return -1.0;
        }
        float remaining = previousSeconds - elapsedSeconds;
        if (remaining < 0.0)
        {
            remaining = 0.0;
        }
        if (spentUnits > 0.0 && remaining < recoveryDelaySeconds)
        {
            remaining = recoveryDelaySeconds;
        }
        if (becameExhausted && remaining < exhaustionDelaySeconds)
        {
            remaining = exhaustionDelaySeconds;
        }
        return remaining;
    }

    static bool IsExhausted(bool wasExhausted, float currentUnits, float capacityUnits, float restartFraction)
    {
        if (!HCStaminaPolicy.Within(currentUnits, 0.0, 500.0) || !HCStaminaPolicy.Within(capacityUnits, 1.0, 500.0) || !HCStaminaPolicy.Within(restartFraction, 0.01, 1.0))
        {
            return true;
        }
        return currentUnits <= 0.0 || (wasExhausted && currentUnits < capacityUnits * restartFraction);
    }

    // Additional server veto, NEVER replacement native permission. Cost is after
    // factors. This method does not spend/replay an event or change client state.
    static bool MayExert(bool serverAuthority, bool enabled, bool nativeAllowed, bool exhausted, float currentUnits, float finalCostUnits)
    {
        return serverAuthority && enabled && nativeAllowed && !exhausted && HCStaminaPolicy.Within(currentUnits, 0.0, 500.0) && currentUnits > 0.0 && HCStaminaPolicy.Within(finalCostUnits, 0.0, 500.0) && currentUnits >= finalCostUnits;
    }

    // Candidate normalized exhaustion only, no native camera/audio/HUD writes.
    static float ExhaustionFraction(float currentUnits, float capacityUnits)
    {
        if (!HCStaminaPolicy.Within(currentUnits, 0.0, 500.0) || !HCStaminaPolicy.Within(capacityUnits, 1.0, 500.0))
        {
            return -1.0;
        }
        if (currentUnits > capacityUnits)
        {
            currentUnits = capacityUnits;
        }
        return 1.0 - currentUnits / capacityUnits;
    }
}
