// C11 / IC-07: diagnostic-only veto contract; no observer provider is installed.
class HCObserverTransitionPolicy
{
    bool ProvisionalDiagnostic = false;
    int Revision = 0;
    float TimeBound = 0;
    float DistanceBound = 0;
    float DurationBound = 0;
    float NearDistance = 0;
    float FarDistance = 0;
    float SnapshotTTL = 0;
    float VisibilityGrace = 0;
    float ProximityGrace = 0;
    float QuietPeriod = 0;
    float TransitionCooldown = 0;
    int MaxObservers = 0;
    int MaxSamples = 0;
}

class HCObserverTransitionSample
{
    int ObserverId = 0;
    float ObservedAt = -1;
    bool CoverageKnown = false;
    bool SpectatorKnown = false;
    bool IsSpectator = false;
    bool OpticsKnown = false;
    bool UsingOptics = false;
    bool VisibilityKnown = false;
    bool Visible = false;
    bool RecentVisibilityKnown = false;
    float LastVisibleAt = -1;
    bool NativeCombatKnown = false;
    bool InNativeCombat = false;
    bool ProximityKnown = false;
    float Distance = -1;
    bool RecentProximityKnown = false;
    float LastNearAt = -1;
}

class HCObserverTransitionInput
{
    float CapturedAt = -1;
    int RosterRevision = 0;
    bool CoverageKnown = false;
    bool SpectatorCoverageKnown = false;
    bool OpticsCoverageKnown = false;
    int ExpectedObservers = -1;
    ref array<ref HCObserverTransitionSample> Observers;
    bool NativeCombatKnown = false;
    bool InNativeCombat = false;
    bool MembershipKnown = false;
    bool MembershipResolved = false;
    bool CEAuthorityKnown = false;
    bool CEAuthority = false;
    bool DurableIntentKnown = false;
    bool DurableIntent = false;
    bool PopulationBudgetKnown = false;
    bool PopulationWithinBudget = false;
    bool TransitionHistoryKnown = false;
    float LastTransitionAt = -1;
}

class HCObserverTransitionState
{
    ref HCObserverTransitionPolicy Policy;
    float HighWater = -1;
    float ClearSince = -1;
    float LastSnapshotAt = -1;
    int RosterRevision = 0;
    int ExpectedObservers = -1;
    float LastTransitionAt = -1;
    float LastVisibilityAt = -1;
    float LastProximityAt = -1;
}

// One state per logical cohort/world/epoch, owned by the diagnostic caller.
// Never persist this evidence across restart; construct fresh unknown state.
class HCObserverTransitionGate
{
    static bool Finite(float value)
    {
        return value == value && value - value == 0;
    }

    static bool Bounded(float value, float bound)
    {
        return HCObserverTransitionGate.Finite(value) && value >= 0 && value <= bound;
    }

    // -1 means known never/empty only when the accompanying Known bit is true.
    static bool OptionalTime(float value, float bound)
    {
        return value == -1 || HCObserverTransitionGate.Bounded(value, bound);
    }

    static bool Duration(float value, float bound)
    {
        return HCObserverTransitionGate.Bounded(value, bound) && value > 0;
    }

    static bool ValidPolicy(HCObserverTransitionPolicy policy)
    {
        if (!policy || !policy.ProvisionalDiagnostic || policy.Revision <= 0)
        {
            return false;
        }
        if (!HCObserverTransitionGate.Finite(policy.TimeBound) || !(policy.TimeBound > 0))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Finite(policy.DistanceBound) || !(policy.DistanceBound > 0))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.DurationBound, policy.TimeBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Bounded(policy.NearDistance, policy.DistanceBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Bounded(policy.FarDistance, policy.DistanceBound))
        {
            return false;
        }
        if (!(policy.FarDistance > policy.NearDistance))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.SnapshotTTL, policy.DurationBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.VisibilityGrace, policy.DurationBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.ProximityGrace, policy.DurationBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.QuietPeriod, policy.DurationBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Duration(policy.TransitionCooldown, policy.DurationBound))
        {
            return false;
        }
        // Structural work ceiling, not a measured population or gameplay budget.
        if (!(policy.MaxSamples >= 1 && policy.MaxSamples <= 32))
        {
            return false;
        }
        return policy.MaxObservers >= 1 && policy.MaxObservers <= policy.MaxSamples;
    }

    // Copy caller values so later mutations cannot silently relax a live window.
    // Every Configure attempt invalidates quiet evidence; clocks/replays persist.
    static bool Configure(HCObserverTransitionState state, HCObserverTransitionPolicy policy)
    {
        if (!state)
        {
            return false;
        }
        state.ClearSince = -1;
        state.Policy = null;
        if (!HCObserverTransitionGate.ValidPolicy(policy))
        {
            return false;
        }
        state.Policy = new HCObserverTransitionPolicy();
        HCObserverTransitionPolicy copy = state.Policy;
        copy.ProvisionalDiagnostic = policy.ProvisionalDiagnostic;
        copy.Revision = policy.Revision;
        copy.TimeBound = policy.TimeBound;
        copy.DistanceBound = policy.DistanceBound;
        copy.DurationBound = policy.DurationBound;
        copy.NearDistance = policy.NearDistance;
        copy.FarDistance = policy.FarDistance;
        copy.SnapshotTTL = policy.SnapshotTTL;
        copy.VisibilityGrace = policy.VisibilityGrace;
        copy.ProximityGrace = policy.ProximityGrace;
        copy.QuietPeriod = policy.QuietPeriod;
        copy.TransitionCooldown = policy.TransitionCooldown;
        copy.MaxObservers = policy.MaxObservers;
        copy.MaxSamples = policy.MaxSamples;
        return true;
    }

    static int Reject(HCObserverTransitionState state, int reason)
    {
        if (state)
        {
            state.ClearSince = -1;
        }
        return reason;
    }

    static bool ValidState(HCObserverTransitionState state, float now)
    {
        float bound = state.Policy.TimeBound;
        if (!HCObserverTransitionGate.Bounded(now, bound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.HighWater, bound))
        {
            return false;
        }
        if (!(now >= state.HighWater))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.ClearSince, state.HighWater))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.LastSnapshotAt, state.HighWater))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.LastTransitionAt, state.HighWater))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.LastVisibilityAt, state.HighWater))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(state.LastProximityAt, state.HighWater))
        {
            return false;
        }
        if (!(state.RosterRevision >= 0 && state.ExpectedObservers >= -1))
        {
            return false;
        }
        return state.ExpectedObservers <= state.Policy.MaxObservers;
    }

    static bool ValidObserver(HCObserverTransitionSample observer, HCObserverTransitionPolicy policy, float now, float captured, float previous)
    {
        if (!observer || observer.ObserverId <= 0)
        {
            return false;
        }
        if (!(observer.CoverageKnown && observer.SpectatorKnown && observer.OpticsKnown))
        {
            return false;
        }
        if (!(observer.VisibilityKnown && observer.RecentVisibilityKnown && observer.NativeCombatKnown))
        {
            return false;
        }
        if (!(observer.ProximityKnown && observer.RecentProximityKnown))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Bounded(observer.ObservedAt, captured))
        {
            return false;
        }
        if (!(observer.ObservedAt > previous && now - observer.ObservedAt < policy.SnapshotTTL))
        {
            return false;
        }
        if (!HCObserverTransitionGate.Bounded(observer.Distance, policy.DistanceBound))
        {
            return false;
        }
        if (!HCObserverTransitionGate.OptionalTime(observer.LastVisibleAt, observer.ObservedAt))
        {
            return false;
        }
        return HCObserverTransitionGate.OptionalTime(observer.LastNearAt, observer.ObservedAt);
    }

    static bool ObserverVeto(HCObserverTransitionSample observer, HCObserverTransitionPolicy policy, float now)
    {
        // Active optics/spectator cameras veto even with alleged clear geometry.
        if (observer.Visible || observer.IsSpectator || observer.UsingOptics || observer.InNativeCombat)
        {
            return true;
        }
        if (observer.Distance <= policy.NearDistance)
        {
            return true;
        }
        if (observer.LastVisibleAt >= 0 && now - observer.LastVisibleAt < policy.VisibilityGrace)
        {
            return true;
        }
        return observer.LastNearAt >= 0 && now - observer.LastNearAt < policy.ProximityGrace;
    }

    // Result codes: 0=unknown/invalid, 1=observed veto, 2=waiting, 3=diagnostic
    // quiet window satisfied. ALL codes still reject executable transitions.
    static int Evaluate(HCObserverTransitionState state, HCObserverTransitionInput sampleInput, float now)
    {
        if (!state)
        {
            return 0;
        }
        HCObserverTransitionPolicy policy = state.Policy;
        if (!HCObserverTransitionGate.ValidPolicy(policy))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!HCObserverTransitionGate.ValidState(state, now))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        // Preserve a high-water mark even when this input is rejected.
        state.HighWater = now;
        if (!sampleInput)
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.CoverageKnown && sampleInput.SpectatorCoverageKnown && sampleInput.OpticsCoverageKnown))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.NativeCombatKnown && sampleInput.MembershipKnown && sampleInput.MembershipResolved))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.CEAuthorityKnown && sampleInput.CEAuthority && sampleInput.DurableIntentKnown && sampleInput.DurableIntent))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.PopulationBudgetKnown && sampleInput.PopulationWithinBudget && sampleInput.TransitionHistoryKnown))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!HCObserverTransitionGate.Bounded(sampleInput.CapturedAt, now))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.CapturedAt > state.LastSnapshotAt && now - sampleInput.CapturedAt < policy.SnapshotTTL))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!HCObserverTransitionGate.OptionalTime(sampleInput.LastTransitionAt, sampleInput.CapturedAt))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.LastTransitionAt >= state.LastTransitionAt))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.RosterRevision > 0 && sampleInput.RosterRevision >= state.RosterRevision))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (!(sampleInput.ExpectedObservers >= 0 && sampleInput.ExpectedObservers <= policy.MaxObservers))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (sampleInput.Observers == null)
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        int count = sampleInput.Observers.Count();
        if (!(count <= policy.MaxSamples && count == sampleInput.ExpectedObservers))
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        if (sampleInput.RosterRevision == state.RosterRevision && count != state.ExpectedObservers)
        {
            return HCObserverTransitionGate.Reject(state, 0);
        }
        bool veto = sampleInput.InNativeCombat;
        bool allFar = true;
        // At most 32 samples plus 496 duplicate-ID comparisons. No world scan.
        for (int index = 0; index < count; index++)
        {
            HCObserverTransitionSample observer = sampleInput.Observers[index];
            if (!HCObserverTransitionGate.ValidObserver(observer, policy, now, sampleInput.CapturedAt, state.LastSnapshotAt))
            {
                return HCObserverTransitionGate.Reject(state, 0);
            }
            for (int prior = 0; prior < index; prior++)
            {
                if (sampleInput.Observers[prior].ObserverId == observer.ObserverId)
                {
                    return HCObserverTransitionGate.Reject(state, 0);
                }
            }
            // Retain known danger even if a later observer invalidates the batch.
            // Later reports of known-never cannot erase already observed history.
            if (observer.LastVisibleAt > state.LastVisibilityAt)
            {
                state.LastVisibilityAt = observer.LastVisibleAt;
            }
            if (observer.Visible && observer.ObservedAt > state.LastVisibilityAt)
            {
                state.LastVisibilityAt = observer.ObservedAt;
            }
            if (observer.LastNearAt > state.LastProximityAt)
            {
                state.LastProximityAt = observer.LastNearAt;
            }
            if (observer.Distance <= policy.NearDistance && observer.ObservedAt > state.LastProximityAt)
            {
                state.LastProximityAt = observer.ObservedAt;
            }
            if (HCObserverTransitionGate.ObserverVeto(observer, policy, now))
            {
                veto = true;
            }
            if (observer.Distance <= policy.FarDistance)
            {
                allFar = false;
            }
        }
        if (now - state.LastSnapshotAt >= policy.SnapshotTTL)
        {
            state.ClearSince = -1;
        }
        if (sampleInput.RosterRevision != state.RosterRevision || sampleInput.LastTransitionAt != state.LastTransitionAt)
        {
            state.ClearSince = -1;
        }
        state.LastSnapshotAt = sampleInput.CapturedAt;
        state.RosterRevision = sampleInput.RosterRevision;
        state.ExpectedObservers = count;
        state.LastTransitionAt = sampleInput.LastTransitionAt;
        if (sampleInput.LastTransitionAt >= 0 && now - sampleInput.LastTransitionAt < policy.TransitionCooldown)
        {
            veto = true;
        }
        if (state.LastVisibilityAt >= 0 && now - state.LastVisibilityAt < policy.VisibilityGrace)
        {
            veto = true;
        }
        if (state.LastProximityAt >= 0 && now - state.LastProximityAt < policy.ProximityGrace)
        {
            veto = true;
        }
        if (veto)
        {
            return HCObserverTransitionGate.Reject(state, 1);
        }
        // Enter only beyond FarDistance; an existing window exits at NearDistance.
        if (state.ClearSince < 0)
        {
            if (!allFar)
            {
                return HCObserverTransitionGate.Reject(state, 2);
            }
            state.ClearSince = now;
        }
        if (now - state.ClearSince < policy.QuietPeriod)
        {
            return 2;
        }
        return 3;
    }

    // Deliberately no caller-provided override. Actual remote camera coverage,
    // CE lifecycle authority and durable entity transitions remain unresolved.
    static bool ProviderCapabilityResolved()
    {
        return false;
    }

    static bool CanTransition()
    {
        return HCObserverTransitionGate.ProviderCapabilityResolved();
    }
}
