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
        // Install once per process, before any adapter binds; never on a client.
        if (!GetGame() || !GetGame().IsServer() || s_Adapter || s_Hooks || !hooks) { return false; }
        s_Hooks = hooks;
        return true;
    }
    // Server start installs the local port only when Expansion AI is loaded.
    static bool InstallLocalHooks()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Scripts") || !GetExpansionSettings()) { return false; }
        return HCXAIService.InstallHooks(new HCXAILocalHooks());
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
    protected ref HCXAIJournal m_Journal;
    protected bool m_Accepting;
    protected bool m_Starting;
    protected string m_Status = "not initialized";
    protected string m_Build;
    protected ref array<ref HCXAILease> m_Leases = new array<ref HCXAILease>();
    protected ref array<string> m_PrunedIds = new array<string>();
    protected bool m_PrunedCapLogged;
    protected int m_ReservedActors;
    protected int m_ReservedItems;
    protected int m_ReservedGroups;
    protected int m_Cursor;
    protected int m_LastNow = -1;
    protected int m_LastReceiptSequence;
    protected int m_LastReceiptAt = -1;
    protected bool m_ReadinessLogged;
    protected ref HCXAISiteDirector m_Sites;
    // AI_ENCOUNTER on the director's own qualified patrols (HCXAIEncounters.c).
    protected ref HCXAIEncounters m_Encounters;
    protected ref HCXAICampRoutine m_CampRoutine;

    override string GetName() { return "optional-expansion-human-ai"; }
    // Invoke startup to create/read the user's preference even without admission.
    override bool IsEnabled(HCSettings settings) { return true; }
    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        // HC sites (patrols, scavengers, holdouts) admit themselves from engine
        // observations; they do not depend on the lease profile below.
        // Seed the V2 encounters flag from the preference before the director binds
        // sites, so checkpoint sites are kept even though HCXLivingModule starts later.
        HCXAIQualification.SetEncountersEnabled(settings && settings.EnableEncounters);
        m_Sites = new HCXAISiteDirector();
        m_Sites.Start();
        // AI_ENCOUNTER readiness comes from the director's live state. The lease
        // spawner path (expansion-ai.json profile, local hook port, trusted
        // receipt verifiers) is retired: it is no longer installed or loaded.
        m_Encounters = new HCXAIEncounters();
        m_Encounters.Open();
        m_CampRoutine = new HCXAICampRoutine();
        m_CampRoutine.Open(settings);
        if (!HCXAIService.Bind(this))
        {
            Print("[HC Expansion AI] unresolved prior reservations; startup rejected");
            return;
        }
        this.LogAddonChecks();
        m_Status = "lease spawner retired; AI_ENCOUNTER binds HC site patrols";
        Print("[HC Expansion AI] retired: expansion-ai.json lease profile, local hook port and receipt verifiers are not loaded; AI_ENCOUNTER gates on site director run + per-process session + a qualified site patrol");
        this.LogReadiness("server start");
    }
    bool ExpansionAISettingsLoaded()
    {
        return GetExpansionSettings() && GetExpansionSettings().GetAI() && GetExpansionSettings().GetAI().IsLoaded();
    }
    // One AI_ENCOUNTER readiness line at start and once more when the
    // encounters settle (armed, or refused with a reason).
    void LogReadiness(string trigger)
    {
        if (!m_Encounters || !m_Sites) { return; }
        Print(m_Sites.HCLocalitySummary());
        if (m_Encounters.Settled()) { m_ReadinessLogged = true; }
        bool ready = m_Encounters.Ready(GetGame().GetWorldName());
        int qualified = m_Encounters.QualifiedCount();
        bool loaded = this.ExpansionAISettingsLoaded();
        string settingsState = "not loaded";
        if (loaded) { settingsState = "loaded"; }
        string globals = this.GlobalsProblem();
        if (globals == "") { globals = "fair"; }
        Print("[HC Expansion AI] readiness (" + trigger + ") AI_ENCOUNTER Ready=" + ready.ToString() + "; encounters=" + m_Encounters.State() + "; sites=" + m_Sites.Phase() + "; qualified_patrols=" + qualified.ToString() + "; expansion_ai_settings=" + settingsState + "; globals=" + globals + "; expansion-ai.json and receipt verifiers retired");
    }
    void LogAddonChecks()
    {
        bool provider = GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Scripts");
        bool animations = GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Animations");
        Print("[HC Expansion AI] installed CfgPatches DayZExpansion_AI_Scripts=" + provider.ToString() + " DayZExpansion_AI_Animations=" + animations.ToString() + "; names alone do not verify artifact/version pin");
        // Exercise the base late-bound selection (HCEventAISelection) once, so startup logs
        // whether HC Events resolves this addon's provider; it only constructs a script object.
        HCEventAIProvider selected = HCEventAISelection.Create();
        string selectedName = "none";
        if (selected) { selectedName = selected.ClassName(); }
        Print("[HC Expansion AI] base event AI provider selection=" + selectedName + "; AI_ENCOUNTER Ready stays false until the site director runs with a qualified patrol");
    }
    bool Install(HCXAIProfile profile, HCXAIHooks hooks)
    {
        if (!GetGame() || !GetGame().IsServer() || m_Profile || this.HasReservations()) { return false; }
        string problem = HCXAIRules.ProfileProblem(profile);
        m_Status = "enabled preference; invalid or missing operator policy: " + problem;
        if (profile && !profile.Enabled) { m_Status = "disabled by operator"; }
        if (problem != "") { return false; }
        m_Status = "enabled preference; pve_patrols admission closed";
        if (!HCXAIQualification.Admitted()) { return false; }
        m_Status = "enabled preference; trusted artifact/observer/ownership hooks missing";
        if (!hooks) { return false; }
        m_Profile = HCXAIStore.Freeze(profile);
        if (!m_Profile || !HCXAIRules.ProfileValid(m_Profile)) { return false; }
        m_Hooks = hooks;
        m_Build = HCXAIStore.NativeBuild();
        if (!this.Prerequisites()) { m_Status = "pinned live prerequisites rejected"; return false; }
        m_Journal = HCXAIJournal.Open(m_Profile.WorldSession, m_Profile.MaxLeaseHistory);
        if (!m_Journal) { m_Status = "lease journal reconciliation refused"; return false; }
        m_Accepting = true;
        m_LastNow = GetGame().GetTime();
        if (!this.Ready(m_Profile.WorldName))
        {
            m_Accepting = false;
            m_Status = "enabled preference; pinned live prerequisites rejected";
            return false;
        }
        Print("[HC Expansion AI] exact source pin d84d3c73694969eba2f969e9178a1914e2f1b31d version 1.9.84 required; built-in human AI stuck recovery owner-approved; recreate blocked for leased actors");
        m_Status = "experimental adapter prerequisites observed; gameplay qualification pending";
        return true;
    }
    bool HasReservations() { return m_ReservedGroups > 0; }
    bool NativeGlobalsFair()
    {
        return this.GlobalsProblem() == "";
    }
    // First unfair or unsettled Expansion AI global, or "" when fair.
    string GlobalsProblem()
    {
        if (eAIBase.s_eAI_UnlimitedReload != 0 || eAIBase.s_eAI_UnlimitedReloadAll != 0) { return "unlimited reload mask set"; }
        // On a server GetAI() returns the instance even before Load(); only loaded settings are settled.
        if (!this.ExpansionAISettingsLoaded()) { return "Expansion AI settings not loaded"; }
        ExpansionAISettings settings = GetExpansionSettings().GetAI();
        if (settings.EnableFlankingOutsideCombat) { return "EnableFlankingOutsideCombat must be false"; }
        if (settings.CanRecruitFriendly || settings.CanRecruitGuards) { return "CanRecruitFriendly/CanRecruitGuards must be false"; }
        if (settings.DamageMultiplier != 1 || settings.DamageReceivedMultiplier != 1) { return "DamageMultiplier/DamageReceivedMultiplier must be 1"; }
        return "";
    }
    bool Prerequisites()
    {
        if (!GetGame() || !GetGame().IsServer() || !m_Profile || !m_Hooks) { return false; }
        int now = GetGame().GetTime();
        if (now < 0 || now < m_LastNow || m_Profile.BuildVersion != m_Build) { return false; }
        if (!HCXAIQualification.Admitted()) { return false; }
        if (!GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Scripts") || !GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Animations")) { return false; }
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
    protected bool CanPrune(HCXAILease lease)
    {
        if (!lease || !lease.Released || lease.Busy || lease.Failed || !lease.IntentConfirmed) { return false; }
        foreach (HCXAIActorSlot slot : lease.Slots)
        {
            if (!slot.Gone || slot.Handle || (slot.Attempted && !slot.DeleteObserved)) { return false; }
        }
        return true;
    }
    protected bool PruneHistory()
    {
        if (m_Leases.Count() < m_Profile.MaxLeaseHistory) { return true; }
        // Preserve cleanup and consumed-id evidence for this adapter's lifetime.
        // At the bound, refuse admission instead of forgetting an old cleanup.
        if (m_PrunedIds.Count() >= 64)
        {
            if (!m_PrunedCapLogged)
            {
                m_PrunedCapLogged = true;
                Print("[HC Expansion AI] pruned-lease-id cap (64) reached; further pruning and new leases refused to keep cleanup evidence; restart the server to reset");
            }
            return false;
        }
        int index = 0;
        while (index < m_Leases.Count())
        {
            HCXAILease oldest = m_Leases[index];
            if (this.CanPrune(oldest))
            {
                if (!m_Journal.Prune(oldest.Id)) { return false; }
                m_PrunedIds.Insert(oldest.Id);
                m_Leases.RemoveOrdered(index);
                m_Cursor = 0;
                return true;
            }
            index++;
        }
        return false;
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
        if (m_PrunedIds.Find(id) >= 0) { return false; }
        HCXAILease prior = this.FindLease(id);
        if (prior)
        {
            return !prior.Retiring && !prior.Failed && !prior.Released && prior.IntentConfirmed && prior.Session == session && prior.MissionId == missionId && prior.Anchor == anchor && prior.RequestedCap == actorCap;
        }
        if (actorCap < 1 || actorCap > HCAILimits.Get().MaxLiveAI) { Print("[HC AI] adapter refused AILimits.MaxLiveAI"); return false; }
        HCXAIMission mission = this.FindMission(missionId);
        if (!mission || anchor != mission.Anchor) { Print("[HC AI] adapter mission or surveyed anchor unavailable"); return false; }
        if (!m_Hooks.RouteQualified(mission.SurveySha256, mission.LoadoutSha256)) { return false; }
        int actors = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, mission.SiteId, "patrol");
        // Select a surveyed prefix, never manufacture extra spawn coordinates.
        if (actors > mission.Spawns.Count()) { actors = mission.Spawns.Count(); }
        if (actors < 1 || actors > actorCap) { Print("[HC AI] adapter group empty or exceeds requested cap"); return false; }
        int items = actors * mission.Equipment.Count();
        if (m_ReservedGroups >= HCAILimits.Get().MaxLiveGroups || m_ReservedActors + actors > HCAILimits.Get().MaxLiveAI || m_ReservedItems + items > m_Profile.MaxItems) { Print("[HC AI] adapter population/item reservation refused"); return false; }
        eAIFaction faction = eAIFaction.Create(mission.FactionName);
        if (!faction || faction.IsInvincible() || faction.IsObserver() || faction.IsPassive() || faction.HasUnlimitedStamina()) { return false; }
        if (faction.GetMeleeDamageMultiplier() != 1 || faction.GetMeleeYeetForce() != 0) { return false; }
        if (!this.PruneHistory()) { return false; }
        // Capacity/duplicate refusals and clean-row pruning create no intent.
        // Resolve them before publishing a reservation that needs End to close.
        if (!HCAIBudget.TryReserve("adapter:" + id, actors)) { Print("[HC AI] adapter shared population reservation refused"); return false; }
        if (!m_Journal.PrepareBegin(id, session, missionId)) { HCAIBudget.Release("adapter:" + id); return false; }
        HCXAILease lease = new HCXAILease();
        lease.Id = id;
        lease.Session = session;
        lease.MissionId = missionId;
        lease.Anchor = anchor;
        lease.RequestedCap = actorCap;
        lease.Objective = mission;
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
        // Journal intent first. Unknown write outcomes consume the id; never recreate.
        lease.IntentConfirmed = m_Journal.Begin(id, session, missionId);
        if (lease.IntentConfirmed) { lease.IntentConfirmed = m_Hooks.BeginLease(id, session, missionId, actors, items); }
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
        lease.Group.m_Persist = false;
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
        vector position = lease.Objective.Spawns[index];
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
        if (now - lease.StartedAtMs >= m_Profile.MaxLeaseMs) { lease.Retiring = true; }
        if (!lease.Retiring && !this.Ready(m_Profile.WorldName))
        {
            lease.Failed = true;
            lease.Retiring = true;
        }
        if (!lease.Retiring && (!lease.Group || lease.Group.m_Leave || lease.Group.m_Persist))
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
            // Receipt closure must precede persisted pruning eligibility. Failed
            // leases remain tombstones even when their reservations are released.
            if (allGone && m_Hooks.EndLease(lease.Id) && m_Journal.End(lease.Id, !lease.Failed && lease.IntentConfirmed))
            {
                if (lease.Group && lease.Group.Count() == 0) { lease.Group.Delete(); }
                lease.Released = true;
                HCAIBudget.Release("adapter:" + lease.Id);
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
        if (!m_Hooks.RouteQualified(lease.Objective.SurveySha256, lease.Objective.LoadoutSha256))
        {
            lease.Failed = true;
            lease.Retiring = true;
            return;
        }
        if (!this.Quiet(lease, slot, index, true, now)) { return; }
        // Never retry creation once the native factory has been entered.
        slot.Attempted = true;
        slot.Handle = GetGame().CreateObjectEx(lease.Objective.ActorClass, lease.Objective.Spawns[index], ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_NOSURFACEALIGN);
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
        actor.HCXAI_LeaseOwned = true;
        actor.SetGroup(lease.Group);
        actor.eAI_SetUnlimitedReload(0);
        actor.eAI_SetEnableFlankingOutsideCombat(0);
        actor.eAI_SetDamageMultiplier(1);
        actor.eAI_SetDamageReceivedMultiplier(1);
        actor.eAI_SetLootingBehavior(0);
        if (!actor.HCXAI_Fair() || !this.Equip(actor, lease.Objective) || !m_Hooks.MemberCreated(lease.Id, index, actor))
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
        if (m_PrunedIds.Find(id) >= 0) { return true; }
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
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (m_Sites) { m_Sites.Step(); }
        if (m_CampRoutine) { m_CampRoutine.Step(); }
        if (m_Encounters)
        {
            m_Encounters.Step();
            if (!m_ReadinessLogged && m_Encounters.Settled()) { this.LogReadiness("encounters settled"); }
        }
        // Retired lease spawner: m_Profile is never installed by OnStart now.
        if (!m_Profile) { return; }
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
        if (m_CampRoutine) { m_CampRoutine.Close(); }
        if (m_Encounters) { m_Encounters.Close(); }
        if (m_Sites) { m_Sites.Stop(); }
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
// AI_ENCOUNTER provider: binds an already-owned, qualified HC site patrol near
// the event anchor (HCXAIEncounters). It never spawns actors.
class HCExpansionAIEventProvider extends HCEventAIProvider
{
    override bool Ready(string world)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.Ready(world);
    }
    override bool Start(string lease, string session, string missionId, vector anchor, int actorCap)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.StartEncounter(lease, session, missionId, anchor, actorCap);
    }
    override HCEventObjectiveEvidence Observe(string lease, PlayerBase participant)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (!encounters) { return null; }
        return encounters.ObserveEncounter(lease, participant);
    }
    override bool Stop(string lease)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.StopEncounter(lease);
    }
    override bool Gone(string lease)
    {
        // No encounters object: nothing is bound in this process.
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (!encounters) { return true; }
        return encounters.GoneEncounter(lease);
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
    bool HCXAI_LeaseOwned;
    override void eAI_Recreate()
    {
        if (this.HCXAI_LeaseOwned)
        {
            m_eAI_Recreate = false;
            Print("[HC Expansion AI] refused inventory-cloning recreate for leased actor; native recovery remains owner-approved");
            return;
        }
        super.eAI_Recreate();
    }
    bool HCXAI_Fair()
    {
        return this.GetAllowDamage() && !m_eAI_EnableFlankingOutsideCombat && m_eAI_UnlimitedReload == 0 && !m_eAI_IsUnlimitedReloadAll && m_eAI_DamageMultiplier == 1 && m_eAI_DamageReceivedMultiplier == 1 && m_eAI_HeadshotResistance == 0;
    }
    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        EntityAI source = EntityAI.Cast(killer);
        if (!source) { return; }
        PlayerBase participant = PlayerBase.Cast(source.GetHierarchyRootPlayer());
        if (!participant || !participant.GetIdentity()) { return; }
        string participantId = participant.GetIdentity().GetId();
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (adapter) { adapter.RecordDeath(this, participantId); }
        // Expansion defers group cleanup to the next frame so EEKilled may still
        // read it: DayZPlayerImplement.c:431-438 (GetGroup at :234).
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (encounters) { encounters.RecordKill(this.GetGroup(), participantId); }
    }
    override void EEDelete(EntityAI parent)
    {
        HCXAIAdapter adapter = HCXAIService.Adapter();
        if (adapter) { adapter.RecordDelete(this); }
        super.EEDelete(parent);
    }
}
