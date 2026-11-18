// V2 #59 distance-only server veto, shared by all 4_World consumers.
// Installed native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 2_GameLib/gameLib.c:4 GetGame; 3_Game/Global/Game.c:945 GetPlayers(out array<Man>),
// :1120 IsServer, :1535 GetTime (milliseconds); 3_Game/Entities/Object.c:287
// GetPosition, :517 IsAlive; 1_Core/proto/EnConvert.c:210 vector.DistanceSq;
// EnScript.c:117 Managed, :380 Count, :385 Clear, :407 Insert, :470 RemoveOrdered;
// EnString.c:199 Length, :526 string.Format; EnDebug.c:96 Print.
// No raycasts, sight/optics/camera tracking, destinations or player data exports.
// Cached samples are up to one second old; they cannot prove absence between samples.
// Legacy C11 / IC-07 diagnostic contracts below retain their existing semantics.
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

// Session-local evidence only. Eviction/parameter changes always restart grace.
class HCObserverTransitionSite extends Managed
{
    string Key;
    vector Position;
    float FarDistance;
    float GraceSeconds;
    int ClearSince = -1;
}

// Owned once by the public gate. No module slot, call queue or feature setting:
// callers keep their own admission/preferences; this utility only vetoes them.
class HCObserverTransitionRuntime extends Managed
{
    protected ref array<Man> m_Players = new array<Man>();
    protected ref array<vector> m_Positions = new array<vector>();
    protected ref array<ref HCObserverTransitionSite> m_Sites = new array<ref HCObserverTransitionSite>();
    protected int m_SnapshotAt = -1;
    protected int m_LastNow = -1;
    protected bool m_SnapshotValid;
    protected int m_Checks;
    protected int m_Refused;
    protected int m_LastLog = -1;

    bool ValidPosition(vector pos)
    {
        int axis = 0;
        while (axis < 3)
        {
            float coordinate = pos[axis];
            if (!HCObserverTransitionGate.Finite(coordinate) || coordinate < -1000000 || coordinate > 1000000) { return false; }
            axis++;
        }
        return true;
    }

    bool ValidArea(vector pos, float farDistance)
    {
        return this.ValidPosition(pos) && HCObserverTransitionGate.Finite(farDistance) && farDistance >= 0 && farDistance <= 1000000;
    }

    bool AreaClear(vector pos, float farDistance)
    {
        float squared = farDistance * farDistance;
        foreach (vector observerPosition : m_Positions)
        {
            // The exact boundary is a veto, including a zero-radius coincidence.
            if (vector.DistanceSq(observerPosition, pos) <= squared) { return false; }
        }
        return true;
    }

    bool Snapshot(int now)
    {
        if (now < 0 || now < m_LastNow)
        {
            m_Positions.Clear();
            m_Sites.Clear();
            m_SnapshotValid = false;
            m_SnapshotAt = now;
            m_LastNow = now;
            return false;
        }
        m_LastNow = now;
        if (m_SnapshotAt >= 0 && now - m_SnapshotAt < 1000) { return m_SnapshotValid; }
        // Allow normal once-per-second tick jitter, never age grace over a gap.
        bool continuous = m_SnapshotAt >= 0 && now - m_SnapshotAt <= 2000;
        m_SnapshotAt = now;
        m_Positions.Clear();
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        // Structural caps, not measured population/performance promises.
        bool valid = m_Players.Count() <= 64;
        if (valid)
        {
            foreach (Man player : m_Players)
            {
                if (!player) { valid = false; break; }
                if (!player.IsAlive()) { continue; }
                vector playerPosition = player.GetPosition();
                if (!this.ValidPosition(playerPosition)) { valid = false; break; }
                m_Positions.Insert(playerPosition);
            }
        }
        m_Players.Clear(); // Cache values, never player handles or identities.
        m_SnapshotValid = valid;
        // Every sampled incursion resets every affected key, even when a
        // different consumer requested this refresh. At most 128 * 64 distances.
        foreach (HCObserverTransitionSite site : m_Sites)
        {
            if (!continuous || !valid || !this.AreaClear(site.Position, site.FarDistance)) { site.ClearSince = -1; }
            else if (site.ClearSince < 0) { site.ClearSince = now; }
        }
        return valid;
    }

    HCObserverTransitionSite Find(string key)
    {
        foreach (HCObserverTransitionSite candidate : m_Sites)
        {
            if (candidate.Key == key) { return candidate; }
        }
        return null;
    }

    bool Record(bool allowed, int now)
    {
        // Interval counters saturate instead of overflowing under abusive calls.
        if (m_Checks < 1000000000) { m_Checks++; }
        if (!allowed && m_Refused < 1000000000) { m_Refused++; }
        if (m_LastLog < 0) { m_LastLog = now; }
        if (now >= m_LastLog && now - m_LastLog >= 600000)
        {
            Print(string.Format("[HollowCountry] V2 observer gate checks=%1 refused=%2", m_Checks, m_Refused));
            m_Checks = 0;
            m_Refused = 0;
            m_LastLog = now;
        }
        return allowed;
    }

    bool CanTransition(vector pos, float farDistance)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        int now = GetGame().GetTime();
        bool clear = this.Snapshot(now) && this.ValidArea(pos, farDistance) && this.AreaClear(pos, farDistance);
        return this.Record(clear, now);
    }

    // Continuous clear means continuous sampled evidence: call at least every
    // two seconds while waiting. Longer gaps restart grace. Namespace keys by
    // feature/site; the same key may not carry evidence to another area/radius.
    bool Quiet(string key, vector pos, float far, float graceSeconds)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        int now = GetGame().GetTime();
        bool valid = this.Snapshot(now) && this.ValidArea(pos, far);
        HCObserverTransitionSite site = this.Find(key);
        if (!valid || key.Length() == 0 || key.Length() > 128 || !HCObserverTransitionGate.Finite(graceSeconds) || graceSeconds < 0 || graceSeconds > 86400)
        {
            if (site) { site.ClearSince = -1; }
            return this.Record(false, now);
        }
        if (!site)
        {
            site = new HCObserverTransitionSite();
            site.Key = key;
            // Bounded FIFO; a forgotten key must earn an entirely new grace.
            if (m_Sites.Count() >= 128) { m_Sites.RemoveOrdered(0); }
            m_Sites.Insert(site);
        }
        if (site.Position != pos || site.FarDistance != far || site.GraceSeconds != graceSeconds)
        {
            site.ClearSince = -1;
            site.Position = pos;
            site.FarDistance = far;
            site.GraceSeconds = graceSeconds;
        }
        if (!this.AreaClear(pos, far))
        {
            site.ClearSince = -1;
            return this.Record(false, now);
        }
        if (site.ClearSince < 0) { site.ClearSince = now; }
        return this.Record((now - site.ClearSince) * 0.001 >= graceSeconds, now);
    }
}

// One state per logical cohort/world/epoch, owned by the diagnostic caller.
// Never persist this evidence across restart; construct fresh unknown state.
class HCObserverTransitionGate
{
    protected static ref HCObserverTransitionRuntime s_Runtime;

    protected static HCObserverTransitionRuntime Runtime()
    {
        if (!s_Runtime) { s_Runtime = new HCObserverTransitionRuntime(); }
        return s_Runtime;
    }

    static bool CanTransition(vector pos, float farDistance)
    {
        return HCObserverTransitionGate.Runtime().CanTransition(pos, farDistance);
    }

    static bool Quiet(string key, vector pos, float far, float graceSeconds)
    {
        return HCObserverTransitionGate.Runtime().Quiet(key, pos, far, graceSeconds);
    }

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
