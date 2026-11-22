// Persistent cadence for an existing owned infected cohort. Static facade is
// intentionally narrow: no entity registration, sensing, spawning or ownership.
class HCEcologyMigration
{
	protected static ref HCEcologyMigration s_Service;
	protected ref HCEcologyMigrationJournal m_State;
	protected ref HCEcologyMigrationStore m_Store;
	protected string m_World;
	protected bool m_Fault;
    protected ref HCEcologyMigrationSaveJob m_SaveJob;
    protected string m_PendingId;
    protected bool m_PendingTown;
    protected vector m_PendingTownGoal;
    protected int m_PendingPhase; // 1 prepared intent; 2 completion checkpoint
    protected int m_PendingUtc;
    protected HCNativeInfectedPack m_PendingPack;
    protected ref HCInfectedClue m_PendingClue;
    protected ref array<HCInfectedActor> m_PendingMembers = new array<HCInfectedActor>;

    bool Pending() { return m_SaveJob && (m_SaveJob.HCDirty || m_SaveJob.HCInFlight); }
    int HCCheckpointStep()
    {
        if (m_Fault) { return HCSaveJob.STEP_FAILED; }
        int result = m_Store.SaveStep(m_State);
        if (result == HCSaveJob.STEP_FAILED) { m_Fault = true; }
        return result;
    }

    static void Tick()
    {
        if (!s_Service || s_Service.m_Fault) { return; }
        HCSaveScheduler.HCPumpFallback(s_Service.m_SaveJob);
        if (s_Service.Pending() || s_Service.m_Fault) { return; }
        if (s_Service.m_PendingPhase == 2)
        {
            s_Service.m_PendingPhase = 0;
            s_Service.m_PendingTown = false;
            s_Service.m_PendingId = "";
            s_Service.m_PendingPack = null;
            s_Service.m_PendingClue = null;
            s_Service.m_PendingMembers.Clear();
        }
        // A roster that disappears never pins all eight schedules forever.
        // Spend its prepared attempt without issuing any native path request.
        if (s_Service.m_PendingPhase == 1 && HCEcologyMigrationNative.Utc() - s_Service.m_PendingUtc >= 60)
        {
            HCEcologyMigrationSchedule slot = HCEcologyMigrationRules.Find(s_Service.m_State, s_Service.m_PendingId);
            if (!slot || !HCEcologyMigrationRules.Complete(slot, slot.Sequence, 3) || !s_Service.Persist()) { s_Service.m_Fault = true; return; }
            s_Service.m_PendingPhase = 2;
        }
    }


	static bool Start(string worldName)
	{
		worldName = HCBuildIdentity.CanonicalWorld(worldName);
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationNative.BuildSupported() || !HCEcologyMigrationQualification.Admitted()) { return false; }
		if (worldName != HCEcologyMigrationNative.CurrentWorld()) { return false; }
		if (s_Service) { return !s_Service.m_Fault && s_Service.m_World == worldName; }
		HCEcologyMigration service = new HCEcologyMigration;
		service.m_World = worldName;
		service.m_Store = new HCEcologyMigrationStore;
		service.m_State = service.m_Store.Open(worldName, HCEcologyMigrationNative.Utc());
		if (!service.m_State)
		{
			service.m_Fault = true;
			Print("[HC Ecology] migration journal rejected; preserve state and pending files");
		}
        if (!service.m_Fault)
        {
            service.m_SaveJob = new HCEcologyMigrationSaveJob;
            service.m_SaveJob.Owner = service;
            HCSaveScheduler.HCRegister(service.m_SaveJob);
        }
		s_Service = service;
		if (!service.m_Fault)
		{
			int schedules = service.m_State.Schedules.Count();
			Print("[HC Ecology] migration journal ready; schedules=" + schedules.ToString() + "; owned native cohort required; cycle owns animal input leases; animal destination setter absent");
		}
		return !service.m_Fault;
	}

    static bool Operational() { return s_Service && !s_Service.m_Fault; }

	static void Stop()
	{
        if (!s_Service) { return; }
        HCSaveScheduler.HCFlush(s_Service.m_SaveJob);
        HCSaveScheduler.HCUnregister(s_Service.m_SaveJob);
        // Preserve a fault latch and every prepared reservation; restart never moves it.
        s_Service.m_Fault = true;
	}

	static bool Enroll(string id, int populationKind, int intervalSeconds)
	{
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationQualification.Admitted() || !s_Service) { return false; }
		return s_Service.EnrollOwned(id, populationKind, intervalSeconds, HCEcologyMigrationNative.Utc());
	}

	bool EnrollOwned(string id, int populationKind, int intervalSeconds, int utc)
	{
		if (!HCEcologyMigrationNative.BuildSupported() || m_Fault || !m_State || HCEcologyMigrationNative.CurrentWorld() != m_World) { return false; }
        if (Pending() || m_PendingPhase != 0) { return false; }
		if (populationKind == HCEcologyPopulation.ANIMAL && !HCEcologyMigrationNative.AnimalDestinationSupported()) { return false; }
		if (!HCEcologyMigrationRules.UtcValid(utc) || utc < m_State.LastUtc) { return false; }
		if (intervalSeconds < 60 || intervalSeconds > 86400 || utc > 2140000000 - intervalSeconds) { return false; }
		HCEcologyMigrationSchedule prior = HCEcologyMigrationRules.Find(m_State, id);
		if (prior) { return prior.PopulationKind == populationKind && prior.IntervalSeconds == intervalSeconds; }
		if (m_State.Schedules.Count() >= 8) { return false; }
		HCEcologyMigrationSchedule slot = new HCEcologyMigrationSchedule;
		slot.Id = id;
		slot.PopulationKind = populationKind;
		slot.IntervalSeconds = intervalSeconds;
		slot.Sequence = 0;
		slot.ReservedMembers = 0;
		slot.LastOutcome = 0;
		slot.NextDueUtc = utc + intervalSeconds;
		if (!HCEcologyMigrationRules.ScheduleValid(slot)) { return false; }
		m_State.Schedules.Insert(slot);
		m_State.LastUtc = utc;
		if (Persist()) { return true; }
		m_Fault = true;
		return false;
	}

	// Core caller seam: use only the Infected owner's already-observed roster.
	// 24 tracked actors and six members are the owner's current hard ceilings.
	// No discovery, ownership acquisition, ordinary-route fallback or replay here.
	static int SubmitCohort(int groupId, HCNativeInfectedPack pack, array<ref HCInfectedActor> actors, int expectedMembers, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
        HCEcologyCycle cycleOwner = HCEcologyCycle.Active();
        if (cycleOwner && cycleOwner.NeedsMigration()) { return 0; }
		if (!HCEcologyMigrationQualification.Admitted() || !pack || !actors) { return 0; }
		if (groupId < 1 || actors.Count() > 24 || expectedMembers < 1 || expectedMembers > 6) { return 0; }
		array<HCInfectedActor> members = new array<HCInfectedActor>;
		int i = 0;
		while (i < actors.Count())
		{
			HCInfectedActor actor = actors.Get(i);
			if (actor && actor.GroupId == groupId)
			{
				if (!actor.InfectedEntity) { return 0; }
				if (actor.InfectedEntity.IsAlive()) { members.Insert(actor); }
			}
			i++;
		}
		if (members.Count() != expectedMembers || !HCEcologyMigrationNative.Owns(pack, members)) { return 0; }
		string id = "infected-" + groupId.ToString();
		if (!Enroll(id, HCEcologyPopulation.INFECTED, 300) && (!s_Service || s_Service.m_PendingId != id))
        {
            if (s_Service && (s_Service.Pending() || s_Service.m_PendingPhase != 0)) { return 3; }
            return 0;
        }
		return Submit(id, pack, members, nativeNow, visualAdmitted, heardAdmitted);
	}

    // Environmental cadence is distinct from sensory attraction. Freeze a
    // native goal before durable prepare; never manufacture HCInfectedClue.
    static int SubmitTown(int groupId, HCNativeInfectedPack pack, array<ref HCInfectedActor> actors, float now)
    {
        int townStart = TickCount(0);
        int townResult = SubmitTownWork(groupId, pack, actors, now);
        HCEcologySteps.Deferred(townStart);
        return townResult;
    }

    static int SubmitTownWork(int groupId, HCNativeInfectedPack pack, array<ref HCInfectedActor> actors, float now)
    {
        HCEcologyCycle cycle = HCEcologyCycle.Active();
        if (!s_Service || s_Service.m_Fault || !cycle || !cycle.Ready() || !cycle.NeedsMigration() || !actors || actors.Count() > 256 || !pack) { return 0; }
        array<HCInfectedActor> members = new array<HCInfectedActor>;
        foreach (HCInfectedActor actor : actors)
        {
            if (actor && actor.GroupId == groupId && actor.InfectedEntity && actor.InfectedEntity.IsAlive()) { members.Insert(actor); }
        }
        if (!pack.HCEcologyOwnsTown(members)) { return 0; }
        string id = "town-pressure";
        int utc = HCEcologyMigrationNative.Utc();
        if (s_Service.Pending()) { return 3; }
        if (s_Service.m_PendingPhase != 0 && s_Service.m_PendingId != id) { return 3; }
        HCEcologyMigrationSchedule slot = HCEcologyMigrationRules.Find(s_Service.m_State, id);
        if (s_Service.m_PendingPhase == 1)
        {
            if (!s_Service.m_PendingTown || !slot || pack != s_Service.m_PendingPack) { return 3; }
            bool same = members.Count() == s_Service.m_PendingMembers.Count();
            for (int i = 0; same && i < members.Count(); i++) { if (members[i] != s_Service.m_PendingMembers[i]) { same = false; } }
            int result = 0;
            if (same && cycle.TakePath())
            {
                result = pack.HCEcologyTownStep(s_Service.m_PendingTownGoal, now, cycle.InfectedInterval());
                cycle.InfectedRequested(result);
            }
            else if (same) { return 3; }
            int outcome = 3;
            if (result == 2) { outcome = 2; }
            if (!HCEcologyMigrationRules.Complete(slot, slot.Sequence, outcome) || !s_Service.Persist()) { s_Service.m_Fault = true; }
            s_Service.m_PendingPhase = 2;
            return result;
        }
        if (s_Service.m_PendingPhase != 0) { return 3; }
        if (!slot)
        {
            if (!s_Service.EnrollOwned(id, HCEcologyPopulation.INFECTED, cycle.InfectedInterval(), utc))
            {
                s_Service.m_Fault = true;
                Print("[HC Ecology] town_schedule=refused reason=journal_capacity_clock_or_store runtime=PENDING");
            }
            return 0;
        }
        if (slot.IntervalSeconds != cycle.InfectedInterval())
        {
            slot.IntervalSeconds = cycle.InfectedInterval();
            slot.NextDueUtc = utc + slot.IntervalSeconds;
            if (!s_Service.Persist()) { s_Service.m_Fault = true; }
            return 3;
        }
        if (!HCEcologyMigrationRules.Due(slot, utc)) { return 0; }
        vector goal;
        if (!cycle.InfectedGoal(members[0].InfectedEntity.GetPosition(), goal)) { return 0; }
        int maximum = HCEcologyMigrationNative.Ceiling(HCEcologyPopulation.INFECTED);
        if (!HCEcologyMigrationRules.CapacityAvailable(s_Service.m_State, slot, members.Count(), maximum)) { return 0; }
        if (!HCEcologyMigrationRules.Prepare(s_Service.m_State, slot, utc)) { return 0; }
        slot.ReservedMembers = Math.Max(slot.ReservedMembers, members.Count());
        s_Service.m_PendingId = id;
        s_Service.m_PendingPhase = 1;
        s_Service.m_PendingTown = true;
        s_Service.m_PendingUtc = utc;
        s_Service.m_PendingPack = pack;
        s_Service.m_PendingTownGoal = goal;
        s_Service.m_PendingMembers.Clear();
        s_Service.m_PendingMembers.InsertAll(members);
        if (!s_Service.Persist()) { s_Service.m_Fault = true; return 0; }
        return 3;
    }

	static int Submit(string id, HCNativeInfectedPack pack, array<HCInfectedActor> members, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
		if (!s_Service) { return 0; }
        int migrationStart = TickCount(0);
        int migrationResult = s_Service.SubmitOwned(id, pack, members, HCEcologyMigrationNative.Utc(), nativeNow, visualAdmitted, heardAdmitted);
        HCEcologySteps.Deferred(migrationStart);
        return migrationResult;
	}

	int SubmitOwned(string id, HCNativeInfectedPack pack, array<HCInfectedActor> members, int utc, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
		if (m_Fault || !HCEcologyNative.Authority() || !HCEcologyMigrationNative.BuildSupported() || !HCEcologyMigrationQualification.Admitted()) { return 0; }
		if (!m_State || HCEcologyMigrationNative.CurrentWorld() != m_World) { return 0; }
		HCEcologyMigrationSchedule slot = HCEcologyMigrationRules.Find(m_State, id);
        if (Pending() || (m_PendingPhase != 0 && m_PendingId != id)) { return 3; }
        if (m_PendingPhase == 1 && m_PendingId == id && !m_PendingTown)
        {
            if (!slot) { m_Fault = true; return 0; }
            bool sameRoster = pack == m_PendingPack && members && members.Count() == m_PendingMembers.Count();
            if (sameRoster)
            {
                for (int index = 0; index < members.Count(); index++)
                {
                    if (members[index] != m_PendingMembers[index]) { sameRoster = false; break; }
                }
            }
            int result = 0;
            if (sameRoster) { result = HCEcologyMigrationNative.Move(pack, m_PendingClue, members, nativeNow); }
            int outcome = 3;
            if (result == 2) { outcome = 2; }
            if (!HCEcologyMigrationRules.Complete(slot, slot.Sequence, outcome) || !Persist()) { m_Fault = true; }
            m_PendingPhase = 2;
            return result;
        }
        if (m_PendingPhase != 0) { return 3; }
		if (!slot || slot.PopulationKind != HCEcologyPopulation.INFECTED || !HCEcologyMigrationRules.Due(slot, utc)) { return 0; }
		int ceMaximum = HCEcologyMigrationNative.Ceiling(slot.PopulationKind);
		int limit = HCEcologyMigrationRules.MemberLimit(ceMaximum, 6);
		if (!members || members.Count() < 1 || members.Count() > limit) { return 0; }
		if (!HCEcologyMigrationRules.CapacityAvailable(m_State, slot, members.Count(), ceMaximum)) { return 0; }
		if (!HCEcologyMigrationNative.Owns(pack, members)) { return 0; }
		HCInfectedClue clue = HCEcologyMigrationNative.Choose(members, nativeNow, visualAdmitted, heardAdmitted);
		if (!clue || !HCEcologyMigrationNative.Unobserved(members, clue)) { return 0; }
		if (!HCEcologyMigrationRules.Prepare(m_State, slot, utc)) { return 0; }
		slot.ReservedMembers = Math.Max(slot.ReservedMembers, members.Count());
        m_PendingId = id;
        m_PendingPhase = 1;
        m_PendingUtc = utc;
        m_PendingPack = pack;
        m_PendingClue = clue;
        m_PendingMembers.Clear();
        m_PendingMembers.InsertAll(members);
        if (!Persist()) { m_Fault = true; return 0; }
        return 3; // retained continuation, no ordinary-route fallback while preparing

	}

    // Queue only; native Move resumes from SubmitOwned with current owner roster,
    // time and visibility checks after the prepare checkpoint has committed.
    bool Persist()
    {
        if (m_Fault || !m_State || !m_Store || !m_SaveJob || m_State.Revision >= 1000000000) { return false; }
        m_State.Revision++;
        m_SaveJob.HCDirty = true;
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
        return true;
    }
}

class HCEcologyMigrationSaveJob : HCSaveJob
{
    HCEcologyMigration Owner;
    override string HCName() { return "EcologyMigration"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCCheckpointStep();
    }
}
