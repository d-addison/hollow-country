// #53 fuel transfer scalars. Vehicle fluid units are liters; container
// quantity units are milliliters, following installed CAContinuousFillFuel's
// quantity * 0.001 conversion. The Siphon* functions serve the registered
// HCActionSiphonFuelFromCar; the exact-arithmetic functions serve the
// unregistered diagnostic. Callers establish server authority, live car,
// held vessel, gasoline compatibility and reach. Leak/FillContainer are
// separate operations: credit is capped by the observed tank loss, so a
// rounding gap can only lose fuel, never create it.
// DayZDiag, normal PBO/server and multiplayer/recovery gates remain pending.
class HCFuelTransferPolicy
{
    static bool FiniteNonNegative(float value)
    {
        return value >= 0 && value <= float.MAX;
    }

    // For ordered nonnegative binary32 operands, reconstruction rejects any
    // rounded subtraction. Reject ambiguity rather than introduce tolerance.
    static bool ExactDifference(float high, float low)
    {
        if (!FiniteNonNegative(high) || !FiniteNonNegative(low) || high < low)
            return false;
        float delta = high - low;
        return high - delta == low;
    }

    // Power-of-two scaling is exact unless it overflows. Require both
    // subtractions in 1000 = 1024 - 16 - 8 to be exact; -1 rejects.
    static float ExactMilliliters(float liters)
    {
        float high = liters * 1024.0;
        float middle = liters * 16.0;
        float low = liters * 8.0;
        if (!ExactDifference(high, middle))
            return -1;
        float remainder = high - middle;
        if (!ExactDifference(remainder, low))
            return -1;
        return remainder - low;
    }

    // Returns one bounded proposed quantum in ml. Zero means do not transfer.
    // Excess elapsed time is discarded; no accumulated catch-up or retry work.
    static float PlanQuantum(float capacityLiters, float fuelFraction, float vesselMl, float vesselMaxMl, float rateMlPerSecond, float elapsedSeconds, float maxStepSeconds, float remainingMl, float quantumCapMl)
    {
        if (!FiniteNonNegative(capacityLiters) || !FiniteNonNegative(fuelFraction))
            return 0;
        if (!FiniteNonNegative(vesselMl) || !FiniteNonNegative(vesselMaxMl))
            return 0;
        if (!FiniteNonNegative(rateMlPerSecond) || !FiniteNonNegative(elapsedSeconds))
            return 0;
        if (!FiniteNonNegative(maxStepSeconds) || !FiniteNonNegative(remainingMl) || !FiniteNonNegative(quantumCapMl))
            return 0;
        if (!(capacityLiters > 0 && fuelFraction > 0 && fuelFraction <= 1))
            return 0;
        if (!(vesselMaxMl > vesselMl && rateMlPerSecond > 0 && elapsedSeconds > 0))
            return 0;
        if (!(maxStepSeconds > 0 && remainingMl > 0 && quantumCapMl > 0))
            return 0;
        float fuelLiters = capacityLiters * fuelFraction;
        float availableMl = ExactMilliliters(fuelLiters);
        if (!FiniteNonNegative(availableMl))
            return 0;
        float stepSeconds = elapsedSeconds;
        if (stepSeconds > maxStepSeconds)
            stepSeconds = maxStepSeconds;
        float quantumMl = rateMlPerSecond * stepSeconds;
        if (!FiniteNonNegative(quantumMl))
            return 0;
        float freeMl = vesselMaxMl - vesselMl;
        if (quantumMl > availableMl)
            quantumMl = availableMl;
        if (quantumMl > freeMl)
            quantumMl = freeMl;
        if (quantumMl > remainingMl)
            quantumMl = remainingMl;
        if (quantumMl > quantumCapMl)
            quantumMl = quantumCapMl;
        float debitLiters = quantumMl * 0.001;
        float afterLiters = fuelLiters - debitLiters;
        if (!(debitLiters > 0 && afterLiters >= 0 && afterLiters < fuelLiters))
            return 0;
        float afterMl = vesselMl + quantumMl;
        if (!(afterMl > vesselMl && afterMl <= vesselMaxMl))
            return 0;
        if (!ExactDifference(afterMl, vesselMl) || afterMl - vesselMl > quantumMl)
            return 0;
        return quantumMl;
    }

    // Proposed credit after fresh native debit readback, using fresh free space.
    // No observed debit, increasing fuel or excess debit rejects the step.
    // Strict comparisons deliberately fail closed; no invented native tolerance.
    // Caller must stop on ambiguity, never automatically replay or refund.
    static float CreditQuantum(float plannedMl, float donorBeforeLiters, float donorAfterLiters, float vesselMl, float vesselMaxMl)
    {
        if (!FiniteNonNegative(plannedMl) || !FiniteNonNegative(donorBeforeLiters) || !FiniteNonNegative(donorAfterLiters))
            return 0;
        if (!FiniteNonNegative(vesselMl) || !FiniteNonNegative(vesselMaxMl))
            return 0;
        if (!(plannedMl > 0 && donorAfterLiters < donorBeforeLiters && vesselMl < vesselMaxMl))
            return 0;
        if (!ExactDifference(donorBeforeLiters, donorAfterLiters))
            return 0;
        float removedMl = ExactMilliliters(donorBeforeLiters - donorAfterLiters);
        if (!FiniteNonNegative(removedMl) || removedMl <= 0 || removedMl > plannedMl)
            return 0;
        float creditMl = removedMl;
        float freeMl = vesselMaxMl - vesselMl;
        if (creditMl > freeMl)
            creditMl = freeMl;
        float afterMl = vesselMl + creditMl;
        if (!(creditMl > 0 && afterMl > vesselMl && afterMl <= vesselMaxMl))
            return 0;
        if (!ExactDifference(afterMl, vesselMl) || afterMl - vesselMl > creditMl)
            return 0;
        return creditMl;
    }

    // Readback conservation check only. Partial credit can pass while losing
    // fuel; true is not successful completion, ownership or durable atomicity.
    static bool ReceiptConserves(float donorBeforeLiters, float donorAfterLiters, float vesselBeforeMl, float vesselAfterMl, float creditCapMl)
    {
        if (!FiniteNonNegative(donorBeforeLiters) || !FiniteNonNegative(donorAfterLiters))
            return false;
        if (!FiniteNonNegative(vesselBeforeMl) || !FiniteNonNegative(vesselAfterMl) || !FiniteNonNegative(creditCapMl))
            return false;
        if (!(donorAfterLiters < donorBeforeLiters && vesselAfterMl > vesselBeforeMl && creditCapMl > 0))
            return false;
        if (!ExactDifference(donorBeforeLiters, donorAfterLiters) || !ExactDifference(vesselAfterMl, vesselBeforeMl))
            return false;
        float removedMl = ExactMilliliters(donorBeforeLiters - donorAfterLiters);
        float addedMl = vesselAfterMl - vesselBeforeMl;
        if (!FiniteNonNegative(removedMl) || !FiniteNonNegative(addedMl))
            return false;
        return addedMl > 0 && addedMl <= removedMl && addedMl <= creditCapMl;
    }

    // Session total in ml: the real tank's fuel and the vessel's free space.
    static float SiphonSessionMl(float fuelLiters, float vesselMl, float vesselMaxMl)
    {
        if (!FiniteNonNegative(fuelLiters) || !FiniteNonNegative(vesselMl) || !FiniteNonNegative(vesselMaxMl))
            return 0;
        if (!(fuelLiters > 0 && vesselMaxMl > vesselMl))
            return 0;
        float availableMl = fuelLiters * 1000.0;
        float freeMl = vesselMaxMl - vesselMl;
        if (!FiniteNonNegative(availableMl))
            return 0;
        if (availableMl > freeMl)
            return freeMl;
        return availableMl;
    }

    // One server step from fresh readback; zero means stop without mutation.
    static float SiphonStepMl(float fuelLiters, float vesselMl, float vesselMaxMl, float pendingMl, float remainingMl)
    {
        if (!FiniteNonNegative(pendingMl))
            return 0;
        float stepMl = SiphonSessionMl(fuelLiters, vesselMl, vesselMaxMl);
        if (stepMl > pendingMl)
            stepMl = pendingMl;
        if (stepMl > remainingMl)
            stepMl = remainingMl;
        return stepMl;
    }

    // Credit only what the tank was observed to lose, never more than the step.
    static float SiphonCreditMl(float stepMl, float fuelBeforeLiters, float fuelAfterLiters)
    {
        if (!FiniteNonNegative(stepMl) || !FiniteNonNegative(fuelBeforeLiters) || !FiniteNonNegative(fuelAfterLiters))
            return 0;
        if (!(stepMl > 0 && fuelAfterLiters < fuelBeforeLiters))
            return 0;
        float removedMl = (fuelBeforeLiters - fuelAfterLiters) * 1000.0;
        if (!FiniteNonNegative(removedMl))
            return 0;
        if (removedMl > stepMl)
            return stepMl;
        return removedMl;
    }
}
