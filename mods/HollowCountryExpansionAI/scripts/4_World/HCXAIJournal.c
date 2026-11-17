// An unresolved intent consumes its id even after uncertain IO. No replay or factory.
// WorldSession must identify a fresh server process, supplied by trusted hooks.
// HC groups never persist; closed prior-process intents are tombstones, not kills.
class HCXAIJournal
{
    protected ref HCXAIJournalData m_Data;
    protected string m_Session;
    protected int m_Limit;

    static HCXAIJournal Open(string worldSession, int limit)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXAIRules.Token(worldSession) || limit < 1 || limit > 64) { return null; }
        HCXAIJournal journal = new HCXAIJournal();
        journal.m_Session = worldSession;
        journal.m_Limit = limit;
        journal.m_Data = HCXAIStore.LoadJournal();
        if (!journal.Reconcile())
        {
            Print("[HC Expansion AI] lease journal unresolved; admission refused (no AI restoration)");
            return null;
        }
        return journal;
    }
    bool Valid()
    {
        if (!m_Data || m_Data.SchemaVersion != 1 || !m_Data.Rows || m_Data.Rows.Count() > m_Limit) { return false; }
        int index = 0;
        foreach (HCXAIJournalRow row : m_Data.Rows)
        {
            if (!row || !HCXAIRules.Token(row.Id) || !HCXAIRules.Token(row.WorldSession) || !HCXAIRules.Token(row.Session) || !HCXAIRules.Token(row.MissionId)) { return false; }
            int prior = 0;
            while (prior < index)
            {
                if (m_Data.Rows[prior].Id == row.Id) { return false; }
                prior++;
            }
            index++;
        }
        return true;
    }
    bool Reconcile()
    {
        if (!this.Valid()) { return false; }
        foreach (HCXAIJournalRow row : m_Data.Rows)
        {
            if (!row.Closed && row.WorldSession == m_Session) { return false; }
        }
        foreach (HCXAIJournalRow oldRow : m_Data.Rows)
        {
            if (!oldRow.Closed)
            {
                oldRow.Closed = true;
                oldRow.Prunable = false;
                Print("[HC Expansion AI] retired prior-process nonpersistent lease intent; no actors/items restored");
            }
        }
        return HCXAIStore.SaveJournal(m_Data);
    }
    // Admission preflight may shrink clean history, but never inserts an intent.
    bool PrepareBegin(string id, string session, string missionId)
    {
        if (!this.Valid()) { return false; }
        if (!HCXAIRules.Token(id) || !HCXAIRules.Token(session) || !HCXAIRules.Token(missionId)) { return false; }
        foreach (HCXAIJournalRow priorRow : m_Data.Rows)
        {
            if (priorRow.Id == id) { return false; }
        }
        if (m_Data.Rows.Count() >= m_Limit)
        {
            HCXAIJournalRow oldest;
            foreach (HCXAIJournalRow candidate : m_Data.Rows)
            {
                if (candidate.Closed && candidate.Prunable) { oldest = candidate; break; }
            }
            if (!oldest || !this.Prune(oldest.Id)) { return false; }
        }
        return true;
    }
    bool Begin(string id, string session, string missionId)
    {
        // Recheck without pruning: callers prepare capacity before reserving.
        // After insertion, an uncertain save must keep the consumed intent.
        if (!this.Valid() || m_Data.Rows.Count() >= m_Limit) { return false; }
        if (!HCXAIRules.Token(id) || !HCXAIRules.Token(session) || !HCXAIRules.Token(missionId)) { return false; }
        foreach (HCXAIJournalRow existingRow : m_Data.Rows)
        {
            if (existingRow.Id == id) { return false; }
        }
        HCXAIJournalRow row = new HCXAIJournalRow();
        row.Id = id;
        row.WorldSession = m_Session;
        row.Session = session;
        row.MissionId = missionId;
        m_Data.Rows.Insert(row);
        return HCXAIStore.SaveJournal(m_Data);
    }
    bool End(string id, bool prunable = false)
    {
        if (!this.Valid()) { return false; }
        foreach (HCXAIJournalRow row : m_Data.Rows)
        {
            if (row.Id == id)
            {
                row.Closed = true;
                bool prior = row.Prunable;
                row.Prunable = prunable;
                if (HCXAIStore.SaveJournal(m_Data)) { return true; }
                row.Prunable = prior;
                return false;
            }
        }
        return false;
    }
    bool Prune(string id)
    {
        if (!GetGame() || !GetGame().IsServer() || !this.Valid()) { return false; }
        HCXAIJournalData retained = new HCXAIJournalData();
        bool found = false;
        foreach (HCXAIJournalRow row : m_Data.Rows)
        {
            if (row.Id == id)
            {
                if (!row.Closed || !row.Prunable) { return false; }
                found = true;
            }
            else { retained.Rows.Insert(row); }
        }
        // Do not discard in-memory evidence before durable shrink succeeds.
        // PrepareBegin may already have evicted this clean row while restart
        // tombstones occupied part of the journal's independent capacity.
        if (!found) { return true; }
        if (!HCXAIStore.SaveJournal(retained)) { return false; }
        m_Data = retained;
        return true;
    }
}
