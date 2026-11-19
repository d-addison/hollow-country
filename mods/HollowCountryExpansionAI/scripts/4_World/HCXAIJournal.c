// An unresolved intent consumes its id even after uncertain IO. No replay or factory.
// WorldSession must identify a fresh server process, supplied by trusted hooks.
// HC groups never persist; closed prior-process intents are tombstones, not kills.
// Once the site director has removed every orphan "HC:" actor of earlier
// processes (orphansReconciled), those tombstones own nothing and are prunable,
// so a 64-row journal recycles instead of refusing every new lease.
class HCXAIJournal
{
    protected ref HCXAIJournalData m_Data;
    protected string m_Session;
    protected int m_Limit;
    // Last Begin refusal code ("" after an accepted intent); logged once per change.
    protected string m_Refusal;

    static HCXAIJournal Open(string worldSession, int limit, bool orphansReconciled = false)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXAIRules.Token(worldSession) || limit < 1 || limit > 64) { return null; }
        HCXAIJournal journal = new HCXAIJournal();
        journal.m_Session = worldSession;
        journal.m_Limit = limit;
        journal.m_Data = HCXAIStore.LoadJournal();
        if (!journal.Reconcile(orphansReconciled))
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
    bool Reconcile(bool orphansReconciled = false)
    {
        if (!this.Valid()) { return false; }
        foreach (HCXAIJournalRow row : m_Data.Rows)
        {
            if (!row.Closed && row.WorldSession == m_Session) { return false; }
        }
        int released = 0;
        foreach (HCXAIJournalRow oldRow : m_Data.Rows)
        {
            if (!oldRow.Closed)
            {
                oldRow.Closed = true;
                oldRow.Prunable = false;
                Print("[HC Expansion AI] retired prior-process nonpersistent lease intent; no actors/items restored");
            }
            if (orphansReconciled && oldRow.WorldSession != m_Session && !oldRow.Prunable)
            {
                oldRow.Prunable = true;
                released++;
            }
        }
        if (released > 0) { Print("[HC Expansion AI] lease journal: " + released.ToString() + " prior-process rows prunable after orphan reconciliation"); }
        return HCXAIStore.SaveJournal(m_Data);
    }
    // Admission preflight may shrink clean history, but never inserts an intent.
    bool PrepareBegin(string id, string session, string missionId)
    {
        if (!this.Valid()) { return this.RefuseBegin("journal_invalid"); }
        if (!HCXAIRules.Token(id) || !HCXAIRules.Token(session) || !HCXAIRules.Token(missionId)) { return this.RefuseBegin("bad_token"); }
        foreach (HCXAIJournalRow priorRow : m_Data.Rows)
        {
            if (priorRow.Id == id) { return this.RefuseBegin("duplicate_id"); }
        }
        if (m_Data.Rows.Count() >= m_Limit)
        {
            HCXAIJournalRow oldest;
            foreach (HCXAIJournalRow candidate : m_Data.Rows)
            {
                if (candidate.Closed && candidate.Prunable) { oldest = candidate; break; }
            }
            if (!oldest) { return this.RefuseBegin(HCRefusal.CAPACITY); }
            if (!this.Prune(oldest.Id)) { return this.RefuseBegin("prune_failed"); }
        }
        m_Refusal = "";
        return true;
    }
    string Refusal() { return m_Refusal; }
    protected bool RefuseBegin(string reason)
    {
        if (m_Refusal != reason) { Print("[HC Expansion AI] lease journal intent refused reason=" + reason); }
        m_Refusal = reason;
        return false;
    }
    bool Begin(string id, string session, string missionId)
    {
        // Recheck without pruning: callers prepare capacity before reserving.
        // After insertion, an uncertain save must keep the consumed intent.
        if (!this.Valid()) { return this.RefuseBegin("journal_invalid"); }
        if (m_Data.Rows.Count() >= m_Limit) { return this.RefuseBegin(HCRefusal.CAPACITY); }
        if (!HCXAIRules.Token(id) || !HCXAIRules.Token(session) || !HCXAIRules.Token(missionId)) { return this.RefuseBegin("bad_token"); }
        foreach (HCXAIJournalRow existingRow : m_Data.Rows)
        {
            if (existingRow.Id == id) { return this.RefuseBegin("duplicate_id"); }
        }
        HCXAIJournalRow row = new HCXAIJournalRow();
        row.Id = id;
        row.WorldSession = m_Session;
        row.Session = session;
        row.MissionId = missionId;
        m_Data.Rows.Insert(row);
        // An uncertain save keeps the consumed intent but must say why Begin failed.
        bool saved = HCXAIStore.SaveJournal(m_Data);
        if (!saved) { return this.RefuseBegin("journal_save_failed"); }
        m_Refusal = "";
        return true;
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
