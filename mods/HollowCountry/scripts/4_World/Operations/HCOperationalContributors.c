// HC-25. Source/cache policy only; lifecycle publisher integration is lead-owned.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,385,407 arrays, :866,926 map;
// EnString.c:137,199,212 UTF8 text bounds via HCDebugSnapshot.HCText;
// EnConvert.c:30 ToString; EnDebug.c:96 Print; 3_Game/Global/Game.c:914
// GetTickTime; gameplay.c:636 GetGame. No world/provider/file queries.
// Trace: consolidated coverage plan Wave 2 HC-25; qualification stays PENDING.
class HCOperationalOwner
{
    string Name;
    ref HCOperationalStatus Status = new HCOperationalStatus;
    bool Requested;
    float ObservedAt = -1;
    float CountersAt = -1;
    int Work = -1;
    int Cap = -1;
    int Refusals = -1;
    string Exception = "owner_counters_unobserved";

    // Called by the normal owner lifecycle, NEVER by an admin request.
    void HCObserve(bool requested, HCOperationalStatus reported, float now)
    {
        Requested = requested;
        Status.HCCapture(Name, requested, reported);
        ObservedAt = now;
    }

    // -1 is unobserved. Zero is reserved for a counter actually supplied by owner.
    // Exceptions: no_work, native, transient; all others retain explicit reason.
    void HCCounters(int work, int cap, int refusals, string exception, float now)
    {
        Work = Math.Max(-1, work);
        Cap = Math.Max(-1, cap);
        Refusals = Math.Max(-1, refusals);
        Exception = HCDebugSnapshot.HCText(exception, 96);
        if (Exception == "") { Exception = "owner_counters_unobserved"; }
        CountersAt = now;
    }

    void HCStop(float now)
    {
        Requested = false;
        Status.HCStop();
        ObservedAt = now;
        CountersAt = -1;
        Exception = "no_work";
    }

    string HCFreshness(float observed, float now)
    {
        if (observed < 0 || now < observed) { return "unobserved"; }
        if (now - observed > HCOperationalContributors.MAX_SOURCE_AGE_SECONDS) { return "stale"; }
        return "cached";
    }

    string HCLine(float now)
    {
        string freshness = HCFreshness(ObservedAt, now);
        // Inactive modules have no tick callback. Their admission receipt stays
        // authoritative until the next lifecycle, without a hidden off-path poll.
        if (!Requested && ObservedAt >= 0 && now >= ObservedAt) { freshness = "inactive_receipt"; }
        string state = Status.HCState();
        string reason = Status.HCReason();
        if (freshness == "stale" || freshness == "unobserved")
        {
            state = "unknown";
            reason = "source_" + freshness;
        }
        string line = "[HC Admin] owner=" + Name + " state=" + state;
        line += " source_state=" + Status.HCState() + " freshness=" + freshness;
        line += " reason=" + HCDebugSnapshot.HCText(reason, 128);
        string readiness = "owner_reported";
        if (Status.HCUnknown()) { readiness = "unknown"; }
        line += " readiness=" + readiness;
        string counterFreshness = HCFreshness(CountersAt, now);
        if (counterFreshness == "cached")
        {
            line += " work=" + Work.ToString() + " cap=" + Cap.ToString() + " refusals=" + Refusals.ToString();
        }
        else { line += " work=unobserved cap=unobserved refusals=unobserved"; }
        line += " counters=" + counterFreshness + " exception=" + Exception;
        return line + " perf=unobserved qualification=PENDING runtime=PENDING";
    }
}

class HCOperationalContributors
{
    // Temporal bound, NOT a world range or runtime performance promise.
    static const int MAX_SOURCE_AGE_SECONDS = 60;
    protected static ref array<ref HCOperationalOwner> s_Owners = new array<ref HCOperationalOwner>;
    protected static ref map<string, ref HCOperationalOwner> s_ByName = new map<string, ref HCOperationalOwner>;
    protected static ref HCDebugOperationalContributor s_Aggregate;
    protected static int s_Refused;
    protected static bool s_Registered;

    static HCOperationalOwner HCRegisterOwner(string name)
    {
        if (name == "" || name.Length() > 64) { return null; }
        HCOperationalOwner existing = s_ByName.Get(name);
        if (existing) { return existing; }
        if (s_Owners.Count() >= 64)
        {
            if (s_Refused < 1000000) { s_Refused++; }
            return null;
        }
        if (!s_Aggregate) { s_Aggregate = new HCDebugOperationalContributor; }
        // One aggregate, not one of the 16 contributor slots per module.
        if (!s_Registered) { s_Registered = HCDebugSnapshot.HCRegister(s_Aggregate); }
        HCOperationalOwner owner = new HCOperationalOwner;
        owner.Name = name;
        s_Owners.Insert(owner);
        s_ByName.Insert(name, owner);
        return owner;
    }

    static void HCReset()
    {
        if (s_Aggregate) { HCDebugSnapshot.HCUnregister(s_Aggregate); }
        s_Aggregate = null;
        s_Registered = false;
        s_Owners.Clear();
        s_ByName.Clear();
        s_Refused = 0;
    }

    static int HCCount() { return s_Owners.Count(); }
    static int HCRefused() { return s_Refused; }

    // Lead calls once after lifecycle admission, not from every owner constructor.
    static void HCReport()
    {
        HCAdminReply receipt = new HCAdminReply;
        array<string> rows = HCRows(GetGame().GetTickTime());
        HCAppend(receipt, rows, s_Refused);
        Print("[HC Plan] HC-25 scope=store_detail state=refused reason=per_store_quarantine_not_exposed runtime=PENDING");
        Print(receipt.Lines[receipt.Lines.Count() - 1]);
    }

    // Only cached HC-28 gate getters. A closed gate does not distinguish off,
    // never-loaded, stopped or quarantine; do not invent that missing capability.
    static string HCStoreLine(string name)
    {
        string gate = "closed_or_quarantined";
        if (HCRecoveryGate.HCReady(name)) { gate = "admitted"; }
        string paired = "unobserved";
        if (HCRecoveryGate.HCGeneration() > 0) { paired = "operator_attested"; }
        string line = "[HC Admin] store=" + name + " disposition=" + HCRecoveryGate.HCDisposition(name);
        line += " recovery=" + gate + " generation=" + HCRecoveryGate.HCGeneration().ToString();
        line += " paired_recovery=" + paired;
        line += " quarantined_total=" + HCRecoveryGate.HCQuarantined().ToString();
        line += " aggregate_reason=" + HCDebugSnapshot.HCText(HCRecoveryGate.HCReason(), 128);
        return line + " refusal=per_store_quarantine_not_exposed per_store_quarantine=unobserved native_generation=unobserved runtime=PENDING";
    }

    static array<string> HCRows(float now)
    {
        array<string> rows = new array<string>;
        HCUnitBudget budget = new HCUnitBudget;
        budget.HCReset(64);
        for (int index = 0; index < s_Owners.Count(); index++)
        {
            if (!budget.HCTake(1)) { break; }
            rows.Insert(s_Owners[index].HCLine(now));
        }
        rows.Insert(HCStoreLine("world"));
        rows.Insert(HCStoreLine("escalation"));
        rows.Insert(HCStoreLine("groups"));
        rows.Insert("[HC Admin] exceptions invitation=transient runtime_handle=transient native_inventory=native native_stash=native unknown_store=unknown_refused no_work=owner_report_required perf=unobserved runtime=PENDING");
        return rows;
    }

    // Fixed existing transport cap: reserve one of 64 lines for visible loss.
    static void HCAppend(HCAdminReply reply, array<string> rows, int lost)
    {
        int dropped = lost;
        for (int index = 0; index < rows.Count(); index++)
        {
            if (reply.Lines.Count() >= 63) { dropped++; continue; }
            reply.Lines.Insert(HCDebugSnapshot.HCText(rows[index], 768));
        }
        string state = "on";
        string reason = "cached_only";
        if (!s_Registered) { state = "refused"; reason = "aggregate_contributor_not_registered"; }
        if (!s_Aggregate) { state = "off"; reason = "owners_not_registered"; }
        string line = "[HC Plan] HC-25 contributors=" + HCDebugSnapshot.HCContributorCount().ToString();
        line += " rows=" + reply.Lines.Count().ToString() + " truncated=" + dropped.ToString();
        line += " state=" + state + " reason=" + reason + " runtime=PENDING";
        if (reply.Lines.Count() < 64) { reply.Lines.Insert(line); }
    }

    static void HCAdminRows(HCAdminReply reply, bool authorized, float now)
    {
        if (!authorized || !reply) { return; }
        array<string> rows = HCRows(now);
        HCAppend(reply, rows, s_Refused);
    }
}
