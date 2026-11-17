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
		if (!JsonFileLoader<HCEcologyMigrationJournal>.LoadData(text, state, error)) { return null; }
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
		if (m_Fault || !HCEcologyRuntimeRules.Token(worldName) || !HCEcologyMigrationRules.UtcValid(utc)) { return null; }
		m_Fault = true;
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return null; }
		string imagePath = m_Root + "/migration-state-" + worldName + ".json";
		string pendingPath = m_Root + "/migration-pending-" + worldName + ".json";
		if (FileExist(pendingPath)) { return null; }
		m_World = worldName;
		HCEcologyMigrationJournal state;
		if (FileExist(imagePath))
		{
			state = HCEcologyMigrationIO.Decode(HCEcologyRuntimeIO.Read(imagePath, 16384));
			if (!HCEcologyMigrationRules.JournalValid(state, worldName)) { return null; }
			if (state.Revision < 1 || utc < state.LastUtc) { return null; }
			m_Revision = state.Revision;
			m_Fault = false;
			// Pending schedule attempts survive verbatim. No live movement is
			// replayed or inferred, even after a long offline interval.
			return state;
		}
		state = new HCEcologyMigrationJournal;
		state.Version = 1;
		state.WorldName = worldName;
		state.Revision = 1;
		state.LastUtc = utc;
		m_Fault = false;
		if (!Save(state)) { return null; }
		return state;
	}

	bool Save(HCEcologyMigrationJournal state)
	{
		if (m_Fault || !HCEcologyMigrationRules.JournalValid(state, m_World)) { return false; }
		if (state.Revision != m_Revision + 1) { return false; }
		string text = HCEcologyMigrationIO.Encode(state);
		if (text.Length() < 1 || text.Length() > 16384) { return false; }
		string imagePath = m_Root + "/migration-state-" + m_World + ".json";
		string pendingPath = m_Root + "/migration-pending-" + m_World + ".json";
		m_Fault = true;
		if (!HCEcologyRuntimeIO.WriteNew(pendingPath, text, 16384)) { return false; }
		if (!HCEcologyRuntimeIO.Write(imagePath, text, 16384)) { return false; }
		if (HCEcologyRuntimeIO.Read(imagePath, 16384) != text) { return false; }
		if (!DeleteFile(pendingPath)) { return false; }
		m_Revision = state.Revision;
		m_Fault = false;
		return true;
	}
}
