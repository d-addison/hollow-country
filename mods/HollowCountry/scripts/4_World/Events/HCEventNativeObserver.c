class HCEventTarget
{
    string MissionId;
    ItemBase Item;
    ItemBase DeliveryContainer;
    Object Presence;
    ZombieBase Infected;
}
class HCEventNativeLease
{
    string Lease;
    ref HCEventMission Objective;
    PlayerBase DeliveredBy;
    string KillerId;
    ItemBase Item;
    ItemBase DeliveryContainer;
    Object Presence;
    ZombieBase Infected;
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
    bool ResetUnleasedTarget(string missionId)
    {
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Objective.Id == missionId) { return false; }
        }
        int index = m_Targets.Count() - 1;
        while (index >= 0)
        {
            if (m_Targets[index].MissionId == missionId) { m_Targets.Remove(index); }
            index = index - 1;
        }
        return true;
    }
    override void RecordDelivery(string lease, ItemBase item, PlayerBase participant, EntityAI destination)
    {
        if (!GetGame().IsServer()) { return; }
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Lease == lease && binding.Item == item)
            {
                binding.DeliveredBy = null;
                if (participant && destination == binding.DeliveryContainer && ContainerValid(binding.DeliveryContainer, binding.Objective))
                {
                    binding.DeliveredBy = participant;
                }
            }
        }
    }
    void RevokeDelivery(ItemBase item)
    {
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Item == item) { binding.DeliveredBy = null; }
        }
    }
    bool RegisterContainer(string missionId, ItemBase container)
    {
        HCEventTarget target = Target(missionId);
        if (!target || !container || container.IsPendingDeletion() || container.GetHierarchyRootPlayer() || container.GetHierarchyParent()) { return false; }
        if (target.DeliveryContainer) { return false; }
        target.DeliveryContainer = container;
        return true;
    }
    bool RegisterPresence(string missionId, Object landmark)
    {
        if (!GetGame().IsServer() || !landmark || landmark.IsPendingDeletion() || Target(missionId) || m_Targets.Count() >= 32) { return false; }
        HCEventTarget entry = new HCEventTarget;
        entry.MissionId = missionId;
        entry.Presence = landmark;
        m_Targets.Insert(entry);
        return true;
    }
    bool RegisterInfected(string missionId, ZombieBase infected)
    {
        if (!GetGame().IsServer() || !infected || !infected.IsAlive() || infected.IsPendingDeletion() || Target(missionId) || m_Targets.Count() >= 32) { return false; }
        foreach (HCEventTarget prior : m_Targets)
        {
            if (prior.Infected == infected) { return false; }
        }
        HCEventTarget entry = new HCEventTarget;
        entry.MissionId = missionId;
        entry.Infected = infected;
        m_Targets.Insert(entry);
        return true;
    }
    override void RecordKill(string lease, ZombieBase infected, string participantId)
    {
        if (!GetGame().IsServer() || !infected || infected.IsAlive() || !HCEventDirector.TextValid(participantId, 96)) { return; }
        foreach (HCEventNativeLease binding : m_Leases)
        {
            if (binding.Lease == lease && binding.Infected == infected && binding.KillerId == "")
            {
                binding.KillerId = participantId;
            }
        }
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
        if (!HCEventQualification.Admitted() || !GetGame().IsServer() || !mission || !HCEventRuntimePolicy.MissionValid(mission, mission.WorldName))
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
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            return target && target.Presence && !target.Presence.IsPendingDeletion() && target.Presence.GetType() == mission.AnchorClass && Near(target.Presence.GetPosition(), mission.Source, mission.Radius);
        }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR)
        {
            return target && target.Infected && target.Infected.IsAlive() && !target.Infected.IsPendingDeletion() && Near(target.Infected.GetPosition(), mission.Source, mission.Radius);
        }
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            if (!target || !ContainerValid(target.DeliveryContainer, mission)) { return false; }
        }
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
            HCEventTarget target = Target(mission.Id);
            binding.Item = target.Item;
            binding.DeliveryContainer = target.DeliveryContainer;
            binding.Presence = target.Presence;
            binding.Infected = target.Infected;
        }
        m_Leases.Insert(binding);
        return true;
    }
    bool ContainerValid(ItemBase container, HCEventMission mission)
    {
        return container && !container.IsPendingDeletion() && !container.IsRuined() && !container.GetHierarchyRootPlayer() && !container.GetHierarchyParent() && container.GetType() == mission.ContainerClass && Near(container.GetPosition(), mission.Destination, mission.Radius);
    }
    override void Forget(string lease, PlayerBase participant)
    {
        foreach (HCEventNativeLease carrierLease : m_Leases)
        {
            if (carrierLease.Lease == lease && carrierLease.DeliveredBy == participant) { carrierLease.DeliveredBy = null; }
        }
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
            if (mission.Family == HCEventFamily.PRESENCE)
            {
                observed = selected.Presence && !selected.Presence.IsPendingDeletion() && selected.Presence.GetType() == mission.AnchorClass && Near(selected.Presence.GetPosition(), mission.Source, mission.Radius) && Near(participant.GetPosition(), mission.Source, mission.Radius);
            }
            else
            {
                if (mission.Family == HCEventFamily.INFECTED_CLEAR)
                {
                    observed = selected.Infected && !selected.Infected.IsPendingDeletion() && !selected.Infected.IsAlive() && selected.KillerId == identity;
                }
                else
                {
                    observed = SupplyObserved(selected, participant);
                }
            }
        }
        if (!observed)
        {
            return null;
        }
        // A lease is session:run; without the separator there is no session to report.
        int sessionEnd = run.Lease.LastIndexOf(":");
        if (sessionEnd < 1)
        {
            return null;
        }
        HCEventObjectiveEvidence result = new HCEventObjectiveEvidence;
        result.Observed = true;
        result.Lease = run.Lease;
        // Runtime supplies session via the durable lease, independently checked.
        result.Session = run.Lease.Substring(0, sessionEnd);
        result.ParticipantId = identity;
        result.Sequence = 1;
        result.Token = run.Lease + ":objective";
        return result;
    }
    bool SupplyObserved(HCEventNativeLease binding, PlayerBase participant)
    {
        HCEventMission mission = binding.Objective;
        ItemBase item = binding.Item;
        if (!item || item.IsPendingDeletion() || item.IsRuined() || item.GetType() != mission.ItemClass) { return false; }
        if (mission.Family == HCEventFamily.DELIVERY)
        {
            return binding.DeliveredBy == participant && ContainerValid(binding.DeliveryContainer, mission) && item.GetHierarchyParent() == binding.DeliveryContainer && Near(participant.GetPosition(), mission.Destination, mission.Radius);
        }
        // Recovery and salvage expose only an existing native item; no grant.
        return item.GetHierarchyRootPlayer() == participant && (mission.Family == HCEventFamily.RECOVERY || Near(participant.GetPosition(), mission.Source, mission.Radius));
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
