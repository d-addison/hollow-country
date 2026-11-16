// Scalar policy seam; synthetic unit tests execute these bodies, never native AI.
class HCInfectedPolicy
{
    static bool AcceptClue(float now, float observed, float expires, int provenance, float strength, int hops)
    {
        return now == now && observed == observed && expires == expires && now >= 0 && observed >= 0 && observed <= now && expires > now && expires - observed <= 30 && (provenance == 1 || provenance == 2) && strength >= 0.2 && strength <= 1 && hops >= 0 && hops <= 2;
    }

    static bool AdmitVoice(float now, float nextAllowed, int queued, int queueCap, int work, int workCap, bool alive, bool nativeNoise, bool duplicate, int hops, float strength, float expires)
    {
        return now >= 0 && now >= nextAllowed && queued >= 0 && queueCap > 0 && queueCap <= 32 && queued < queueCap && work >= 0 && workCap > 0 && workCap <= 32 && work < workCap && alive && nativeNoise && !duplicate && hops >= 0 && hops < 2 && strength >= 0.2 && strength <= 1 && expires > now && expires - now <= 30;
    }

    static float Attenuate(float strength)
    {
        return strength * 0.5;
    }

    static bool CanReserve(int groups, int groupCap, int reserved, int memberCap, int requested)
    {
        return groups >= 0 && groupCap > 0 && groupCap <= 2 && groups < groupCap && reserved >= 0 && memberCap > 0 && memberCap <= 24 && requested > 0 && requested <= 6 && reserved <= memberCap - requested;
    }

    static bool CanMaterialize()
    {
        return false;
    }

    static bool CanAbstract()
    {
        return false;
    }

    static int NextHordeState(int state, int living, bool clue, bool engaged, float quiet, float age)
    {
        if (state == 5 || living <= 0 || age >= 3600 || age < 0)
        {
            return 5;
        }
        if (state == 6)
        {
            return 6;
        }
        if (engaged)
        {
            return 3;
        }
        if (clue)
        {
            return 2;
        }
        if ((state == 3 || state == 4) && quiet < 60)
        {
            return 4;
        }
        return 1;
    }

    static int AfterRestart(int state)
    {
        if (state == 5)
        {
            return 5;
        }
        return 6;
    }

    static bool ValidSnapshotHeader(int schema, bool sameWorld, int epoch, int groups, int reserved, int memberCap, int savedAt, int now)
    {
        return schema == 1 && sameWorld && epoch > 0 && groups >= 0 && groups <= 2 && memberCap > 0 && memberCap <= 24 && reserved >= 0 && reserved <= memberCap && savedAt > 0 && now >= savedAt;
    }

    static bool SuppressStrike(bool attack, bool target, bool reachable)
    {
        return attack && target && !reachable;
    }

    static bool ValidGroupRecord(int id, int index, int reserved, int living, int state, int created, int signal, int saved)
    {
        return id == index + 1 && reserved >= 3 && reserved <= 6 && living >= 0 && living <= reserved && state >= 0 && state <= 6 && created > 0 && created <= saved && signal >= created && signal <= saved;
    }

    static bool ValidGenerationPair(int newer, int older, int epoch, int oldEpoch, int saved, int oldSaved, int reserved, int oldReserved, int groups, int oldGroups)
    {
        return newer == older + 1 && epoch == oldEpoch && saved >= oldSaved && reserved >= oldReserved && groups >= oldGroups;
    }

    static float ProfileLifetime(bool military, bool injured, int stance)
    {
        if (stance < 0 || stance > 3)
        {
            return 0;
        }
        if (injured)
        {
            return 6 + stance;
        }
        if (military)
        {
            return 12 + stance;
        }
        return 24 + stance;
    }

    static bool CanAdvanceRecord(int oldId, int id, int oldReserved, int reserved, int oldLiving, int living, int oldState, int state, int oldCreated, int created)
    {
        return id == oldId && reserved == oldReserved && living <= oldLiving && created == oldCreated && (oldState != 5 || state == 5) && (oldState != 6 || state == 6 || state == 5);
    }

    static bool MayInvestigate(bool enabled, bool liveVisual, bool engaged, bool injured, bool grouped, int attempts, float now, float nextAttempt)
    {
        return enabled && liveVisual && !engaged && !injured && !grouped && attempts < 2 && now >= nextAttempt;
    }

    static bool RouteAlive(float now, float expires, float stalledSeconds, bool alive, bool interrupted)
    {
        return now >= 0 && now < expires && stalledSeconds >= 0 && stalledSeconds < 15 && alive && !interrupted;
    }

    static bool DirectlyObserved(bool nativeCandidate, float distanceSq, float facing, bool viewTarget, bool fireTarget)
    {
        return nativeCandidate && distanceSq >= 0.01 && distanceSq <= 400 && facing >= 0.5 && viewTarget && fireTarget;
    }

    static int SearchAnchorBudget(bool military, bool injured)
    {
        if (injured)
        {
            return 0;
        }
        if (military)
        {
            return 1;
        }
        return 3;
    }

    static bool MayRetryRelease(int attempts, int now, int nextAttempt)
    {
        return attempts >= 0 && attempts < 3 && now >= 0 && now >= nextAttempt;
    }

    static bool AdoptionWorkReady(int workCap)
    {
        return workCap >= 9 && workCap <= 32;
    }

    static int NextAdoptionCursor(int cursor, int count)
    {
        if (count <= 0)
        {
            return 0;
        }
        return (cursor + 1) % count;
    }

    static bool CountsOwnedMember(bool alive, bool agent, bool sameGroup)
    {
        return alive && agent && sameGroup;
    }
}
