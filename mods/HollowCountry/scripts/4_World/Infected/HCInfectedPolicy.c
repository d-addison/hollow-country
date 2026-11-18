// Scalar policy seam; synthetic unit tests execute these bodies, never native AI.
class HCInfectedPolicy
{
    // Reuse a released journal slot only after a bounded quiet interval.
    static int HordeCooldownSeconds()
    {
        return 180;
    }

    static bool MayReuseHorde(int state, bool refunded, int retired, int now)
    {
        if (state != 5 || !refunded || retired <= 0 || now < retired)
        {
            return false;
        }
        return now - retired >= HordeCooldownSeconds();
    }

    static bool AcceptClue(float now, float observed, float expires, int provenance, float strength, int hops)
    {
        if (!(now == now && observed == observed && expires == expires))
        {
            return false;
        }
        if (!(now >= 0 && observed >= 0 && observed <= now))
        {
            return false;
        }
        if (!(expires > now && expires - observed <= 30))
        {
            return false;
        }
        if (!(provenance == 1 || provenance == 2))
        {
            return false;
        }
        return strength >= 0.2 && strength <= 1 && hops >= 0 && hops <= 2;
    }

    static bool AdmitVoice(float now, float nextAllowed, int queued, int queueCap, int work, int workCap, bool alive, bool nativeNoise, bool duplicate, int hops, float strength, float expires)
    {
        if (!(now >= 0 && now >= nextAllowed))
        {
            return false;
        }
        if (!(queued >= 0 && queueCap > 0 && queueCap <= 32 && queued < queueCap))
        {
            return false;
        }
        if (!(work >= 0 && workCap > 0 && workCap <= 32 && work < workCap))
        {
            return false;
        }
        if (!(alive && nativeNoise && !duplicate))
        {
            return false;
        }
        if (!(hops >= 0 && hops < 2 && strength >= 0.2 && strength <= 1))
        {
            return false;
        }
        return expires > now && expires - now <= 30;
    }

    static float Attenuate(float strength)
    {
        return strength * 0.5;
    }

    static float CentroidWeight(int living)
    {
        if (living < 1 || living > 6)
        {
            return 0;
        }
        return 1.0 / living;
    }

    // Base personality IDs 0..5; 6 is the native injury overlay only.
    // Stalker/heavy physical capabilities are unavailable. Resolution is ordinary
    // logical behavior, never capability admission; inspect the disposition too.
    // No probability weights or physical controllers are supplied here.
    static int ResolveVariant(int requested)
    {
        if (requested < 0 || requested > 5)
        {
            return -1;
        }
        if (requested == 3 || requested == 4)
        {
            return 0;
        }
        return requested;
    }

    // "supported" describes this authored attention-policy choice only. It is
    // not qualification of native movement, audio, contact, rooms or recognition.
    static string VariantDisposition(int requested)
    {
        if (requested < 0 || requested > 5)
        {
            return "invalid";
        }
        if (requested == 3 || requested == 4)
        {
            return "unsupported_substituted_native";
        }
        return "supported";
    }

    static string VariantReason(int requested)
    {
        if (requested < 0 || requested > 5)
        {
            return "invalid_base_variant";
        }
        if (requested == 3)
        {
            return "stalker_physical_unqualified";
        }
        if (requested == 4)
        {
            return "heavy_physical_unqualified";
        }
        return "attention_policy_only";
    }

    static float VariantLifetime(int variant, int stance, bool injured)
    {
        if (!(variant >= 0 && variant <= 5 && stance >= 0 && stance <= 3))
        {
            return 0;
        }
        if (injured)
        {
            return 6 + stance;
        }
        if (variant == 2)
        {
            return 24 + stance;
        }
        if (variant == 5)
        {
            return 16 + stance;
        }
        if (variant == 1)
        {
            return 12 + stance;
        }
        return 8 + stance;
    }

    static int VariantAnchorBudget(int variant, bool injured)
    {
        if (injured || variant < 0 || variant > 5)
        {
            return 0;
        }
        if (variant == 2)
        {
            return 3;
        }
        if (variant == 5)
        {
            return 2;
        }
        return 1;
    }

    static bool PreferStimulus(float observed, int provenance, float strength, float previousObserved, int previousProvenance, float previousStrength)
    {
        if (provenance != previousProvenance)
        {
            return provenance == 2;
        }
        if (observed != previousObserved)
        {
            return observed > previousObserved;
        }
        return strength > previousStrength;
    }

    static bool RetargetAllowed(float now, float nextAllowed, float observed, float lastObserved, float expires, int attempts, bool ownsCohort, bool engaged)
    {
        if (!(now >= 0 && now >= nextAllowed && observed >= 0 && observed <= now))
        {
            return false;
        }
        if (!(expires > now && expires - observed <= 30 && observed > lastObserved))
        {
            return false;
        }
        return attempts >= 0 && attempts < 2 && ownsCohort && !engaged;
    }

    static bool CompleteMembership(int reserved, int living, int dead, int accounted, bool ambiguous)
    {
        if (!(reserved >= 3 && reserved <= 6 && living >= 0 && dead >= 0))
        {
            return false;
        }
        return !ambiguous && accounted == reserved && living + dead == reserved;
    }

    static bool CanReserve(int groups, int groupCap, int reserved, int memberCap, int requested)
    {
        if (!(groups >= 0 && groupCap > 0 && groupCap <= 2 && groups < groupCap))
        {
            return false;
        }
        if (!(reserved >= 0 && memberCap > 0 && memberCap <= 24))
        {
            return false;
        }
        return requested > 0 && requested <= 6 && reserved <= memberCap - requested;
    }

    static bool RetargetSpent(int outcome)
    {
        return outcome == 1 || outcome == 2;
    }

    static bool RouteMadeProgress(float distanceSq, float bestDistanceSq)
    {
        return distanceSq >= 0 && bestDistanceSq >= 0 && distanceSq <= bestDistanceSq - 1;
    }

    // 1=active, 2=arrived, 3=stalled, 4=expired, 5=interrupted,
    // 6=missing/ambiguous ownership. These are observations, not engine claims.
    static int RouteObservationResult(float now, float expires, float stalled, int living, int arrived, bool ambiguous, bool interrupted)
    {
        if (!(now >= 0 && expires > 0 && stalled >= 0))
        {
            return 6;
        }
        if (ambiguous || living < 1 || living > 6 || arrived < 0 || arrived > living)
        {
            return 6;
        }
        if (interrupted)
        {
            return 5;
        }
        if (now >= expires)
        {
            return 4;
        }
        if (arrived == living)
        {
            return 2;
        }
        if (stalled >= 15)
        {
            return 3;
        }
        return 1;
    }

    static bool ValidRouteMetadata(int purpose, int result, int planned, int completed, bool active)
    {
        if (planned == 0)
        {
            return purpose == 0 && result == 0 && completed == 0 && !active;
        }
        if (!(purpose >= 1 && purpose <= 2 && planned >= 1 && planned <= 3))
        {
            return false;
        }
        if (!(completed >= 0 && completed <= planned && result >= 1 && result <= 6))
        {
            return false;
        }
        if (result == 2)
        {
            return completed == planned && !active;
        }
        if (result == 1)
        {
            return completed < planned && active;
        }
        return !active;
    }

    static bool ValidAdoptionRecord(int stage, int state, bool conflicted)
    {
        if (stage == 1)
        {
            return state == 6 && !conflicted;
        }
        if (stage == 2)
        {
            return state >= 0 && state <= 6;
        }
        return stage == 3 && (state == 6 || state == 5) && conflicted;
    }

    static bool ValidAdoptionStagePair(int oldStage, int stage)
    {
        if (oldStage == 1)
        {
            return stage >= 1 && stage <= 3;
        }
        return oldStage >= 2 && oldStage <= 3 && stage == oldStage;
    }

    static bool CommitAdoptionRecord(int oldId, int id, int oldReserved, int reserved, int oldLiving, int living, int oldState, int state, int oldCreated, int created, int oldStage, int stage)
    {
        if (!(oldId == id && oldReserved == reserved && oldLiving == living))
        {
            return false;
        }
        if (!(oldCreated == created && oldState == 6 && state == 0))
        {
            return false;
        }
        return oldStage == 1 && stage == 2;
    }

    static int AdoptionOutcome(bool intentReadback, bool attempted, bool succeeded, bool releasing)
    {
        if (!intentReadback)
        {
            return 0;
        }
        if (!attempted)
        {
            return 2;
        }
        if (succeeded && !releasing)
        {
            return 2;
        }
        return 3;
    }

    static int AdoptionAfterRestart(int stage)
    {
        if (stage == 1)
        {
            return 3;
        }
        if (stage == 2 || stage == 3)
        {
            return stage;
        }
        return -1;
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
        if (!(schema == 2 && sameWorld && epoch > 0))
        {
            return false;
        }
        if (!(groups >= 0 && groups <= 2 && memberCap > 0 && memberCap <= 24))
        {
            return false;
        }
        return reserved >= 0 && reserved <= memberCap && savedAt > 0 && now >= savedAt;
    }

    static bool SuppressStrike(bool attack, bool target, bool reachable)
    {
        return attack && target && !reachable;
    }

    static bool ValidGroupRecord(int id, int index, int reserved, int living, int state, int created, int signal, int saved)
    {
        if (!(id == index + 1 && reserved >= 3 && reserved <= 6))
        {
            return false;
        }
        if (!(living >= 0 && living <= reserved && state >= 0 && state <= 6))
        {
            return false;
        }
        return created > 0 && created <= saved && signal >= created && signal <= saved;
    }

    static bool ValidGenerationPair(int newer, int older, int epoch, int oldEpoch, int saved, int oldSaved, int reserved, int oldReserved, int groups, int oldGroups)
    {
        return newer == older + 1 && epoch == oldEpoch && saved >= oldSaved && reserved >= oldReserved && groups >= oldGroups;
    }

    static bool RefundedGenerationPair(int newer, int older, int epoch, int oldEpoch, int saved, int oldSaved, int reserved, int oldReserved, int groups, int oldGroups)
    {
        bool sequence = newer == older + 1 && epoch == oldEpoch && saved >= oldSaved;
        bool refunded = reserved >= 0 && reserved < oldReserved && groups >= oldGroups;
        // LoadVerbatim verifies an actual new BudgetReleased transition before
        // this exception to the legacy monotonic ledger is authorized.
        return sequence && refunded;
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
        if (!(id == oldId && reserved == oldReserved && living <= oldLiving && created == oldCreated))
        {
            return false;
        }
        if (oldState == 5 && state != 5)
        {
            return false;
        }
        return oldState != 6 || state == 6 || state == 5;
    }

    static bool MayInvestigate(bool enabled, bool liveClue, bool engaged, bool injured, bool grouped, int attempts, float now, float nextAttempt)
    {
        return enabled && liveClue && !engaged && !injured && !grouped && attempts < 2 && now >= nextAttempt;
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

    // Single source for the native release retry ceiling; Navigation latches
    // its quarantine on this same value.
    static int MaxReleaseAttempts()
    {
        return 3;
    }

    static bool MayRetryRelease(int attempts, int now, int nextAttempt)
    {
        return attempts >= 0 && attempts < MaxReleaseAttempts() && now >= 0 && now >= nextAttempt;
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

    static bool MayRelay(float now, float rootObserved, float rootExpires, int hops, float strength, bool actualNativeEmission, bool alive)
    {
        if (!(now >= rootObserved && rootObserved >= 0 && rootExpires > now && rootExpires - rootObserved <= 30))
        {
            return false;
        }
        if (!(hops >= 0 && hops < 2 && strength >= 0.2 && strength <= 1))
        {
            return false;
        }
        return actualNativeEmission && alive;
    }

    static bool MayHearRelay(float now, float rootExpires, int hops, float strength, float distanceSq, int recipients, int recipientCap, bool duplicate, bool alive, bool clearGeometry, float nextAllowed)
    {
        if (!(now >= 0 && rootExpires > now && hops >= 0 && hops <= 2))
        {
            return false;
        }
        if (!(strength >= 0.2 && strength <= 1 && distanceSq >= 0.01 && distanceSq <= 225))
        {
            return false;
        }
        if (!(recipients >= 0 && recipientCap > 0 && recipientCap <= 12 && recipients < recipientCap))
        {
            return false;
        }
        return !duplicate && alive && clearGeometry && now >= nextAllowed;
    }

    static bool RootSlotReusable(float now, float expires)
    {
        return now >= 0 && expires >= 0 && now >= expires;
    }

    static bool PreferRoom(bool candidateClueRoom, bool currentClueRoom, float candidateDistanceSq, float currentDistanceSq, int candidateId, int currentId)
    {
        if (candidateClueRoom != currentClueRoom)
        {
            return candidateClueRoom;
        }
        if (candidateDistanceSq != currentDistanceSq)
        {
            return candidateDistanceSq < currentDistanceSq;
        }
        return candidateId < currentId;
    }

    static bool AdmitRoomCatalog(bool measured, bool sameBuildWorld, int revision, int anchors, int registered, int cap)
    {
        if (!(measured && sameBuildWorld && revision > 0))
        {
            return false;
        }
        if (!(anchors >= 1 && anchors <= 6 && registered >= 0))
        {
            return false;
        }
        return cap > 0 && cap <= 4 && registered < cap;
    }

    static bool ValidMemberIdentity(int b1, int b2, int b3, int b4, bool hasClass)
    {
        return hasClass && (b1 != 0 || b2 != 0 || b3 != 0 || b4 != 0);
    }

    static bool MayRecoverMember(bool enabled, bool loadedFromStorage, bool exactId, bool exactClass, bool duplicate, bool assigned, int state, int created, int now, int recovered, int expected)
    {
        if (!(enabled && loadedFromStorage && exactId && exactClass))
        {
            return false;
        }
        if (!(!duplicate && !assigned && state == 6))
        {
            return false;
        }
        if (!(created > 0 && now >= created && now - created < 3600))
        {
            return false;
        }
        return recovered >= 0 && expected > 0 && expected <= 6 && recovered < expected;
    }

    static bool RecoveryComplete(int recovered, int living, int reserved, bool conflict)
    {
        return !conflict && recovered > 0 && recovered == living && living <= reserved && reserved >= 3 && reserved <= 6;
    }
}
