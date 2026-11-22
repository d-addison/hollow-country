// V2 #59 distance-only server veto, shared by all 4_World consumers.
// Installed native snapshot: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 2_GameLib/gameLib.c:4 GetGame; 3_Game/Global/Game.c:945 GetPlayers(out array<Man>),
// :1120 IsServer, :1535 GetTime (milliseconds); 3_Game/Entities/Object.c:287
// GetPosition, :517 IsAlive; 1_Core/proto/EnConvert.c:210 vector.DistanceSq;
// EnScript.c:117 Managed, :380 Count, :385 Clear, :407 Insert, :470 RemoveOrdered;
// EnString.c:199 Length, :526 string.Format; EnDebug.c:96 Print.
// No raycasts, sight/optics/camera tracking, destinations or player data exports.
// Cached samples are up to one second old; they cannot prove absence between samples.
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

// Shared session-local distance veto.
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
}
