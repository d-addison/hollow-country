// HC-16 / #143 supersedes LC-T416's abstract raider combat and casualties.
// Eligibility remains a scheduling policy, not evidence of physical attackers.
// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:397 FileExist. No engine/Expansion actor request is invented.
class HCCampProbes
{
    protected static string s_Refusal;
    protected static bool s_AdmissionPrinted;
    protected static bool s_Enabled;

    static bool HCEnabled()
    {
        if (!s_AdmissionPrinted)
        {
            s_Enabled = !FileExist("$profile:HollowCountry/acceptance/camp_probes.disable");
            Print(HCV2Admission.Line("CampProbes", s_Enabled, "HC-16-PROBE", false) + " runtime=PENDING");
            s_AdmissionPrinted = true;
        }
        return s_Enabled;
    }

    static void HCStart()
    {
        if (HCEnabled())
        {
            HCBaseRaid.HCEnabled();
            if (!HCBaseRaid.HCGet()) { HCRefuse("PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE"); }
        }
    }

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        Print("[HC Plan] HC-16 probes=dispatch_pending reason=" + reason + " runtime=PENDING");
    }

    protected static ref HCBaseRaidPort s_Visitor;
    protected static ref HCOperationalStatus s_VisitorStatus = new HCOperationalStatus;
    protected static bool s_VisitorStarted;
    protected static bool s_VisitorEnabled;

    static void HCBindVisitor(HCBaseRaidPort visitor) { s_Visitor = visitor; }
    static HCBaseRaidPort HCVisitor() { return s_Visitor; }
    static bool HCVisitorOwns(string lease) { return s_Visitor && s_Visitor.HCOwns(lease); }

    static bool HCVisitorsEnabled()
    {
        if (!s_VisitorStarted)
        {
            s_VisitorEnabled = !FileExist("$profile:HollowCountry/acceptance/camp_visitors.disable");
            s_VisitorStarted = true;
            Print(HCV2Admission.Line("CampVisitors", s_VisitorEnabled, "HC-16-VISIT", false) + " runtime=PENDING");
        }
        return s_VisitorEnabled;
    }

    static HCOperationalStatus HCGetOperationalStatus()
    {
        if (!HCCampProbes.HCVisitorsEnabled() || !HCCampProbes.HCEnabled()) { s_VisitorStatus.HCPublish("off", "camp_visitors_or_probes_operator_disabled"); return s_VisitorStatus; }
        if (!HCBaseRaid.HCEnabled())
        {
            HCOperationalStatus baseStatus = HCBaseRaid.HCGetOperationalStatus();
            s_VisitorStatus.HCPublish(baseStatus.HCState(), baseStatus.HCReason());
            return s_VisitorStatus;
        }
        if (!s_Visitor) { s_VisitorStatus.HCPublish("degraded", "CAMP_VISITOR_PROVIDER_UNAVAILABLE"); return s_VisitorStatus; }
        if (!s_Visitor.HCReady()) { s_VisitorStatus.HCPublish("degraded", s_Visitor.HCRefusal()); return s_VisitorStatus; }
        s_VisitorStatus.HCPublish("ready", "physical_visitor_provider_bound_runtime_pending");
        string waiting = s_Visitor.HCWaitingReason();
        if (waiting != "") { s_VisitorStatus.HCPublish("ready", waiting); }
        return s_VisitorStatus;
    }

    static bool HCRequestRaidParty(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now, out string reason)
    {
        reason = "camp_probes.disable";
        if (!HCCampProbes.HCEnabled()) { return false; }
        reason = "BASE_RAID_TIER_DAY_HIDDEN_OR_COOLDOWN";
        if (!HCCampProbes.Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastProbe, scan.Hidden(burning))) { return false; }
        reason = "base-raid-warning-started; runtime=PENDING";
        if (HCBaseRaid.HCWarn(module, camp, scan, now)) { return true; }
        reason = HCBaseRaid.HCRefusal();
        return false;
    }

    // Visits share the conservative probe tier/day/hidden/three-day policy.
    // LastVisit is independent of raid cooldown; no metadata/body fiction.
    static bool HCRequestVisitorParty(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now, out string reason)
    {
        HCOperationalStatus status = HCCampProbes.HCGetOperationalStatus();
        reason = status.HCReason();
        if (status.HCState() != "ready") { HCCampProbes.HCRefuse(status.HCReason()); return false; }
        reason = "CAMP_VISITOR_TIER_DAY_HIDDEN_OR_COOLDOWN";
        if (!HCCampProbes.Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastVisit, scan.Hidden(burning))) { return false; }
        reason = "CAMP_VISITOR_PARTY_NOT_OBSERVED";
        if (!s_Visitor.HCSeen(camp, scan)) { HCCampProbes.HCRefuse("CAMP_VISITOR_PARTY_NOT_OBSERVED"); return false; }
        reason = "CAMP_VISITOR_ATTENDED_OR_OBSERVED";
        if (!HCBaseRaid.HCUnattended(module, camp, camp.Position)) { HCCampProbes.HCRefuse("CAMP_VISITOR_ATTENDED_OR_OBSERVED"); return false; }
        reason = "CAMP_VISITOR_RESERVATION_OR_PERSISTENCE_REFUSED";
        if (!s_Visitor.HCVisit(module, camp, now)) { HCCampProbes.HCRefuse("CAMP_VISITOR_RESERVATION_OR_PERSISTENCE_REFUSED"); return false; }
        reason = "camp-visitor-reserved-walk-pending; runtime=PENDING";
        return true;
    }

    // #212: a group must hold its claim for the tier-3 day threshold (14
    // elapsed real days), AND the existing world day gate still applies in
    // HCRequest*Party. Stored native cargo is required; no tier/hearth gain.
    // Reuse Eligible so the threshold/cooldown policy has one authority.
    static string HCClaimEligibility(HCBuildingClaimRecord row, int now, bool stored, bool hidden, bool raid)
    {
        if (!row || !row.Anchor || now < row.ClaimedUtc || now < 1) { return "CLAIM_CLOCK_OR_ANCHOR_INVALID"; }
        int heldDays = (now - row.ClaimedUtc) / 86400;
        if (!HCCampProbes.Eligible(3, heldDays, now, 0, false)) { return "CLAIM_HOLD_DAYS"; }
        if (!stored) { return "CLAIM_NO_STORED_ITEMS"; }
        if (hidden) { return "CLAIM_HIDDEN"; }
        int last = row.Anchor.LastVisit;
        if (raid) { last = row.Anchor.LastProbe; }
        if (!HCCampProbes.Eligible(3, heldDays, now, last, false))
        {
            if (raid) { return "CLAIM_PROBE_COOLDOWN"; }
            return "CLAIM_VISIT_COOLDOWN";
        }
        return "";
    }

    static bool Eligible(int tier, int day, int now, int last, bool hidden)
    {
        if (tier != 3 || day < 14 || hidden || now < 1 || now < last) { return false; }
        if (last > 0 && now - last < 259200) { return false; }
        return true;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now)
    {
        if (!HCEnabled()) { return; }
        if (camp.ProbePhase > 0)
        {
            // Clear old abstract leases once; never turn them into casualties.
            camp.ProbePhase = 0;
            camp.ProbeUntil = 0;
            module.HCRequestCheckpoint(now);
            return; // A later scan may warn only after this metadata is durable.
        }
        if (!Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastProbe, scan.Hidden(burning))) { return; }
        HCBaseRaid.HCWarn(module, camp, scan, now);
    }
}
