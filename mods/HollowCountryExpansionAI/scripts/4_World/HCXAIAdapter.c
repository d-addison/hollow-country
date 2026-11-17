// Original calls against pinned Expansion 1.9.84. Qualification remains pending.
// Trusted server ports. No RPC/JSON capability flag installs these hooks.
// Begin/MemberCreated/MemberGone/End must be durable, idempotent ledger operations.
// False is uncertain, never permission to free reservations or repeat creation.
class HCXAIHooks
{
    HCXAIAdmission Admission(string worldSession) { return null; }
    bool RouteQualified(string surveySha256, string loadoutSha256) { return false; }
    bool BeginLease(string lease, string session, string missionId, int actors, int items) { return false; }
    bool MemberCreated(string lease, int index, Object actor) { return false; }
    bool MemberGone(string lease, int index) { return false; }
    bool EndLease(string lease) { return false; }
    HCObserverTransitionInput Observers(string worldSession, string lease, int index, Object actor, vector position) { return null; }
}
class HCXAIService
{
    protected static ref HCXAIHooks s_Hooks;
    protected static ref HCXAIAdapter s_Adapter;
    static bool InstallHooks(HCXAIHooks hooks)
    {
        if (!GetGame() || !GetGame().IsServer() || s_Adapter || !hooks) { return false; }
        s_Hooks = hooks;
        return true;
    }
    static HCXAIHooks Hooks() { return s_Hooks; }
    static HCXAIAdapter Adapter() { return s_Adapter; }
    static bool Bind(HCXAIAdapter adapter)
    {
        if (s_Adapter && s_Adapter != adapter && s_Adapter.HasReservations()) { return false; }
        s_Adapter = adapter;
        return true;
    }
}
class HCXAIAdapter extends HCModule
{
    protected ref HCXAIProfile m_Profile;
    protected ref HCXAIHooks m_Hooks;
    protected bool m_Accepting;
    protected bool m_Starting;
    protected string m_Status = "not initialized";
    protected string m_Build;
    protected ref array<ref HCXAILease> m_Leases = new array<ref HCXAILease>();
    protected int m_ReservedActors;
    protected int m_ReservedItems;
    protected int m_ReservedGroups;
    protected int m_Cursor;
    protected int m_LastNow = -1;
    protected int m_LastReceiptSequence;
    protected int m_LastReceiptAt = -1;

    override string GetName() { return "optional-expansion-human-ai"; }
    // Invoke startup to create/read the user's preference even without admission.
    override bool IsEnabled(HCSettings settings) { return true; }
    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (!HCXAIService.Bind(this))
        {
            Print("[HC Expansion AI] unresolved prior reservations; startup rejected");
            return;
        }
        HCXAIProfile profile = HCXAIStore.Load();
        this.Install(profile, HCXAIService.Hooks());
        Print("[HC Expansion AI] " + m_Status);
    }
    bool Install(HCXAIProfile profile, HCXAIHooks hooks)
    {
        if (!GetGame() || !GetGame().IsServer() || m_Profile || this.HasReservations()) { return false; }
        m_Status = "enabled preference; invalid or missing operator policy";
        if (profile && !profile.Enabled) { m_Status = "disabled by operator"; }
        if (!HCXAIRules.ProfileValid(profile)) { return false; }
        m_Status = "enabled preference; trusted artifact/observer/ownership hooks missing";
        if (!hooks) { return false; }
        m_Profile = HCXAIStore.Freeze(profile);
        if (!m_Profile || !HCXAIRules.ProfileValid(m_Profile)) { return false; }
        m_Hooks = hooks;
        m_Build = HCXAIStore.NativeBuild();
        m_Accepting = true;
        m_LastNow = GetGame().GetTime();
        if (!this.Ready(m_Profile.WorldName))
        {
            m_Accepting = false;
            m_Status = "enabled preference; pinned live prerequisites rejected";
            return false;
        }
        m_Status = "experimental adapter prerequisites observed; gameplay qualification pending";
        return true;
    }
    bool HasReservations() { return m_ReservedGroups > 0; }
    bool NativeGlobalsFair()
    {
        if (eAIBase.s_eAI_UnlimitedReload != 0 || eAIBase.s_eAI_UnlimitedReloadAll != 0) { return false; }
        if (!GetExpansionSettings() || !GetExpansionSettings().GetAI()) { return false; }
        ExpansionAISettings settings = GetExpansionSettings().GetAI();
        if (settings.EnableFlankingOutsideCombat || settings.CanRecruitFriendly || settings.CanRecruitGuards) { return false; }
        return settings.DamageMultiplier == 1 && settings.DamageReceivedMultiplier == 1;
    }
    bool Prerequisites()
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Profile || !m_Hooks) { return false; }
        int now = GetGame().GetTime();
        if (now < 0 || now < m_LastNow || m_Profile.BuildVersion != m_Build) { return false; }
        if (GetGame().GetWorldName() != m_Profile.WorldName || !this.NativeGlobalsFair()) { return false; }
        HCXAIAdmission receipt = m_Hooks.Admission(m_Profile.WorldSession);
        if (!HCXAIRules.ReceiptValid(m_Profile, receipt, now)) { return false; }
        if (receipt.Sequence < m_LastReceiptSequence || receipt.ObservedAtMs < m_LastReceiptAt) { return false; }
        if (receipt.Sequence == m_LastReceiptSequence && receipt.ObservedAtMs != m_LastReceiptAt) { return false; }
        m_LastReceiptSequence = receipt.Sequence;
        m_LastReceiptAt = receipt.ObservedAtMs;
        return true;
    }
    bool Ready(string world)
    {
        return m_Accepting && m_Profile && world == m_Profile.WorldName && this.Prerequisites();
    }
    HCXAILease FindLease(string id)
    {
        foreach (HCXAILease lease : m_Leases)
        {
            if (lease.Id == id) { return lease; }
        }
        return null;
    }
    HCXAIMission FindMission(string id)
    {
        foreach (HCXAIMission mission : m_Profile.Missions)
        {
            if (mission.MissionId == id) { return mission; }
        }
        return null;
    }
    bool StartLease(string id, string session, string missionId, vector anchor, int actorCap)
    {
        if (m_Starting) { return false; }
        m_Starting = true;
        bool result = this.StartLeaseWork(id, session, missionId, anchor, actorCap);
        m_Starting = false;
        return result;
    }
    protected bool StartLeaseWork(string id, string session, string missionId, vector anchor, int actorCap)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXAIRules.Token(id) || !HCXAIRules.Token(session)) { return false; }
        if (!m_Profile || !this.Ready(m_Profile.WorldName)) { return false; }
        HCXAILease prior = this.FindLease(id);
        if (prior)
        {
            return !prior.Retiring && !prior.Failed && !prior.Released && prior.IntentConfirmed && prior.Session == session && prior.MissionId == missionId && prior.Anchor == anchor && prior.RequestedCap == actorCap;
        }
        if (actorCap < 1 || actorCap > m_Profile.MaxActors || m_Leases.Count() >= m_Profile.MaxLeaseHistory) { return false; }
        HCXAIMission mission = this.FindMission(missionId);
        if (!mission || anchor != mission.Anchor || mission.Spawns.Count() > actorCap) { return false; }
        if (!m_Hooks.RouteQualified(mission.SurveySha256, mission.LoadoutSha256)) { return false; }
        int actors = mission.Spawns.Count();
        int items = actors * mission.Equipment.Count();
        if (m_ReservedGroups >= m_Profile.MaxGroups || m_ReservedActors + actors > m_Profile.MaxActors || m_ReservedItems + items > m_Profile.MaxItems) { return false; }
        eAIFaction faction = eAIFaction.Create(mission.FactionName);
        if (!faction || faction.IsInvincible() || faction.IsObserver() || faction.IsPassive() || faction.HasUnlimitedStamina()) { return false; }
        if (faction.GetMeleeDamageMultiplier() != 1 || faction.GetMeleeYeetForce() != 0) { return false; }
        HCXAILease lease = new HCXAILease();
        lease.Id = id;
        lease.Session = session;
        lease.MissionId = missionId;
        lease.Anchor = anchor;
        lease.RequestedCap = actorCap;
        lease.Mission = mission;
        lease.StartedAtMs = GetGame().GetTime();
        lease.ActorReservation = actors;
        lease.ItemReservation = items;
        int index = 0;
        while (index < actors)
        {
            HCXAIActorSlot slot = new HCXAIActorSlot();
            HCObserverTransitionGate.Configure(slot.SpawnGate, m_Profile.ObserverPolicy);
            HCObserverTransitionGate.Configure(slot.RetireGate, m_Profile.ObserverPolicy);
            lease.Slots.Insert(slot);
            index++;
        }
        // Publish reservation before the first uncertain external side effect.
        m_Leases.Insert(lease);
        m_ReservedGroups++;
        m_ReservedActors += actors;
        m_ReservedItems += items;
        lease.IntentConfirmed = m_Hooks.BeginLease(id, session, missionId, actors, items);
        if (!lease.IntentConfirmed)
        {
            lease.Failed = true;
            lease.Retiring = true;
            return false;
        }
        lease.Group = eAIGroup.CreateGroup(faction);
        if (!lease.Group)
        {
            lease.Failed = true;
            lease.Retiring = true;
            return false;
        }
        lease.Group.SetWaypointBehaviour(eAIWaypointBehavior.HALT);
        foreach (vector waypoint : mission.Waypoints) { lease.Group.AddWaypoint(waypoint); }
        return true;
    }
    bool Equip(eAIBase actor, HCXAIMission mission)
    {
        foreach (HCXAIEquipment spec : mission.Equipment)
        {
            EntityAI item;
            if (spec.InHands) { item = actor.GetHumanInventory().CreateInHands(spec.ClassName); }
            else { item = actor.GetInventory().CreateInInventory(spec.ClassName); }
            if (!item) { return false; }
            Magazine magazine = Magazine.Cast(item);
            if (spec.IsMagazine)
            {
                if (!magazine || spec.AmmoCount > magazine.GetAmmoMax()) { return false; }
                magazine.ServerSetAmmoCount(spec.AmmoCount);
                if (magazine.GetAmmoCount() != spec.AmmoCount) { return false; }
            }
            else if (magazine) { return false; }
        }
        return true;
    }
    bool Quiet(HCXAILease lease, HCXAIActorSlot slot, int index, bool spawning, int now)
    {
        vector position = lease.Mission.Spawns[index];
        if (slot.Handle) { position = slot.Handle.GetPosition(); }
        HCObserverTransitionInput observation = m_Hooks.Observers(m_Profile.WorldSession, lease.Id, index, slot.Handle, position);
        HCObserverTransitionState gate = slot.RetireGate;
        if (spawning) { gate = slot.SpawnGate; }
        if (!observation) { return false; }
        return HCObserverTransitionGate.Evaluate(gate, observation, now * 0.001) == 3;
    }
    void StepLease(HCXAILease lease, int now)
    {
        if (!GetGame() || !GetGame().IsServer() || !lease || lease.Busy) { return; }
        lease.Busy = true;
        this.StepLeaseWork(lease, now);
        lease.Busy = false;
    }
    protected void StepLeaseWork(HCXAILease lease, int now)
    {
        if (!lease || lease.Released || !m_Profile || !m_Hooks || now < lease.StartedAtMs) { return; }
        if (now - lease.StartedAtMs > m_Profile.MaxLeaseMs) { lease.Retiring = true; }
        if (!lease.Retiring && !this.Ready(m_Profile.WorldName))
        {
            lease.Failed = true;
            lease.Retiring = true;
        }
        if (!lease.Retiring && (!lease.Group || lease.Group.m_Leave))
        {
            lease.Failed = true;
            lease.Retiring = true;
        }
        int index = lease.Cursor;
        lease.Cursor = (lease.Cursor + 1) % lease.Slots.Count();
        HCXAIActorSlot slot = lease.Slots[index];
        if (lease.Retiring)
        {
            if (!slot.Attempted) { slot.Gone = true; }
            else if (slot.Handle)
            {
                // Neither Stop nor pressure grants immunity or visible deletion.
                if (!slot.DeleteRequested && this.Prerequisites())
                {
                    if ((!lease.Group || !lease.Group.IsInCombat()) && this.Quiet(lease, slot, index, false, now))
                    {
                        slot.DeleteRequested = true;
                        slot.Handle.Delete();
                    }
                }
            }
            else if (slot.DeleteObserved && m_Hooks.MemberGone(lease.Id, index)) { slot.Gone = true; }
            bool allGone = true;
            foreach (HCXAIActorSlot member : lease.Slots)
            {
                if (!member.Gone) { allGone = false; }
            }
            if (allGone && m_Hooks.EndLease(lease.Id))
            {
                if (lease.Group && lease.Group.Count() == 0) { lease.Group.Delete(); }
                lease.Released = true;
                m_ReservedGroups--;
                m_ReservedActors -= lease.ActorReservation;
                m_ReservedItems -= lease.ItemReservation;
            }
            return;
        }
        if (slot.Handle)
        {
            eAIBase existing = eAIBase.Cast(slot.Handle);
            if (!existing || !existing.HCXAI_Fair() || existing.GetGroup() != lease.Group)
            {
                lease.Failed = true;
                lease.Retiring = true;
            }
        }
        if (slot.Attempted) { return; }
        if (!m_Hooks.RouteQualified(lease.Mission.SurveySha256, lease.Mission.LoadoutSha256))
        {
            lease.Failed = true;
            lease.Retiring = true;
            return;
        }
        if (!this.Quiet(lease, slot, index, true, now)) { return; }
        // Never retry creation once the native factory has been entered.
        slot.Attempted = true;
        slot.Handle = GetGame().CreateObjectEx(lease.Mission.ActorClass, lease.Mission.Spawns[index], ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_NOSURFACEALIGN);
        if (!slot.Handle)
        {
            slot.DeleteObserved = true;
            lease.Failed = true;
            lease.Retiring = true;
            return;
        }
        eAIBase actor = eAIBase.Cast(slot.Handle);
        if (!actor)
        {
            lease.Failed = true;
            lease.Retiring = true;
            return;
        }
        actor.SetGroup(lease.Group);
        actor.eAI_SetUnlimitedReload(0);
        actor.eAI_SetEnableFlankingOutsideCombat(0);
        actor.eAI_SetDamageMultiplier(1);
        actor.eAI_SetDamageReceivedMultiplier(1);
        actor.eAI_SetLootingBehavior(0);
        if (!actor.HCXAI_Fair() || !this.Equip(actor, lease.Mission) || !m_Hooks.MemberCreated(lease.Id, index, actor))
        {
            lease.Failed = true;
            lease.Retiring = true;
            return;
        }
        bool complete = true;
        foreach (HCXAIActorSlot candidate : lease.Slots)
        {
            if (!candidate.Attempted) { complete = false; }
        }
        if (complete) { lease.Group.SetWaypointBehaviour(eAIWaypointBehavior.LOOP); }
    }
    bool StopLease(string id)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        HCXAILease lease = this.FindLease(id);
        if (!lease) { return false; }
        lease.Retiring = true;
        return true;
    }
    bool Gone(string id)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        HCXAILease lease = this.FindLease(id);
        return lease && lease.Released;
    }
    void RecordDelete(Object actor)
    {
        if (!GetGame() || !GetGame().IsServer() || !actor) { return; }
        foreach (HCXAILease lease : m_Leases)
        {
            foreach (HCXAIActorSlot slot : lease.Slots)
            {
                if (slot.Handle == actor) { slot.DeleteObserved = true; }
            }
        }
    }
    void RecordDeath(Object actor, string participantId)
    {
        if (!GetGame() || !GetGame().IsServer() || !actor || actor.IsAlive() || !HCXAIRules.Token(participantId)) { return; }
        foreach (HCXAILease lease : m_Leases)
        {
            if (lease.Released || lease.Retiring) { continue; }
            int index = 0;
            foreach (HCXAIActorSlot slot : lease.Slots)
            {
                if (slot.Handle == actor && !slot.DeathObserved)
                {
                    slot.DeathObserved = true;
                    HCXAIKill kill = new HCXAIKill();
                    kill.ParticipantId = participantId;
                    kill.Token = lease.Id + ":kill:" + index.ToString();
                    lease.Kills.Insert(kill);
                }
                index++;
            }
        }
    }
    HCEventObjectiveEvidence ObserveLease(string id, PlayerBase participant)
    {
        if (!GetGame() || !GetGame().IsServer() || !participant || !participant.IsAlive() || !participant.GetIdentity()) { return null; }
        HCXAILease lease = this.FindLease(id);
        if (!lease || lease.Retiring || lease.Released) { return null; }
        string participantId = participant.GetIdentity().GetId();
        if (!lease.ReceiptToken)
        {
            foreach (HCXAIKill kill : lease.Kills)
            {
                if (kill.ParticipantId == participantId)
                {
                    lease.ReceiptToken = kill.Token;
                    lease.ReceiptParticipant = participantId;
                    lease.Sequence = 1;
                    break;
                }
            }
        }
        if (!lease.ReceiptToken || lease.ReceiptParticipant != participantId) { return null; }
        HCEventObjectiveEvidence evidence = new HCEventObjectiveEvidence();
        evidence.Observed = true;
        evidence.Lease = lease.Id;
        evidence.Session = lease.Session;
        evidence.ParticipantId = participantId;
        evidence.Sequence = lease.Sequence;
        evidence.Token = lease.ReceiptToken;
        return evidence;
    }
    override void OnTick(float deltaTime)
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Profile) { return; }
        int now = GetGame().GetTime();
        if (now < 0 || now < m_LastNow)
        {
            m_Accepting = false;
            m_Status = "clock rollback; reservations retained for reconciliation";
            return;
        }
        if (now == m_LastNow) { return; }
        m_LastNow = now;
        int work = 0;
        while (work < m_Profile.MaxTickWork && m_Leases.Count() > 0)
        {
            m_Cursor = m_Cursor % m_Leases.Count();
            this.StepLease(m_Leases[m_Cursor], now);
            m_Cursor++;
            work++;
        }
    }
    override void OnStop()
    {
        m_Accepting = false;
        foreach (HCXAILease lease : m_Leases)
        {
            lease.Retiring = true;
        }
        if (this.HasReservations())
        {
            Print("[HC Expansion AI] stop requested; unresolved actors/items remain journal obligations");
        }
    }
}
class HCExpansionAIEventProvider extends HCEventAIProvider
{
    override bool Ready(string world)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        return adapter && adapter.Ready(world);
    }
    override bool Start(string lease, string session, string missionId, vector anchor, int actorCap)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        return adapter && adapter.StartLease(lease, session, missionId, anchor, actorCap);
    }
    override HCEventObjectiveEvidence Observe(string lease, PlayerBase participant)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (!adapter) { return null; }
        return adapter.ObserveLease(lease, participant);
    }
    override bool Stop(string lease)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        return adapter && adapter.StopLease(lease);
    }
    override bool Gone(string lease)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        return adapter && adapter.Gone(lease);
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXAIAdapter());
    }
}
// Narrow original observation/getter extension; no provider source is replaced.
modded class eAIBase
{
    bool HCXAI_Fair()
    {
        return this.GetAllowDamage() && !m_eAI_EnableFlankingOutsideCombat && m_eAI_UnlimitedReload == 0 && !m_eAI_IsUnlimitedReloadAll && m_eAI_DamageMultiplier == 1 && m_eAI_DamageReceivedMultiplier == 1 && m_eAI_HeadshotResistance == 0;
    }
    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        HCXAIAdapter adapter = HCXAIService.Adapter();
        EntityAI source = EntityAI.Cast(killer);
        if (!adapter || !source) { return; }
        PlayerBase participant = PlayerBase.Cast(source.GetHierarchyRootPlayer());
        if (participant && participant.GetIdentity()) { adapter.RecordDeath(this, participant.GetIdentity().GetId()); }
    }
    override void EEDelete(EntityAI parent)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (adapter) { adapter.RecordDelete(this); }
        super.EEDelete(parent);
    }
}
