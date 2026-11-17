// All scalar bounds are implementation budgets, not measured population targets.
class HCEcologyMigrationRules
{
	static bool UtcValid(int utc)
	{
		return utc >= 1767225600 && utc <= 2140000000;
	}

	static int MemberLimit(int ceMaximum, int budget)
	{
		if (ceMaximum < 1 || budget < 1 || budget > 6) { return 0; }
		return Math.Min(ceMaximum, budget);
	}

	static bool ScheduleValid(HCEcologyMigrationSchedule slot)
	{
		if (!slot || !HCEcologyRuntimeRules.Token(slot.Id)) { return false; }
		if (slot.PopulationKind != 1 && slot.PopulationKind != 2) { return false; }
		if (slot.IntervalSeconds < 60 || slot.IntervalSeconds > 86400) { return false; }
		if (!UtcValid(slot.NextDueUtc)) { return false; }
		if (slot.Sequence < 0 || slot.Sequence > 1000000000) { return false; }
		if (slot.ReservedMembers < 0 || slot.ReservedMembers > 6) { return false; }
		if (slot.LastOutcome < 0 || slot.LastOutcome > 4) { return false; }
		if (slot.Pending) { return slot.Sequence > 0 && slot.LastOutcome == 1; }
		if (slot.LastOutcome == 1) { return false; }
		return true;
	}

	static bool JournalValid(HCEcologyMigrationJournal state, string worldName)
	{
		worldName = HCBuildIdentity.CanonicalWorld(worldName);
		if (!state || state.Version != 1 || !HCBuildIdentity.SameWorld(state.WorldName, worldName)) { return false; }
		if (!HCBuildIdentity.Matches(state.Build)) { return false; }
		if (!HCEcologyRuntimeRules.Token(worldName) || !UtcValid(state.LastUtc)) { return false; }
		if (state.Revision < 0 || state.Revision > 1000000000) { return false; }
		if (!state.Schedules || state.Schedules.Count() > 8) { return false; }
		int i = 0;
		while (i < state.Schedules.Count())
		{
			HCEcologyMigrationSchedule slot = state.Schedules.Get(i);
			if (!ScheduleValid(slot)) { return false; }
			int j = 0;
			while (j < i)
			{
				if (state.Schedules.Get(j).Id == slot.Id) { return false; }
				j++;
			}
			i++;
		}
		return true;
	}

	static HCEcologyMigrationSchedule Find(HCEcologyMigrationJournal state, string id)
	{
		if (!state || !state.Schedules || state.Schedules.Count() > 8) { return null; }
		int i = 0;
		while (i < state.Schedules.Count())
		{
			HCEcologyMigrationSchedule slot = state.Schedules.Get(i);
			if (slot && slot.Id == id) { return slot; }
			i++;
		}
		return null;
	}

	static bool CapacityAvailable(HCEcologyMigrationJournal state, HCEcologyMigrationSchedule slot, int members, int ceMaximum)
	{
		if (!state || !slot || !JournalValid(state, state.WorldName) || Find(state, slot.Id) != slot) { return false; }
		if (members < 1 || members > MemberLimit(ceMaximum, 6)) { return false; }
		int reserved = Math.Max(slot.ReservedMembers, members);
		int i = 0;
		while (i < state.Schedules.Count())
		{
			HCEcologyMigrationSchedule other = state.Schedules.Get(i);
			if (other != slot && other.PopulationKind == slot.PopulationKind) { reserved += other.ReservedMembers; }
			i++;
		}
		return reserved <= ceMaximum;
	}

	static bool Due(HCEcologyMigrationSchedule slot, int utc)
	{
		if (!ScheduleValid(slot) || !UtcValid(utc) || slot.Pending) { return false; }
		return utc >= slot.NextDueUtc && utc <= 2140000000 - slot.IntervalSeconds;
	}

	static bool Prepare(HCEcologyMigrationJournal state, HCEcologyMigrationSchedule slot, int utc)
	{
		if (!state || !JournalValid(state, state.WorldName) || !Due(slot, utc)) { return false; }
		if (Find(state, slot.Id) != slot || utc < state.LastUtc) { return false; }
		if (slot.Sequence >= 1000000000 || state.Revision >= 1000000000) { return false; }
		slot.Sequence++;
		slot.NextDueUtc = utc + slot.IntervalSeconds;
		slot.Pending = true;
		slot.LastOutcome = 1;
		state.LastUtc = utc;
		return true;
	}

	static int RecoverPending(HCEcologyMigrationJournal state)
	{
		if (!state || !JournalValid(state, state.WorldName)) { return -1; }
		int recovered = 0;
		int i = 0;
		while (i < state.Schedules.Count())
		{
			HCEcologyMigrationSchedule slot = state.Schedules.Get(i);
			if (slot.Pending)
			{
				slot.Pending = false;
				slot.LastOutcome = 4; // ambiguous, not replayed; never command acceptance
				recovered++;
			}
			i++;
		}
		return recovered;
	}

	static bool Complete(HCEcologyMigrationSchedule slot, int sequence, int outcome)
	{
		if (!ScheduleValid(slot) || !slot.Pending || slot.Sequence != sequence) { return false; }
		if (outcome != 2 && outcome != 3) { return false; }
		slot.Pending = false;
		slot.LastOutcome = outcome;
		return true;
	}
}
