// HC-39 / #147. Spec -> plan -> task: two content profiles for the same
// existing HC-10 RAIDER foot party. No module, scheduler, spawner, population
// cap, inventory owner, door override or separate gameplay state machine.
// HC-38 owns situation validation/barriers/history; HC-16 owns funded camps;
// HC-37 owns opposed-faction observations; HC-10 owns body/cargo fold-back.
// HC-38 owns a bounded named-profile registry; cooldown/combat/custody
// observations are still unverified and never inferred from an empty history.
// Native scripts-1.30.164289, inspected read-only:
// 3_Game/Global/Game.c:1120 IsServer; 3_Game/gameplay.c:636 GetGame;
// 1_Core/proto/EnDebug.c:96 Print; EnString.c:199 Length;
// EnScript.c:380 Count, :394 Find; 3_Game/tools/JsonFileLoader.c:69 LoadData.
// 1_Core/proto/EnSystem.c:397 FileExist.
// All remaining calls are existing HC ports. No N17 AI SDK is inferred.

class HCCampRaidProfile
{
    string Id;
    string Kind;
    string PartyRole;
    string FactionId;
    int CooldownSeconds;
}

class HCCampRaidConfig
{
    // Zero (including a native missing-int load) is explicitly refused.
    // Legacy Enabled is retained for decoding; acceptance/w38_raids.disable is the opt-out.
    int Version;
    bool Enabled;
    ref array<ref HCCampRaidProfile> Profiles = new array<ref HCCampRaidProfile>;
}

// Trusted server capability port. HCXAIRaidAdapter uses the shared live-party
// implementation; HC-38 alone starts actors after its durable intent barrier.
// Availability is an observation of the bound provider, never a JSON ready flag.
class HCCampRaidActorPort : HCSituationActorPort
{
    override string HCRefusal() { return "RAID_PROVIDER_UNAVAILABLE"; }
}

class HCCampRaidActors
{
    protected static ref HCCampRaidActorPort s_Adapter;
    static void HCBind(HCCampRaidActorPort adapter) { s_Adapter = adapter; }
    static HCCampRaidActorPort HCGet()
    {
        if (s_Adapter) { return s_Adapter; }
        return new HCCampRaidActorPort;
    }
}

class HCCampRaidSituation
{
    protected ref HCCampRaidConfig m_Config;
    protected static ref HCCampRaidConfig s_Profiles;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Enabled;
    protected int m_Reports;
    protected int m_Authored;
    protected string m_Effective = "off";
    protected string m_Reason = "not_started";

    static bool HCProfileValid(HCCampRaidProfile profile)
    {
        if (!profile || profile.PartyRole != "RAIDER" || profile.FactionId != "raiders") { return false; }
        if (profile.CooldownSeconds < 60 || profile.CooldownSeconds > 604800) { return false; }
        if (profile.Kind == "raid") { return profile.Id == "camp-raid"; }
        if (profile.Kind == "column") { return profile.Id == "foot-column"; }
        return false;
    }

    static bool HCValidConfig(HCCampRaidConfig config)
    {
        if (!config || config.Version != 1 || !config.Profiles || config.Profiles.Count() != 2) { return false; }
        if (!HCProfileValid(config.Profiles[0]) || !HCProfileValid(config.Profiles[1])) { return false; }
        return config.Profiles[0].Kind == "raid" && config.Profiles[1].Kind == "column";
    }

    // Read-only preflight, called ONLY by the existing budgeted server dispatch
    // with its exact owned proposal and durable HC-38 history, never from RPC.
    // lastEndedAt: -1/negative = unknown; 0 = explicit first-ever receipt from
    // the durable owner; positive = observed prior closure. Never deserialize a
    // missing history int and call its zero a first-ever receipt.
    // Exit refs are syntactic provenance ONLY. Even a successful preflight is
    // not surveyed geometry, route completion, cargo custody or admission.
    static string HCValidate(HCCampRaidProfile profile, HCSituationState opportunity, HCStoryProgress progress, HCWorldProposal proposal, string targetLease, int now, int lastEndedAt, string exitRef, string returnRef)
    {
        if (!HCProfileValid(profile)) { return "RAID_PROFILE_INVALID"; }
        if (!opportunity || !HCSituationDirector.HCValid(opportunity, progress)) { return "RAID_SITUATION_INVALID"; }
        if (opportunity.Phase != "pending") { return "RAID_SITUATION_NOT_PENDING"; }
        if (now < 1 || now > 999000000 || now < opportunity.DueAt || now >= opportunity.EndsAt) { return "RAID_SITUATION_NOT_DUE"; }
        if (!proposal || !HCWorldLimits.Token(proposal.Id)) { return "RAID_PARTY_LEASE_UNOWNED"; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(proposal.Id);
        if (!HCAIPartyIdentity.HCValid(identity) || proposal.Identity != identity) { return "RAID_PARTY_LEASE_UNOWNED"; }
        if (proposal.Kind != profile.PartyRole || proposal.FactionId != profile.FactionId) { return "RAID_PARTY_ROLE_MISMATCH"; }
        if (lastEndedAt < 0 || lastEndedAt > now) { return "RAID_COOLDOWN_UNOBSERVED"; }
        if (lastEndedAt > 0 && now - lastEndedAt < profile.CooldownSeconds) { return "RAID_COOLDOWN_ACTIVE"; }
        if (!HCWorldLimits.Token(exitRef) || !HCWorldLimits.Token(returnRef) || exitRef == returnRef) { return "RAID_ROUTE_EXITS_MISSING"; }
        // A visible column does not need a victim, enter a house or debit a camp.
        if (profile.Kind == "column") { return ""; }
        HCAIPartyIdentity target = HCWorldMaterializer.HCIdentity(targetLease);
        if (!HCAIPartyIdentity.HCValid(target) || targetLease == proposal.Id) { return "RAID_TARGET_LEASE_UNOWNED"; }
        if (target.HCGeneration() != identity.HCGeneration()) { return "RAID_TARGET_LEASE_UNOWNED"; }
        if (target.HCPartyId() == identity.HCPartyId() || target.HCCargoId() == identity.HCCargoId()) { return "RAID_TARGET_LEASE_UNOWNED"; }
        HCHoldouts camps = HCHoldouts.Get();
        if (!camps) { return "RAID_FUNDED_TARGET_UNAVAILABLE"; }
        HCAICampRoutineView view = camps.HCRoutineView(target);
        if (!view || !view.Home || view.Level < 0 || view.Supply < 1 || view.Population < 1) { return "RAID_FUNDED_TARGET_UNAVAILABLE"; }
        if (target.HCCampId() != "camp:" + view.Home.Id || view.Home.CacheRef.Length() < 1) { return "RAID_FUNDED_TARGET_UNAVAILABLE"; }
        if (view.Home.State != "OCCUPIED" && view.Home.State != "ALERT") { return "RAID_FUNDED_TARGET_UNAVAILABLE"; }
        // HC-38's scene clock has a fixed 2020 origin. Camp lockout is Unix
        // UTC; reuse its owner clock instead of comparing unlike epochs.
        int campNow = HCWorldClock.UTC();
        if (campNow < 1) { return "RAID_TARGET_CLOCK_UNAVAILABLE"; }
        if (campNow < view.Home.ReoccupyAfter) { return "RAID_TARGET_LOCKOUT"; }
        if (HCWorldFactionCatalog.Relation(proposal.FactionId, view.Home.FactionId) != -1) { return "RAID_TARGET_NOT_HOSTILE"; }
        return "";
    }

    void HCReport(string kind, string party, string outcome)
    {
        // Lifetime-bounded diagnostics; no hidden retry, scan or save loop.
        if (m_Reports >= 16) { return; }
        m_Reports++;
        string line = "[HC Plan] HC-39 kind=" + kind + " party=" + party + " outcome=" + outcome;
        line += " state=" + m_Effective + " refusal=" + m_Reason;
        string authored = "0";
        if (m_Authored == 2) { authored = "2"; }
        Print(line + " authored=" + authored + " admitted=0 observed=0 count_cap=2 report_cap=16 runtime=PENDING");
    }

    HCOperationalStatus HCStatus()
    {
        if (m_Enabled)
        {
            HCCampRaidActorPort actors = HCCampRaidActors.HCGet();
            m_Effective = "refused";
            m_Reason = actors.HCRefusal();
            if (actors.HCReady()) { m_Effective = "ready"; m_Reason = "live_raid_provider_available"; }
            m_Status.HCPublish(m_Effective, m_Reason);
        }
        return m_Status;
    }

    static HCCampRaidConfig HCLoad()
    {
        string encoded;
        string error;
        HCCampRaidConfig config;
        if (!HCGroupIO.Read("$mission:hollow-country/events/raids.json", 8192, encoded)) { return null; }
        if (!JsonFileLoader<HCCampRaidConfig>.LoadData(encoded, config, error)) { return null; }
        if (!HCValidConfig(config)) { return null; }
        return config;
    }

    static int HCCooldown(string kind)
    {
        if (!s_Profiles || !HCValidConfig(s_Profiles)) { return -1; }
        array<ref HCCampRaidProfile> profiles = s_Profiles.Profiles;
        foreach (HCCampRaidProfile profile : profiles)
        {
            if (profile.Kind == kind) { return profile.CooldownSeconds; }
        }
        return -1;
    }

    bool HCProfilesEnabled() { return m_Enabled; }

    void HCOpen(HCCampRaidConfig config, bool enabled)
    {
        m_Enabled = false;
        m_Config = null;
        m_Authored = 0;
        if (HCValidConfig(config)) { m_Authored = 2; }
        m_Effective = "off";
        m_Reason = "operator_off";
        if (HCV2Admission.Admitted(enabled) && !FileExist("$profile:HollowCountry/acceptance/w38_raids.disable"))
        {
            m_Effective = "refused";
            m_Reason = "RAID_CONFIG_INVALID";
            if (HCValidConfig(config) && GetGame() && GetGame().IsServer())
            {
                m_Config = config;
                s_Profiles = config;
                m_Enabled = true;
                HCCampRaidActorPort actors = HCCampRaidActors.HCGet();
                m_Reason = actors.HCRefusal();
                if (actors.HCReady()) { m_Effective = "ready"; m_Reason = "live_raid_provider_available"; }
                Print(HCV2Admission.Line("CampRaids", true, "w38_raids", false) + " runtime=PENDING");
            }
        }
        m_Status.HCPublish(m_Effective, m_Reason);
        HCReport("raid,column", "none", m_Effective);
    }

    bool HCAdmit(HCCampRaidProfile profile, HCSituationState opportunity, HCStoryProgress progress, HCWorldProposal proposal, string targetLease, int now, int lastEndedAt, string exitRef, string returnRef)
    {
        if (!m_Enabled || !GetGame() || !GetGame().IsServer()) { return false; }
        if (!m_Config || m_Config.Profiles.Find(profile) < 0) { return false; }
        m_Reason = HCValidate(profile, opportunity, progress, proposal, targetLease, now, lastEndedAt, exitRef, returnRef);
        bool admitted = false;
        if (m_Reason == "")
        {
            admitted = HCCampRaidActors.HCGet().HCReady();
            if (!admitted) { m_Reason = HCCampRaidActors.HCGet().HCRefusal(); }
        }
        m_Effective = "refused";
        if (admitted) { m_Effective = "ready"; m_Reason = "raid_preflight_valid"; }
        string party = "none";
        if (proposal && HCAIPartyIdentity.HCValid(proposal.Identity)) { party = proposal.Identity.HCPartyId(); }
        m_Status.HCPublish(m_Effective, m_Reason);
        HCReport(profile.Kind, party, m_Effective);
        // NEVER begin, mutate the lifecycle, debit camp/cargo or release HC-10.
        // Existing provider death/cleanup/result handlers retain all ownership.
        return admitted;
    }

    void HCClose()
    {
        m_Enabled = false;
        if (s_Profiles == m_Config) { s_Profiles = null; }
        m_Config = null;
        m_Effective = "off";
        m_Reason = "owner_closed";
        m_Status.HCPublish(m_Effective, m_Reason);
        HCReport("raid,column", "none", "off");
    }
}
