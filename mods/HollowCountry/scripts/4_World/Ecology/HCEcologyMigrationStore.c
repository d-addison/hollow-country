// Native evidence in the same installed snapshot as HCEcologyMigrationNative:
// 3_Game/tools/JsonFileLoader.c:69-83 LoadData, :85-99 MakeData;
// 1_Core/proto/EnSystem.c:397 FileExist, :525 MakeDirectory, :528 DeleteFile.
// HCEcologyRuntimeIO uses EnSystem.c:417 OpenFile, :425 ReadFile,
// :443 CloseFile, :462 FPrint. No atomic rename/fsync contract is asserted.

// HCEcologyMigrationJournal.Build lives in the 3_Game DTO: a modded class
// cannot extend a class from a lower script module. Missing Build remains
// invalid. LastOutcome 4 means ambiguous, not replayed; recovery retains the
// prepared sequence, due time and population reservation.

// Bounded write-ahead/readback protocol. No fsync/atomicity claim; ambiguous
// journal contents are preserved and block admission rather than retried.
class HCEcologyMigrationIO
{
	static string Encode(HCEcologyMigrationJournal state)
	{
		string text;
		string error;
		if (!JsonFileLoader<HCEcologyMigrationJournal>.MakeData(state, text, error)) { return ""; }
		if (text.Length() > 16384) { return ""; }
		return text;
	}

	static HCEcologyMigrationJournal Decode(string text)
	{
		if (text.Length() < 1 || text.Length() > 16384) { return null; }
		HCEcologyMigrationJournal state;
		string error;
		if (!JsonFileLoader<HCEcologyMigrationJournal>.LoadData(text, state, error) || !state) { return null; }
		// Missing sentinels become native zero, which is a valid idle counter.
		// Require each row's keys before any recovery/reservation is admitted.
		if (!HCJsonFields.Has(text, "LastUtc") || !HCJsonFields.Has(text, "Schedules")) { return null; }
		if (!HCJsonFields.Every(text, "Sequence", 3) || !HCJsonFields.Every(text, "ReservedMembers", 3)) { return null; }
		if (!HCJsonFields.Every(text, "LastOutcome", 3) || !HCJsonFields.Every(text, "Pending", 3)) { return null; }
		state.WorldName = HCBuildIdentity.CanonicalWorld(state.WorldName);
		state.Build = HCBuildIdentity.Normalize(state.Build);
		return state;
	}
}

class HCEcologyMigrationStore
{
	protected string m_Root = "$profile:HollowCountry/Ecology";
	protected string m_World;
	protected int m_Revision;
	protected bool m_Fault;

	HCEcologyMigrationJournal Open(string worldName, int utc)
	{
		worldName = HCBuildIdentity.CanonicalWorld(worldName);
		if (!HCEcologyMigrationNative.BuildSupported()) { return null; }
		if (m_Fault || !HCEcologyRuntimeRules.Token(worldName) || !HCEcologyMigrationRules.UtcValid(utc)) { return null; }
		m_Fault = true;
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return null; }
		string imagePath = m_Root + "/migration-state-" + worldName + ".json";
		string pendingPath = m_Root + "/migration-pending-" + worldName + ".json";
		if (FileExist(pendingPath))
		{
			Print("[HC Ecology] migration quarantine in place; reason=unfinished write-ahead file; preserve both journal files");
			return null;
		}
		m_World = worldName;
		HCEcologyMigrationJournal state;
		if (FileExist(imagePath))
		{
			state = HCEcologyMigrationIO.Decode(HCEcologyRuntimeIO.Read(imagePath, 16384));
			if (!HCEcologyMigrationRules.JournalValid(state, worldName))
			{
				Print("[HC Ecology] migration quarantine in place; reason=corrupt, oversized or foreign build/world journal; preserve file");
				return null;
			}
			if (state.Revision < 1 || utc < state.LastUtc) { return null; }
			m_Revision = state.Revision;
			m_Fault = false;
			state.WorldName = worldName;
			state.Build = HCBuildIdentity.Canonical();
			int recovered = HCEcologyMigrationRules.RecoverPending(state);
			if (recovered < 0) { m_Fault = true; return null; }
			if (recovered > 0)
			{
				if (state.Revision >= 1000000000) { m_Fault = true; return null; }
				state.Revision++;
				state.LastUtc = utc;
				if (!Save(state)) { m_Fault = true; return null; }
				Print("[HC Ecology] stale migration pending resolved; reason=ambiguous, not replayed; sequence/deadline/reservation retained");
			}
			return state;
		}
		state = new HCEcologyMigrationJournal;
		state.Version = 1;
		state.Build = HCBuildIdentity.Canonical();
		state.WorldName = worldName;
		state.Revision = 1;
		state.LastUtc = utc;
		m_Fault = false;
		if (!Save(state)) { return null; }
		return state;
	}

    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;
    protected int m_SaveRevision;

    int SaveStep(HCEcologyMigrationJournal state)
    {
        if (m_Fault || !HCEcologyMigrationNative.BuildSupported()) { return HCSaveJob.STEP_FAILED; }
        if (!m_Image.Active())
        {
            if (!HCEcologyMigrationRules.JournalValid(state, m_World) || state.Revision != m_Revision + 1) { m_Fault = true; return HCSaveJob.STEP_FAILED; }
            string text = HCEcologyMigrationIO.Encode(state);
            string imagePath = m_Root + "/migration-state-" + m_World + ".json";
            string pendingPath = m_Root + "/migration-pending-" + m_World + ".json";
            if (!m_Image.Begin(imagePath, text, 16384, false, false, "", HCStagedSaveImage.HC_IMAGE_REPLACE, pendingPath)) { m_Fault = true; return HCSaveJob.STEP_FAILED; }
            m_SaveRevision = state.Revision;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { m_Fault = true; }
        if (result == HCSaveJob.STEP_DONE) { m_Revision = m_SaveRevision; }
        return result;
    }

    bool Save(HCEcologyMigrationJournal state)
    {
        int result = HCSaveJob.STEP_MORE;
        int stages;
        // Open/recovery only. Runtime prepares/completions queue the same stages.
        while (result == HCSaveJob.STEP_MORE && stages < HCStagedSaveImage.HC_MAX_STAGES)
        {
            result = SaveStep(state);
            stages++;
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            Print("[HC Persistence] owner=HCEcologyMigrationStore guard=save_stage_guard steps=" + stages.ToString());
            m_Fault = true;
            return false;
        }
        return result == HCSaveJob.STEP_DONE;
    }
}
