// Exact identity reconciliation only. This does not make CE infected persistent.
// If the engine does not restore an infected with the same nonzero native ID,
// its reservation stays spent and unresolved. No substitute entity is spawned.
class HCHordeMemberId
{
    int B1;
    int B2;
    int B3;
    int B4;
    string Type;

    bool IsValid()
    {
        return Type.Length() <= 128 && HCInfectedPolicy.ValidMemberIdentity(B1, B2, B3, B4, Type.Length() > 0);
    }

    bool SameId(HCHordeMemberId other)
    {
        return other && B1 == other.B1 && B2 == other.B2 && B3 == other.B3 && B4 == other.B4;
    }

    static HCHordeMemberId Read(ZombieBase entity)
    {
        if (!entity)
            return null;
        HCHordeMemberId identity = new HCHordeMemberId;
        entity.GetPersistentID(identity.B1, identity.B2, identity.B3, identity.B4);
        identity.Type = entity.GetType();
        if (!identity.IsValid())
            return null;
        return identity;
    }
}

class HCHordeRecovery
{
    // Persist the complete roster or none of it. Partial IDs cannot authorize
    // inferred replacement. The source remains compatible with legacy no-ID
    // records, which stay unresolved on restart.
    static void Capture(array<HCInfectedActor> candidates, HCHordeRecord record)
    {
        record.MemberIds.Clear();
        foreach (HCInfectedActor actor : candidates)
        {
            HCHordeMemberId identity = HCHordeMemberId.Read(actor.InfectedEntity);
            if (!identity)
            {
                record.MemberIds.Clear();
                return;
            }
            foreach (HCHordeMemberId previous : record.MemberIds)
            {
                if (identity.SameId(previous))
                {
                    record.MemberIds.Clear();
                    record.RecoveryConflicted = true;
                    return;
                }
            }
            record.MemberIds.Insert(identity);
        }
    }

    static bool ValidateRoster(HCHordeRecord record)
    {
        if (!record.MemberIds || (record.MemberIds.Count() != 0 && record.MemberIds.Count() != record.Reserved))
            return false;
        for (int i = 0; i < record.MemberIds.Count(); i++)
        {
            HCHordeMemberId current = record.MemberIds[i];
            if (!current || !current.IsValid())
                return false;
            for (int j = 0; j < i; j++)
            {
                if (current.SameId(record.MemberIds[j]))
                    return false;
            }
        }
        return true;
    }

    static bool SameRoster(HCHordeRecord previous, HCHordeRecord current)
    {
        if (!ValidateRoster(previous) || !ValidateRoster(current) || previous.MemberIds.Count() != current.MemberIds.Count())
            return false;
        for (int i = 0; i < previous.MemberIds.Count(); i++)
        {
            if (!previous.MemberIds[i].SameId(current.MemberIds[i]) || previous.MemberIds[i].Type != current.MemberIds[i].Type)
                return false;
        }
        return !previous.RecoveryConflicted || current.RecoveryConflicted;
    }

    // One caller-budgeted actor, at most 2*6 roster entries and 24 registered
    // entities. Identity is compared only; native persistent-ID lookup is NOT
    // called outside its restricted engine event.
    static bool Reconcile(HCInfectedActor actor, HCInfectedSnapshot snapshot, array<ref HCInfectedActor> actors, bool enabled, int now)
    {
        if (!enabled || !actor || !actor.InfectedEntity || !actor.InfectedEntity.HCLoadedFromStorage() || !snapshot)
            return false;
        HCHordeMemberId identity = HCHordeMemberId.Read(actor.InfectedEntity);
        if (!identity)
            return false;
        foreach (HCHordeRecord record : snapshot.Groups)
        {
            if (record.State != 6 || record.RecoveryConflicted)
                continue;
            foreach (HCHordeMemberId member : record.MemberIds)
            {
                if (!identity.SameId(member))
                    continue;
                int recovered = 0;
                bool duplicate = false;
                foreach (HCInfectedActor registered : actors)
                {
                    if (registered.GroupId == record.Id && registered.InfectedEntity && registered.InfectedEntity.IsAlive())
                        recovered++;
                    if (registered != actor && registered.InfectedEntity && registered.InfectedEntity.IsAlive())
                    {
                        HCHordeMemberId other = HCHordeMemberId.Read(registered.InfectedEntity);
                        if (identity.SameId(other))
                            duplicate = true;
                    }
                }
                if (duplicate || identity.Type != member.Type || (actor.GroupId > 0 && actor.GroupId != record.Id))
                {
                    record.RecoveryConflicted = true;
                    return true;
                }
                if (actor.GroupId == record.Id)
                    return false;
                if (!HCInfectedPolicy.MayRecoverMember(enabled, true, true, identity.Type == member.Type, duplicate, actor.EverAssigned, record.State, record.CreatedUtc, now, recovered, record.Living))
                {
                    // An extra exact member beyond the saved living count is
                    // ambiguity, not capacity to grow a cohort.
                    if (recovered >= record.Living)
                    {
                        record.RecoveryConflicted = true;
                        return true;
                    }
                    return false;
                }
                actor.GroupId = record.Id;
                actor.EverAssigned = true;
                actor.RecoveredMember = true;
                recovered++;
                if (HCInfectedPolicy.RecoveryComplete(recovered, record.Living, record.Reserved, record.RecoveryConflicted))
                {
                    // Exact members are now accounted for. Keep state UNRESOLVED
                    // and never recreate a native pack from a JSON assertion.
                    // Native restored-agent/group/CE lifetime acceptance is the
                    // separate gate for reactivation, still deliberately closed.
                    Print("[HC Infected] exact restored member roster accounted for horde " + record.Id + "; native pack reactivation remains gated");
                }
                return true;
            }
        }
        return false;
    }
}
