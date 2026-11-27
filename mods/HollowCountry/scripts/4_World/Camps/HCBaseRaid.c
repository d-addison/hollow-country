// #151 spec -> observed local storage/door -> warned reservation -> one physical
// raid. Native scripts-1.30.164289: EnSystem.c:397 FileExist; EnDebug.c:96
// Print; EnScript.c:380 Count; Game.c:945 GetPlayers, :1120 IsServer;
// gameplay.c:636 GetGame; Object.c:287 GetPosition, :517 IsAlive, :215
// IsPendingDeletion; Man.c:21 GetIdentity; EnConvert.c:210 DistanceSq.
// Tell is the existing group-ACL warning path, HCCampModule.c:145-153.
// No offline inbox is invented; absent online recipients spend no cooldown.
class HCBaseRaidConfig
{
    int Version = 1;
    float NoticeRangeMeters = 40;
    float AttendanceRangeMeters = 500;
    float ObserverRangeMeters = 500;
    float SourceRangeMeters = 12;
    int WarningSeconds = 300;
    int RaidSeconds = 600;
    int MaxPlayers = 32;
    int MaxObjects = 128;
    int MaxDoors = 32;
    int MaxRouteNodes = 32;
    int MaxCargoScan = 32;

    bool HCValid()
    {
        HCBaseRaidConfig config = this;
        // Reject NaN and missing-field zeros; literal bounds mirror the registry.
        if (config.Version != 1 || config.NoticeRangeMeters != config.NoticeRangeMeters) { return false; }
        if (config.NoticeRangeMeters < 2 || config.NoticeRangeMeters > 100) { return false; }
        if (config.AttendanceRangeMeters != config.AttendanceRangeMeters || config.ObserverRangeMeters != config.ObserverRangeMeters) { return false; }
        if (config.SourceRangeMeters != config.SourceRangeMeters) { return false; }
        if (config.AttendanceRangeMeters < 500 || config.AttendanceRangeMeters > 1000) { return false; }
        if (config.ObserverRangeMeters < 500 || config.ObserverRangeMeters > 1000) { return false; }
        if (config.SourceRangeMeters < 2 || config.SourceRangeMeters > 12) { return false; }
        if (config.WarningSeconds < 60 || config.WarningSeconds > 600 || config.RaidSeconds < 60 || config.RaidSeconds > 600) { return false; }
        if (config.MaxPlayers < 1 || config.MaxPlayers > 32 || config.MaxObjects < 1 || config.MaxObjects > 128) { return false; }
        if (config.MaxDoors < 1 || config.MaxDoors > 32 || config.MaxRouteNodes < 1 || config.MaxRouteNodes > 32) { return false; }
        if (config.MaxCargoScan < 1 || config.MaxCargoScan > 32) { return false; }
        if (!HCOperatorSettingsRegistry.HCFind("BaseRaid.Version")) { return true; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.Version", config.Version)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.NoticeRangeMeters", config.NoticeRangeMeters)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.AttendanceRangeMeters", config.AttendanceRangeMeters)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.ObserverRangeMeters", config.ObserverRangeMeters)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.SourceRangeMeters", config.SourceRangeMeters)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.WarningSeconds", config.WarningSeconds)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.RaidSeconds", config.RaidSeconds)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.MaxPlayers", config.MaxPlayers)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.MaxObjects", config.MaxObjects)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.MaxDoors", config.MaxDoors)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.MaxRouteNodes", config.MaxRouteNodes)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("BaseRaid.MaxCargoScan", config.MaxCargoScan)) { return false; }
        return true;
    }
}

// Server capability, not JSON readiness. The addon binds its single instance.
class HCBaseRaidPort
{
    bool HCVisit(HCCampModule owner, HCCampRecord camp, int now) { return false; }
    bool HCReady() { return false; }
    string HCRefusal() { return "PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE"; }
    // Cached sensing state only; status reads must not search for a party.
    string HCWaitingReason() { return ""; }
    bool HCSeen(HCCampRecord camp, HCCampScan scan) { return false; }
    bool HCRetainedSeen(HCCampRecord camp, HCCampScan scan) { return false; }
    bool HCReserve(HCCampModule owner, HCCampRecord camp, int now) { return false; }
    void HCWarned(HCCampRecord camp, int now) {}
    void HCCancel() {}
    bool HCOwns(string lease) { return false; }
    bool HCCustodyAllowed(PlayerBase actor, EntityAI source) { return false; }
}

class HCBaseRaid
{
    protected static HCCampModule s_WarningOwner;
    protected static ref HCCampRecord s_WarningCamp;
    protected static ref HCCampScan s_WarningScan;
    protected static HCBaseRaidPort s_WarningPort;
    protected static int s_WarningReceipt;
    protected static int s_WarningUtc;

    static void HCAdvanceWarning(HCCampModule owner, int now, array<Man> roster, map<string, PlayerBase> players)
    {
        if (!s_WarningCamp || owner != s_WarningOwner) { return; }
        HCBaseRaidPort port = s_WarningPort;
        if (owner != HCCampModule.Get() || now < s_WarningUtc || now - s_WarningUtc > 60)
        {
            if (port) { port.HCCancel(); }
            s_WarningCamp = null;
            return;
        }
        if (!owner.HCDurable(s_WarningReceipt)) { return; }
        ref HCCampRecord camp = s_WarningCamp;
        s_WarningCamp = null;
        if (!HCEnabled() || !port || port != HCGet() || !port.HCReady() || !port.HCRetainedSeen(camp, s_WarningScan) || !HCRecipients(owner, camp, roster, players))
        {
            if (port) { port.HCCancel(); }
            return;
        }
        owner.Tell(camp, "Raiders have noticed your camp. A warned probe may return after a warning delay if it is unattended.", roster, players);
        port.HCWarned(camp, now);
    }

    protected static ref HCBaseRaidPort s_Port;
    protected static ref HCBaseRaidConfig s_Config;
    protected static ref HCEncounterStore<HCBaseRaidConfig> s_Store;
    protected static ref HCOperationalStatus s_Status = new HCOperationalStatus;
    protected static bool s_Started;
    protected static bool s_Enabled;
    protected static string s_Refusal;
    protected static string s_RequestRefusal;

    static void HCBind(HCBaseRaidPort port)
    {
        // s_WarningPort is raw (HCBaseRaidPort is not Managed): replacing s_Port frees the old port, so drop a
        // pending warning that still points at it instead of calling HCCancel on freed memory later.
        if (port != s_Port)
        {
            // Cancel on the old port before it is freed; HCCancel is idempotent (the adapter's OnStop already calls it).
            if (s_Port) { s_Port.HCCancel(); }
            s_WarningPort = null;
            s_WarningCamp = null;
        }
        s_Port = port;
    }
    static HCBaseRaidPort HCGet() { return s_Port; }
    static HCBaseRaidConfig HCConfig() { return s_Config; }
    static bool HCOwns(string lease) { return (s_Port && s_Port.HCOwns(lease)) || HCCampProbes.HCVisitorOwns(lease); }

    static bool HCEnabled()
    {
        if (s_Started) { return s_Enabled && s_Config != null; }
        s_Started = true;
        s_Enabled = !FileExist("$profile:HollowCountry/acceptance/base_raid.disable");
        Print(HCV2Admission.Line("BaseRaid", s_Enabled, "base_raid", false) + " runtime=PENDING");
        if (!s_Enabled) { s_Status.HCPublish("off", "operator_disabled"); return false; }
        s_Store = new HCEncounterStore<HCBaseRaidConfig>("base-raid-config");
        HCBaseRaidConfig fresh = new HCBaseRaidConfig;
        s_Config = s_Store.Load(fresh, "NoticeRangeMeters");
        string encoded = s_Store.HCTakeLoadedText();
        if (encoded != "" && !HCJsonFields.Has(encoded, "Version")) { s_Config = null; }
        if (!s_Config || !s_Config.HCValid())
        {
            s_Config = null;
            s_Status.HCPublish("degraded", "BASE_RAID_CONFIG_INVALID");
            HCRefuse("BASE_RAID_CONFIG_INVALID");
            return false;
        }
        return true;
    }

    static string HCRefusal()
    {
        if (s_RequestRefusal != "") { return s_RequestRefusal; }
        if (s_Refusal != "") { return s_Refusal; }
        return "BASE_RAID_REQUEST_REFUSED";
    }

    static void HCRefuse(string reason)
    {
        s_RequestRefusal = reason;
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        if (reason != "") { Print("[HC BaseRaid] reason=" + reason + " runtime=PENDING"); }
    }

    static HCOperationalStatus HCGetOperationalStatus()
    {
        if (!HCBaseRaid.HCEnabled()) { return s_Status; }
        // Every raid step also needs the parent probe feature; its opt-out turns raids off.
        if (!HCCampProbes.HCEnabled()) { s_Status.HCPublish("off", "camp_probes_operator_disabled"); return s_Status; }
        HCBaseRaidPort port = HCBaseRaid.HCGet();
        if (!port) { s_Status.HCPublish("degraded", "PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE"); return s_Status; }
        if (!port.HCReady()) { s_Status.HCPublish("degraded", port.HCRefusal()); return s_Status; }
        s_Status.HCPublish("ready", "base_raid_provider_bound");
        string waiting = port.HCWaitingReason();
        if (waiting != "") { s_Status.HCPublish("ready", waiting); }
        return s_Status;
    }

    static bool HCRecipients(HCCampModule owner, HCCampRecord camp, array<Man> roster = null, map<string, PlayerBase> players = null)
    {
        if (!owner || !camp || !s_Config || !GetGame() || !GetGame().IsServer()) { return false; }
        return owner.HCBaseRaidHasRecipients(camp, s_Config.MaxPlayers, roster, players);
    }

    // Same live attendance policy as HCCampTheft.HCAllowed, independently of
    // the theft opt-out. Re-read membership and positions before every action.
    static bool HCUnattended(HCCampModule owner, HCCampRecord camp, vector at)
    {
        if (!owner || owner != HCCampModule.Get() || !camp || !HCEnabled()) { return false; }
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        // #212: a retained claim target stays eligible only while its group still holds the claim.
        if (camp.AnchorKind == "claim")
        {
            if (!HCBuildingClaim.HCGet() || !HCGroupService.Get()) { return false; }
            int claimedGroup = camp.GroupId.ToInt();
            if (HCGroupService.Get().HCClaimGroupState(claimedGroup) != 1) { return false; }
            if (!HCBuildingClaim.HCGet().HCHoldsClaim(claimedGroup, camp.ClaimBuildingId)) { return false; }
        }
        array<Man> people = new array<Man>;
        GetGame().GetPlayers(people);
        if (people.Count() > s_Config.MaxPlayers) { return false; }
        map<string, PlayerBase> attendancePlayers = HCGroupService.HCPlayersFromRoster(people);
        foreach (Man person : people)
        {
            PlayerBase player = PlayerBase.Cast(person);
            if (!player || !player.IsAlive() || !player.GetIdentity()) { continue; }
            if (owner.HCGroupIdWithPlayers(player, attendancePlayers) == camp.GroupId && vector.DistanceSq(player.GetPosition(), camp.Position) <= s_Config.AttendanceRangeMeters * s_Config.AttendanceRangeMeters) { return false; }
        }
        return HCObserverTransitionGate.CanTransition(at, s_Config.ObserverRangeMeters);
    }

    static bool HCWarn(HCCampModule owner, HCCampRecord camp, HCCampScan scan, int now)
    {
        s_RequestRefusal = "BASE_RAID_DISABLED_OR_INVALID_REQUEST";
        if (s_WarningCamp || !HCBaseRaid.HCEnabled() || !owner || !camp || !scan || now < 1) { return false; }
        s_RequestRefusal = "";
        HCBaseRaidPort port = HCBaseRaid.HCGet();
        if (!port) { HCBaseRaid.HCRefuse("PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE"); return false; }
        if (!port.HCReady()) { HCBaseRaid.HCRefuse(port.HCRefusal()); return false; }
        if (!port.HCSeen(camp, scan)) { HCBaseRaid.HCRefuse("BASE_RAID_PARTY_NOT_OBSERVED"); return false; }
        if (!HCBaseRaid.HCRecipients(owner, camp)) { HCBaseRaid.HCRefuse("BASE_RAID_WARNING_RECIPIENT_OFFLINE"); return false; }
        if (!port.HCReserve(owner, camp, now)) { HCBaseRaid.HCRefuse(port.HCRefusal()); return false; }
        // Existing probe cooldown is 3 real days, stricter than one/day. Save
        // before the existing warning; uncertain IO never refunds/replays it.
        camp.LastProbe = now;
        int receipt = owner.HCRequestCheckpoint(now);
        if (receipt < 1) { port.HCCancel(); s_RequestRefusal = "BASE_RAID_PERSISTENCE_REFUSED"; return false; }
        s_WarningOwner = owner;
        s_WarningCamp = camp;
        s_WarningScan = scan;
        s_WarningPort = port;
        s_WarningReceipt = receipt;
        s_WarningUtc = now;
        return true;
    }
}

// Existing camp status refresh publishes the non-module provider observation.
// Native Game.c:914 GetTickTime; no new registry slot or scheduler.
modded class HCCampModule
{
    protected ref HCOperationalOwner m_HCBaseRaidStatus;
    protected ref HCOperationalOwner m_HCVisitorStatus;
    protected string m_HCBaseRaidLine;
    protected string m_HCVisitorLine;

    // Exact recipient list used by Tell in this synchronous camp scan; a
    // different player cache must not turn an undelivered warning into a debit.
    bool HCBaseRaidHasRecipients(HCCampRecord camp, int cap, array<Man> roster = null, map<string, PlayerBase> players = null)
    {
        array<Man> recipients = roster;
        if (!recipients)
        {
            recipients = new array<Man>;
            GetGame().GetPlayers(recipients);
        }
        if (recipients.Count() == 0 || recipients.Count() > cap || recipients.Count() > HCGCCampGroupConfig.Get().CampPlayers) { return false; }
        map<string, PlayerBase> ownedPlayers = players;
        if (!ownedPlayers) { ownedPlayers = HCGroupService.HCPlayersFromRoster(recipients); }
        foreach (Man recipient : recipients)
        {
            PlayerBase peer = PlayerBase.Cast(recipient);
            if (peer && peer.IsAlive() && !peer.IsPendingDeletion() && peer.GetIdentity() && HCGroupIdWithPlayers(peer, ownedPlayers) == camp.GroupId) { return true; }
        }
        return false;
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus inherited = super.HCGetOperationalStatus();
        if (!m_Running || !GetGame()) { return inherited; }
        if (!m_HCBaseRaidStatus) { m_HCBaseRaidStatus = HCOperationalContributors.HCRegisterOwner("BaseRaid"); }
        if (!m_HCVisitorStatus) { m_HCVisitorStatus = HCOperationalContributors.HCRegisterOwner("CampVisitors"); }
        HCOperationalStatus visitors = HCCampProbes.HCGetOperationalStatus();
        if (m_HCVisitorStatus) { m_HCVisitorStatus.HCObserve(true, visitors, GetGame().GetTickTime()); }
        HCOperationalStatus raid = HCBaseRaid.HCGetOperationalStatus();
        if (m_HCBaseRaidStatus) { m_HCBaseRaidStatus.HCObserve(true, raid, GetGame().GetTickTime()); }
        // Camps starts before the addon. Its boot-only unavailable lines are
        // superseded here on the existing 15-second status refresh, like theft.
        // Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print.
        string raidLine = "[HC CampGroup] probes=" + raid.HCState() + " reason=" + raid.HCReason();
        if (raidLine != m_HCBaseRaidLine)
        {
            m_HCBaseRaidLine = raidLine;
            Print(raidLine + " mailbox=retired runtime=PENDING");
        }
        string visitorLine = "[HC CampGroup] visitors=" + visitors.HCState() + " reason=" + visitors.HCReason();
        if (visitorLine != m_HCVisitorLine)
        {
            m_HCVisitorLine = visitorLine;
            Print(visitorLine + " runtime=PENDING");
        }
        return inherited;
    }
}
