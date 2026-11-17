class HCEventTarget
{
    string MissionId;
    ItemBase Item;
}
class HCEventNativeLease
{
    string Lease;
    ref HCEventMission Objective;
    ItemBase Item;
}
class HCEventDwell
{
    string Lease;
    PlayerBase Player;
    int Since;
    int Last;
}
// Server-owned references only. No item is created, moved, consumed or deleted.
// Targets must be registered from a reviewed server site by the integration.
class HCEventNativeObserver : HCEventObjectiveProvider
{
    protected ref array<ref HCEventTarget> m_Targets = new array<ref HCEventTarget>();
    protected ref array<ref HCEventNativeLease> m_Leases = new array<ref HCEventNativeLease>();
    protected ref array<ref HCEventDwell> m_Dwells = new array<ref HCEventDwell>();

    static string Identity(PlayerBase player)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || player.IsPendingDeletion() || !player.IsAlive())
        {
            return "";
        }
        PlayerIdentity identity = player.GetIdentity();
        if (!identity || !HCEventDirector.TextValid(identity.GetId(), 96))
        {
            return "";
        }
        return identity.GetId();
    }
    bool RegisterTarget(string missionId, ItemBase item)
    {
        if (!GetGame().IsServer() || !HCEventDirector.TextValid(missionId, 64) || !item || item.IsPendingDeletion())
        {
            return false;
        }
        if (m_Targets.Count() >= 32)
        {
            return false;
        }
        foreach (HCEventTarget target : m_Targets)
        {
            if (target.MissionId == missionId || target.Item == item)
            {
                return false;
            }
        }
        HCEventTarget entry = new HCEventTarget;
        entry.MissionId = missionId;
        entry.Item = item;
        m_Targets.Insert(entry);
        return true;
    }
    bool Near(vector position, vector anchor, float radius)
    {
        return HCEventRuntimePolicy.PositionValid(position) && vector.DistanceSq(position, anchor) <= radius * radius;
    }
    HCEventTarget Target(string missionId)
    {
        foreach (HCEventTarget target : m_Targets)
        {
            if (target.MissionId == missionId)
            {
                return target;
            }
        }
        return null;
    }
    override bool Ready(HCEventMission mission)
    {
        if (!GetGame().IsServer() || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName))
        {
            return false;
        }
        if (mission.Family == HCEventFamily.INVESTIGATION)
        {
            return true;
        }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            return false;
        }
        HCEventTarget target = Target(mission.Id);
        if (!target || !target.Item || target.Item.IsPendingDeletion() || target.Item.IsRuined())
        {
            return false;
        }
        if (target.Item.GetType() != mission.ItemClass || target.Item.GetHierarchyRootPlayer())
        {
            return false;
        }
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Item == target.Item)
            {
                return false;
            }
        }
        return Near(target.Item.GetPosition(), mission.Source, mission.Radius);
    }
    override bool Prepare(string lease, HCEventMission mission)
    {
        if (!HCEventDirector.TextValid(lease, 128) || m_Leases.Count() >= 32 || !Ready(mission))
        {
            return false;
        }
        foreach (HCEventNativeLease existing : m_Leases)
        {
            if (existing.Lease == lease)
            {
                return false;
            }
        }
        HCEventNativeLease binding = new HCEventNativeLease;
        binding.Lease = lease;
        binding.Objective = mission;
        if (mission.Family != HCEventFamily.INVESTIGATION)
        {
            binding.Item = Target(mission.Id).Item;
        }
        m_Leases.Insert(binding);
        return true;
    }
    override void Forget(string lease, PlayerBase participant)
    {
        int index = m_Dwells.Count() - 1;
        while (index >= 0)
        {
            HCEventDwell dwell = m_Dwells[index];
            if (dwell.Lease == lease && dwell.Player == participant)
            {
                m_Dwells.Remove(index);
            }
            index = index - 1;
        }
    }
    override HCEventObjectiveEvidence Observe(HCEventRun run, PlayerBase participant, int now)
    {
        if (!run || now < 0 || now > 1000000000)
        {
            return null;
        }
        string identity = Identity(participant);
        if (identity == "")
        {
            Forget(run.Lease, participant);
            return null;
        }
        HCEventNativeLease selected;
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Lease == run.Lease)
            {
                selected = binding;
            }
        }
        if (!selected || selected.Objective.Id != run.Objective.Id)
        {
            return null;
        }
        HCEventMission mission = selected.Objective;
        bool observed = false;
        if (mission.Family == HCEventFamily.INVESTIGATION)
        {
            if (!Near(participant.GetPosition(), mission.Source, mission.Radius))
            {
                Forget(run.Lease, participant);
                return null;
            }
            HCEventDwell current;
            foreach (HCEventDwell dwell : m_Dwells)
            {
                if (dwell.Lease == run.Lease && dwell.Player == participant)
                {
                    current = dwell;
                }
            }
            if (!current)
            {
                if (m_Dwells.Count() >= 2880)
                {
                    return null;
                }
                current = new HCEventDwell;
                current.Lease = run.Lease;
                current.Player = participant;
                current.Since = now;
                current.Last = now;
                m_Dwells.Insert(current);
            }
            // Missing samples, rollback and disconnection never count as dwell.
            if (now < current.Last || now - current.Last > 5)
            {
                current.Since = now;
            }
            current.Last = now;
            observed = now - current.Since >= mission.DwellSeconds;
        }
        else
        {
            ItemBase item = selected.Item;
            if (!item || item.IsPendingDeletion() || item.IsRuined() || item.GetType() != mission.ItemClass)
            {
                return null;
            }
            if (item.GetHierarchyRootPlayer() != participant)
            {
                return null;
            }
            if (mission.Family == HCEventFamily.DELIVERY)
            {
                observed = Near(participant.GetPosition(), mission.Destination, mission.Radius);
            }
            else
            {
                // Recovery confirms custody; static salvage also requires
                // collection at its surveyed site. Neither transforms loot.
                observed = mission.Family == HCEventFamily.RECOVERY || Near(participant.GetPosition(), mission.Source, mission.Radius);
            }
        }
        if (!observed)
        {
            return null;
        }
        HCEventObjectiveEvidence result = new HCEventObjectiveEvidence;
        result.Observed = true;
        result.Lease = run.Lease;
        // Runtime supplies session via the durable lease, independently checked.
        result.Session = run.Lease.Substring(0, run.Lease.LastIndexOf(":"));
        result.ParticipantId = identity;
        result.Sequence = 1;
        result.Token = run.Lease + ":objective";
        return result;
    }
    override bool Release(string lease)
    {
        if (!GetGame().IsServer())
        {
            return false;
        }
        int index = m_Leases.Count() - 1;
        while (index >= 0)
        {
            HCEventNativeLease binding = m_Leases[index];
            if (binding.Lease == lease)
            {
                m_Leases.Remove(index);
            }
            index = index - 1;
        }
        index = m_Dwells.Count() - 1;
        while (index >= 0)
        {
            if (m_Dwells[index].Lease == lease)
            {
                m_Dwells.Remove(index);
            }
            index = index - 1;
        }
        return true;
    }
}
