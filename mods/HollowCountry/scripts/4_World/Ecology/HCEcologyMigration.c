// Persistent cadence for an existing owned infected cohort. Static facade is
// intentionally narrow: no entity registration, sensing, spawning or ownership.
class HCEcologyMigration
{
	protected static ref HCEcologyMigration s_Service;
	protected ref HCEcologyMigrationJournal m_State;
	protected ref HCEcologyMigrationStore m_Store;
	protected string m_World;
	protected bool m_Fault;

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
		s_Service = service;
		if (!service.m_Fault)
		{
			int schedules = service.m_State.Schedules.Count();
			Print("[HC Ecology] migration journal ready; schedules=" + schedules.ToString() + "; owned-cohort hook and native qualifications required; animal destination unsupported");
		}
		return !service.m_Fault;
	}

	static void Stop()
	{
		// Every mutation is synchronously journaled; no live route is owned here.
		// Preserve a fault latch for this process: a restart is not a retry API.
		if (s_Service) { s_Service.m_Fault = true; }
	}

	static bool Enroll(string id, int populationKind, int intervalSeconds)
	{
		if (!HCEcologyNative.Authority() || !HCEcologyMigrationQualification.Admitted() || !s_Service) { return false; }
		return s_Service.EnrollOwned(id, populationKind, intervalSeconds, HCEcologyMigrationNative.Utc());
	}

	bool EnrollOwned(string id, int populationKind, int intervalSeconds, int utc)
	{
		if (!HCEcologyMigrationNative.BuildSupported() || m_Fault || !m_State || HCEcologyMigrationNative.CurrentWorld() != m_World) { return false; }
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
		if (!Enroll(id, HCEcologyPopulation.INFECTED, 300)) { return 0; }
		return Submit(id, pack, members, nativeNow, visualAdmitted, heardAdmitted);
	}

	static int Submit(string id, HCNativeInfectedPack pack, array<HCInfectedActor> members, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
		if (!s_Service) { return 0; }
		return s_Service.SubmitOwned(id, pack, members, HCEcologyMigrationNative.Utc(), nativeNow, visualAdmitted, heardAdmitted);
	}

	int SubmitOwned(string id, HCNativeInfectedPack pack, array<HCInfectedActor> members, int utc, float nativeNow, bool visualAdmitted, bool heardAdmitted)
	{
		if (m_Fault || !HCEcologyNative.Authority() || !HCEcologyMigrationNative.BuildSupported() || !HCEcologyMigrationQualification.Admitted()) { return 0; }
		if (!m_State || HCEcologyMigrationNative.CurrentWorld() != m_World) { return 0; }
		HCEcologyMigrationSchedule slot = HCEcologyMigrationRules.Find(m_State, id);
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
		int sequence = slot.Sequence;
		if (!Persist()) { m_Fault = true; return 0; }
		int result = HCEcologyMigrationNative.Move(pack, clue, members, nativeNow);
		int outcome = 3;
		if (result == 2) { outcome = 2; }
		if (!HCEcologyMigrationRules.Complete(slot, sequence, outcome) || !Persist())
		{
			m_Fault = true;
			// Native path work already happened. Preserve the owner's work
			// charge while refusing a durable acceptance claim after IO failure.
			if (result == 1 || result == 2) { return 1; }
			return 0;
		}
		return result;
	}

	bool Persist()
	{
		if (m_Fault || !m_State || !m_Store || m_State.Revision >= 1000000000) { return false; }
		m_State.Revision++;
		return m_Store.Save(m_State);
	}
}
