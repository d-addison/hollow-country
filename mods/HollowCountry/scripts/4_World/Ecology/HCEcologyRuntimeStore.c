// Fixed owned paths; bounded parsing and readback, no globbing or claimed fsync.
// Startup archives leftover pending bytes before admitting the promoted image.
// Invalid images and failed quarantine remain refused; no pending-image replay.
class HCEcologyRuntimeIO
{
	static string Read(string path, int limit)
	{
		FileHandle handle = OpenFile(path, FileMode.READ);
		if (!handle) { return ""; }
		string text;
		int count = ReadFile(handle, text, limit + 1);
		CloseFile(handle);
		if (count < 1 || count > limit || text.Length() > limit) { return ""; }
		return text;
	}

	static bool Write(string path, string text, int limit)
	{
		if (text.Length() < 1 || text.Length() > limit) { return false; }
		FileHandle handle = OpenFile(path, FileMode.WRITE);
		if (!handle) { return false; }
		FPrint(handle, text);
		CloseFile(handle);
		return Read(path, limit) == text;
	}

    // Staged-only raw write: caller verifies before deleting the pending intent.
    static bool WriteRaw(string path, string text, int limit)
    {
        if (text.Length() < 1 || text.Length() > limit) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        FPrint(handle, text);
        CloseFile(handle);
        return true;
    }

	static bool WriteNew(string path, string text, int limit)
	{
		if (FileExist(path)) { return false; }
		return Write(path, text, limit);
	}

	static string Encode(HCEcologyCheckpoint state)
	{
		string text;
		string error;
		if (!JsonFileLoader<HCEcologyCheckpoint>.MakeData(state, text, error)) { return ""; }
		if (text.Length() > 2048) { return ""; }
		return text;
	}

	static HCEcologyCheckpoint Decode(string text)
	{
		HCEcologyCheckpoint state;
		string error;
		if (text.Length() < 1 || text.Length() > 2048) { return null; }
		if (!JsonFileLoader<HCEcologyCheckpoint>.LoadData(text, state, error)) { return null; }
		// Samples/PathQueries default to -1; native load zero-fills absent ints (#177).
		if (!HCJsonFields.Has(text, "Samples") || !HCJsonFields.Has(text, "PathQueries")) { return null; }
		return state;
	}

	static HCEcologyRuntimeSettings Settings()
	{
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		string root = "$profile:HollowCountry/Ecology";
		if (!FileExist(root) && !MakeDirectory(root)) { return null; }
		string path = root + "/settings.json";
		HCEcologyRuntimeSettings settings = new HCEcologyRuntimeSettings;
		string error;
		string text;
		if (FileExist(path))
		{
			text = Read(path, 2048);
			if (text.Length() < 1) { return null; }
			if (!JsonFileLoader<HCEcologyRuntimeSettings>.LoadData(text, settings, error)) { return null; }
		}
		else
		{
			if (!JsonFileLoader<HCEcologyRuntimeSettings>.MakeData(settings, text, error)) { return null; }
			if (!WriteNew(path, text, 2048)) { return null; }
		}
		if (!HCEcologyRuntimeRules.SettingsValid(settings)) { return null; }
		return settings;
	}
}

class HCEcologyRuntimeStore
{
	protected string m_Root = "$profile:HollowCountry/Ecology";
	protected string m_World;
	protected string m_Session;
	protected int m_Revision;
	protected bool m_Fault;
	protected int m_SavePhase;
	protected int m_SaveRevision;
	protected string m_SaveText;

	// HC-29: six scalar fields, encoded at <=2048 bytes. No live entity
	// snapshot, rename/fsync claim or unsupported asynchronous engine IO.
	// EnSystem.c:397/417/425/443/462/528; JsonFileLoader.c:85 MakeData.
	bool HCBeginSave(HCEcologyCheckpoint state)
	{
		if (m_Fault || m_SavePhase != 0 || !HCEcologyRuntimeRules.CheckpointValid(state, m_World)) { return false; }
		if (state.SessionId != m_Session || state.Revision != m_Revision + 1) { return false; }
		m_SaveText = HCEcologyRuntimeIO.Encode(state);
		if (m_SaveText.Length() < 1 || m_SaveText.Length() > 2048) { return false; }
		m_SaveRevision = state.Revision;
		m_SavePhase = 1;
		return true;
	}

	int HCPhase() { return m_SavePhase; }

	// Crash boundary 1: pending written, old primary intact; Open archives pending.
    // 2: pending verified, old primary intact. 3: primary written with pending
    // retained; Open archives pending and validates primary, refusing corruption.
    // 4: primary verified. 5: pending removed, new primary admitted as before.
    // Exactly one full write/read per stage; result codes 0 done/1 more/2 failed.
    // Perf batch E / #261: bounded staged writer, not a synchronous Save drain.
    // HCEcologySaveJob.HCAdvance invokes exactly one phase per scheduler stage;
    // each read/write is capped at 2048 bytes and pending names must stay intact.
    // Analyzer currently recognizes only HCStagedSaveImage as a stage boundary.
	int HCStepSave()
	{
		if (m_Fault && m_SavePhase <= 0) { return 2; }
		if (m_SavePhase < 1 || m_SavePhase > 5) { return 2; }
		string pendingPath = m_Root + "/pending-" + m_World + ".json";
		string imagePath = m_Root + "/state-" + m_World + ".json";
		bool ok = false;
		// Fault before the first intent attempt. Only this in-flight continuation
		// may proceed; every failure retains the journal and forbids retries.
		m_Fault = true;
		if (m_SavePhase == 1)
        {
            HCSaveJob.HCOperation = "write_tmp";
            ok = !FileExist(pendingPath) && HCEcologyRuntimeIO.WriteRaw(pendingPath, m_SaveText, 2048);
        }
        if (m_SavePhase == 2)
        {
            HCSaveJob.HCOperation = "read_tmp";
            ok = HCEcologyRuntimeIO.Read(pendingPath, 2048) == m_SaveText;
        }
        if (m_SavePhase == 3)
        {
            HCSaveJob.HCOperation = "write_primary";
            ok = HCEcologyRuntimeIO.WriteRaw(imagePath, m_SaveText, 2048);
        }
        if (m_SavePhase == 4)
        {
            HCSaveJob.HCOperation = "read_primary";
            ok = HCEcologyRuntimeIO.Read(imagePath, 2048) == m_SaveText;
        }
        if (m_SavePhase == 5)
        {
            HCSaveJob.HCOperation = "clear_intent";
            ok = DeleteFile(pendingPath);
        }
		if (!ok)
		{
			m_SavePhase = -1;
			m_SaveText = "";
			Print("[HC Plan] HC-29 state=refused reason=checkpoint_io visited=0 deferred=0 save_phase=-1 elapsed_us=-1; runtime=PENDING");
			return 2;
		}
		if (m_SavePhase < 5)
		{
			m_SavePhase++;
			return 1;
		}
		m_Revision = m_SaveRevision;
		m_SavePhase = 0;
		m_SaveText = "";
		m_Fault = false;
		return 0;
	}

	HCEcologyCheckpoint Open(string worldName, string session)
	{
		if (m_Fault || !HCEcologyRuntimeRules.Token(worldName) || !HCEcologyRuntimeRules.Token(session)) { return null; }
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return null; }
		// Keyed by world: another map's checkpoint never blocks or is touched.
		string imagePath = m_Root + "/state-" + worldName + ".json";
		string pendingName = "pending-" + worldName + ".json";
		string pendingPath = m_Root + "/" + pendingName;
		bool pending = FileExist(pendingPath);
		if (pending)
		{
			// HC-28 logical rename: verified archive before removing the active name.
			// No native rename exists. EnSystem.c:528/531 DeleteFile/CopyFile;
			// HCGroupClock.Utc uses EnSystem.c:76/100 UTC time/date.
			int now = HCGroupClock.Utc();
			string suffix = ".quarantined-" + now.ToString();
			string pendingText = HCEcologyRuntimeIO.Read(pendingPath, 2048);
			string pendingReason = "leftover_pending";
			if (pendingText.Trim().Length() == 0) { pendingReason = "leftover_pending_empty"; }
			bool archived = false;
			if (now > 0) { archived = HCPersistenceDisposition.HCArchive(pendingPath, suffix, 2048, true); }
			if (!archived || !DeleteFile(pendingPath) || FileExist(pendingPath))
			{
				m_Fault = true;
				Print("[HC Ecology] state=refused reason=pending_quarantine_failed runtime=PENDING");
				return null;
			}
			pending = false;
			Print("[HC Ecology] recovery=quarantined reason=" + pendingReason + " path=" + pendingName + suffix + " runtime=PENDING");
			HCPersistenceDisposition.HCPruneArchives(pendingPath, ".quarantined-");
		}
		bool image = FileExist(imagePath);
		HCEcologyCheckpoint prior;
		bool valid = false;
		if (image)
		{
			prior = HCEcologyRuntimeIO.Decode(HCEcologyRuntimeIO.Read(imagePath, 2048));
			valid = HCEcologyRuntimeRules.CheckpointValid(prior, worldName);
		}
		if (!HCEcologyRuntimeRules.CheckpointAdmission(pending, image, valid))
		{
			m_Fault = true;
			Print("[HC Ecology] checkpoint rejected; preserve pending/state files for recovery");
			return null;
		}
		m_World = worldName;
		m_Session = session;
		HCEcologyCheckpoint fresh = new HCEcologyCheckpoint;
		fresh.Version = 1;
		fresh.WorldName = worldName;
		fresh.SessionId = session;
		fresh.Samples = 0;
		fresh.PathQueries = 0;
		if (prior)
		{
			if (prior.SessionId == session || prior.Revision >= 1000000000) { return null; }
			fresh.Samples = prior.Samples;
			fresh.PathQueries = prior.PathQueries;
			m_Revision = prior.Revision;
		}
		fresh.Revision = m_Revision + 1;
		if (!Save(fresh)) { return null; }
		return fresh;
	}

	bool Save(HCEcologyCheckpoint state)
	{
		// Startup/shutdown barrier cannot overlap a routine continuation.
		if (m_SavePhase != 0) { return false; }
		if (m_Fault || !HCEcologyRuntimeRules.CheckpointValid(state, m_World)) { return false; }
		if (state.SessionId != m_Session) { return false; }
		if (state.Revision != m_Revision + 1) { return false; }
		string text = HCEcologyRuntimeIO.Encode(state);
		if (text.Length() < 1 || text.Length() > 2048) { return false; }
		// Once an intent write is attempted, every failure poisons this store.
		// No live caller can overwrite a possibly interrupted transaction.
		string imagePath = m_Root + "/state-" + m_World + ".json";
		string pendingPath = m_Root + "/pending-" + m_World + ".json";
		m_Fault = true;
		if (!HCEcologyRuntimeIO.WriteNew(pendingPath, text, 2048)) { return false; }
		if (!HCEcologyRuntimeIO.Write(imagePath, text, 2048)) { return false; }
		string actual = HCEcologyRuntimeIO.Read(imagePath, 2048);
		if (actual != text) { return false; }
		if (!DeleteFile(pendingPath)) { return false; }
		m_Revision = state.Revision;
		m_Fault = false;
		return true;
	}
}
