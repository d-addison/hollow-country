// w29-debugmap #194: one-pass read-only batch getter for the lead-ledger layer.
// The contributor reads HCWorldClock.UTC() once per Describe and passes it in, so
// the clock is no longer read once per getter call. Scans at most
// HC_DEBUG_LEAD_SCAN rows (the store ceiling), copies unexpired rows with the group
// id withheld, never calls Select/Latest (they advance cursors) and never mutates
// the store. Returns the number of unexpired rows scanned. Runtime acceptance pending.
modded class HCLeadModule
{
    int HCDebugLeadRows(int now, array<ref HCWorldLead> output)
    {
        if (!output || now <= 0 || !Get()) { return 0; }
        int scan = m_Store.Data.Leads.Count();
        if (scan > HC_DEBUG_LEAD_SCAN) { scan = HC_DEBUG_LEAD_SCAN; }
        int count = 0;
        for (int index = 0; index < scan; index++)
        {
            HCWorldLead row = m_Store.Data.Leads[index];
            if (row.Expires <= now) { continue; }
            HCWorldLead copy = HCLeadPolicy.Copy(row);
            copy.GroupId = "";
            output.Insert(copy);
            count++;
        }
        return count;
    }
}
