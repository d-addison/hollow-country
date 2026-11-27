// Entry-local roster port: native scripts-1.30.164289 3_Game/Global/Game.c:945;
// resolver identity/life: Entities/Man.c:21, gameplay.c:368, Entities/Object.c:517.
// HC-26 spec/plan/task: Wave 2 group presentation privacy. Runtime PENDING.
// Uses existing Broadcast/Connected/Disconnected callbacks; no new tick/RPC.
// Auth is canonical server peer + native sender identity, never keybind state.
// Native references below also cover lifecycle cleanup and bounded logs.
// #131. No periodic scan/tick work. Per admitted ping: <=90 cache rows and
// <=90 connected peers, bounded existing group lookup; <=90 pins per collection.
// Feature disabled: service returns DISABLED before any ping allocation.
// Native scripts-1.30.164289: 3_Game/gameplay.c:636 GetGame;
// 3_Game/Global/Game.c:914 GetTickTime; :1120 IsServer;
// Entities/Object.c:287/517 GetPosition/IsAlive; Entities/Man.c:21 GetIdentity;
// 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious;
// 3_Game/Client/Notifications/NotificationSystem.c:125 SendNotificationToPlayerExtended;
// 1_Core/proto/EnScript.c:380/394/399/407/470 Count/Find/Get/Insert/RemoveOrdered;
// EnConvert.c:30 ToString; EnString.c:113/199 Substring/Length; EnDebug.c:96 Print.
// RPC/nonce/expiry use existing
// HCGroupService/HCGroupPins; UTC uses HCGroupClock; no new RPC number.
class HCTeamPingRow
{
    string Account;
    string Session;
    int GroupId;
    int Epoch;
    int At;
    ref HCGroupPlace Pin;
}
class HCTeamPingModule : HCModule
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    protected static HCTeamPingModule s_Instance;
    protected ref array<ref HCTeamPingRow> m_Rows;
    protected bool m_AdmissionPrinted;
    protected bool m_OffPrinted;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected int m_PruneCursor;
    protected int m_Expired;
    protected int m_Refused;
    protected string m_LastRefusal = "none";
    void HCTeamPingModule() { m_Status.HCPublish("off", "not_started"); }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (s_Instance != this) { return m_Status; }
        HCGroupService groups = HCGroupService.Get();
        string fault;
        if (!groups || !groups.HCPresentationReady()) { fault = "group_service_unavailable"; }
        HCModuleReadiness.HCDerive(m_Status, m_Rows != null, "", fault, "server_handlers_ready_runtime_pending");
        return m_Status;
    }
    static HCTeamPingModule Get() { return s_Instance; }
    override string GetName() { return "TeamPing"; }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableTeamPing && settings.EnableGroups;
        if (!enabled && !m_OffPrinted)
        {
            m_OffPrinted = true;
            m_Status.HCPublish("off", "feature_preference");
            HCReport("none", 0);
        }
        return enabled;
    }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || !GetGame().IsServer() || s_Instance) { return; }
        m_StatusLogLine = "";
        m_StatusLogAt = 0;
        HCGroupService groups = HCGroupService.Get();
        if (!groups || !groups.HCPresentationReady())
        {
            m_Status.HCPublish("refused", "group_service_unavailable");
            HCReport("group_service_unavailable", 0);
            return;
        }
        HCGCCampGroupConfig.Get();
        m_Rows = new array<ref HCTeamPingRow>;
        s_Instance = this;
        groups.HCPingPreference(true);
        m_Status.HCPublish("ready", "server_handlers_ready_runtime_pending");
        HCReport("none", 0);
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("TeamPing", true, "W5-131", false));
            m_AdmissionPrinted = true;
        }
    }
    static string HCStatus(int status)
    {
        if (status == 0) { return "OK"; }
        if (status == 1) { return "hurt"; }
        if (status == 2) { return "need help"; }
        return "";
    }
    int HCReceive(HCGroupPeer peer, int status, map<string, PlayerBase> hcPlayers)
    {
        if (s_Instance != this || !GetGame().IsServer()) { return HCGroupCode.DISABLED; }
        HCGroupService service = HCGroupService.Get();
        if (!service || !service.HCPresentationReady()) { HCReport("group_service_unavailable", 0); return HCGroupCode.DISABLED; }
        HCGroupRecord group = service.HCPingGroup(peer, hcPlayers);
        if (!group) { HCReport("sender_identity_membership_or_life", 0); return HCGroupCode.DENIED; }
        string label = HCStatus(status);
        if (label == "") { HCReport("status", 0); return HCGroupCode.INVALID; }
        int now = HCGroupClock.Utc();
        if (!HCGroupRules.DeadlineFits(now, HCGCCampGroupConfig.Get().TeamPingSeconds)) { HCReport("clock", 0); return HCGroupCode.DENIED; }
        HCTeamPingRow previous;
        for (int index = m_Rows.Count() - 1; index >= 0; index--)
        {
            HCTeamPingRow cached = m_Rows.Get(index);
            if (now < cached.At) { HCReport("clock", 0); return HCGroupCode.RATE; }
            if (now - cached.At >= HCGCCampGroupConfig.Get().TeamPingSeconds) { m_Rows.RemoveOrdered(index); if (m_Expired < 1000000) { m_Expired++; } continue; }
            if (cached.Account == peer.Id) { previous = cached; }
        }
        if (previous && now - previous.At < HCGCCampGroupConfig.Get().TeamPingCooldownSeconds) { HCReport("sender_rate", 0); return HCGroupCode.RATE; }
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = service.HCPlayerOf(hcPlayers, peer.Id);
        if (!hcPeerPlayer) { HCReport("sender_identity_membership_or_life", 0); return HCGroupCode.DENIED; }
        vector actual = hcPeerPlayer.GetPosition();
        if (!HCGroupRules.PositionValid(actual)) { HCReport("position", 0); return HCGroupCode.INVALID; }
        if (!previous)
        {
            if (m_Rows.Count() >= HCGCCampGroupConfig.Get().TeamPingRows) { HCReport("receipt_cap", 0); return HCGroupCode.LIMIT; }
            previous = new HCTeamPingRow;
            previous.Account = peer.Id;
            m_Rows.Insert(previous);
        }
        previous.Session = peer.Session;
        previous.GroupId = group.Id;
        previous.Epoch = group.Epoch;
        previous.At = now;
        previous.Pin = new HCGroupPlace;
        // Keep both the name and pin id inside the existing validated DTO limits.
        previous.Pin.Id = "hc-ping:" + group.Id.ToString() + ":" + peer.Session;
        string shortName = peer.Name;
        if (shortName == "") { shortName = "Teammate"; }
        if (shortName.Length() > 48) { shortName = shortName.Substring(0, 48); }
        previous.Pin.Name = shortName + ": " + label;
        previous.Pin.Position = actual;
        previous.Pin.Radius = HCGCCampGroupConfig.Get().TeamPingRadiusMeters;
        previous.Pin.HCPinExpiresUtc = now + HCGCCampGroupConfig.Get().TeamPingSeconds;
        int recipients = service.HCPingDeliver(group, peer, label, hcPlayers);
        HCReport("none", recipients);
        HCReached.Mark("team_ping.received");
        if (recipients > 0) { HCModuleReadiness.HCUse("TeamPing", "ping_delivered"); }
        return HCGroupCode.OK;
    }
    void HCCollect(HCGroupRecord group, int cap, array<ref HCGroupPlace> output, map<string, PlayerBase> hcPlayers)
    {
        if (s_Instance != this || !m_Rows || !group || !output || cap < 1) { return; }
        if (cap > HCGCCampGroupConfig.Get().PinLimit) { cap = HCGCCampGroupConfig.Get().PinLimit; }
        int now = HCGroupClock.Utc();
        if (now < 1) { return; }
        HCGroupStringIndex members = new HCGroupStringIndex(group.Members);
        array<ref HCTeamPingRow> hcRows1 = m_Rows;
        foreach (HCTeamPingRow row : hcRows1)
        {
            if (output.Count() >= cap) { break; }
            if (row.GroupId != group.Id || row.Epoch != group.Epoch) { continue; }
            if (!members.Has(row.Account) || now < row.At || now - row.At >= HCGCCampGroupConfig.Get().TeamPingSeconds) { continue; }
            HCGroupService service = HCGroupService.Get();
            if (!service) { continue; }
            HCGroupPeer source = service.Peer(row.Account);
            HCGroupRecord current = service.HCPingGroup(source, hcPlayers);
            if (!current || current.Id != row.GroupId || current.Epoch != row.Epoch || source.Session != row.Session) { continue; }
            if (HCGroupVisibility.HCSnapshotActive() && !service.HCPresentationAllows(HCGroupVisibility.HCRecipient(), row.Pin, hcPlayers)) { continue; }
            output.Insert(row.Pin);
        }
    }
    // No independent scan/tick. Reuse group Broadcast's lifecycle/refresh path.
    // Authorization is always checked on collection even if cleanup yields.
    void HCInvalidate(map<string, PlayerBase> hcPlayers)
    {
        if (!m_Rows || s_Instance != this) { return; }
        HCGroupService service = HCGroupService.Get();
        m_Work.HCReset(HCGCCampGroupConfig.Get().TeamPingPruneRows);
        m_Units.HCReset(HCGCCampGroupConfig.Get().TeamPingPruneRows);
        int remaining = m_Rows.Count();
        int now = HCGroupClock.Utc();
        while (remaining > 0 && m_Work.HCContinue() && m_Units.HCTake(1))
        {
            if (m_PruneCursor >= m_Rows.Count()) { m_PruneCursor = 0; }
            HCTeamPingRow row = m_Rows.Get(m_PruneCursor);
            remaining--;
            HCGroupPeer peer;
            HCGroupRecord group;
            if (service) { peer = service.Peer(row.Account); group = service.HCPingGroup(peer, hcPlayers); }
            if (!group || group.Id != row.GroupId || group.Epoch != row.Epoch || peer.Session != row.Session || now < row.At || now - row.At >= HCGCCampGroupConfig.Get().TeamPingSeconds)
            {
                m_Rows.RemoveOrdered(m_PruneCursor);
                if (m_Expired < 1000000) { m_Expired++; }
                continue;
            }
            m_PruneCursor++;
        }
        HCReport("none", 0);
    }
    void HCForget(string uid)
    {
        if (!m_Rows) { return; }
        for (int index = m_Rows.Count() - 1; index >= 0; index--)
        {
            if (m_Rows.Get(index).Account == uid) { m_Rows.RemoveOrdered(index); }
        }
    }
    bool HCVisible(string uid, HCGroupPlace pin, map<string, PlayerBase> hcPlayers)
    {
        if (s_Instance != this || !m_Rows || !pin) { return false; }
        HCGroupService service = HCGroupService.Get();
        if (!service || !service.HCPresentationRange(uid, pin.Position, hcPlayers)) { return false; }
        HCGroupPeer recipient = service.Peer(uid);
        int now = HCGroupClock.Utc();
        HCTeamPingRow selected;
        array<ref HCTeamPingRow> hcRows2 = m_Rows;
        foreach (HCTeamPingRow row : hcRows2)
        {
            if (row.Pin.Id != pin.Id || now < row.At || now - row.At >= HCGCCampGroupConfig.Get().TeamPingSeconds) { continue; }
            selected = row;
            break;
        }
        if (!selected) { return false; }
        HCGroupPeer peer = service.Peer(selected.Account);
        HCGroupRecord group = service.HCPingGroup(peer, hcPlayers);
        if (!group || group.Id != selected.GroupId || group.Epoch != selected.Epoch || peer.Session != selected.Session) { return false; }
        return group.Members.Find(uid) >= 0 && service.VisibilityAllows(peer, recipient, hcPlayers);
    }
    void HCReport(string reason, int recipients)
    {
        if (reason != "none")
        {
            if (m_Refused < 1000000) { m_Refused++; }
            m_LastRefusal = reason;
        }
        float now = GetGame().GetTickTime();
        string state = HCGetOperationalStatus().HCState();
        string head = "[HC Plan] HC-26 group_recipients=" + recipients.ToString() + " expired=" + m_Expired.ToString() + " refused=" + m_LastRefusal;
        string statusLine = head + " state=" + state + " refusals=" + m_Refused.ToString() + " runtime=PENDING";
        // First receipt, changed content, or one unchanged heartbeat per 30 minutes.
        float statusNow = now;
        if (statusLine != m_StatusLogLine || statusNow < m_StatusLogAt || statusNow - m_StatusLogAt >= 1800)
        {
            Print("" + statusLine);
            m_StatusLogLine = statusLine;
            m_StatusLogAt = statusNow;
        }
        m_LastRefusal = "none";
    }
    override void OnStop()
    {
        map<string, PlayerBase> hcPlayers = HCGroupService.HCBuildPlayers();
        if (s_Instance == this) { s_Instance = null; }
        HCGroupService groups = HCGroupService.Get();
        if (groups) { groups.HCPingPreference(false); }
        m_Rows = null;
        m_Status.HCPublish("off", "server_stop_requested");
        HCReport("none", 0);
        // FULL replaces cached Places, including when Groups remains enabled.
        if (groups) { groups.Broadcast(hcPlayers); }
    }
}
modded class HCGroupService
{
    void HCPingPreference(bool enabled)
    {
        if (m_Config) { m_Config.HCTeamPingEnabled = enabled; }
    }
    bool HCPresentationReady() { return m_Healthy && m_Config && m_Config.Enabled; }
    HCGroupRecord HCPresentationGroup(string uid)
    {
        if (!HCPresentationReady() || !m_State) { return null; }
        return HCGroupRules.FindGroup(m_State, uid);
    }
    HCGroupRecord HCPingGroup(HCGroupPeer peer, map<string, PlayerBase> hcPlayers)
    {
        if (!HCPresentationReady() || !Live(peer, hcPlayers) || !m_State) { return null; }
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(hcPlayers, peer.Id);
        PlayerIdentity hcPeerIdentity;
        if (hcPeerPlayer) hcPeerIdentity = hcPeerPlayer.GetIdentity();
        HCGroupPeer hcFoundPeer1 = Peer(peer.Id);
        if (!hcPeerPlayer || !hcPeerIdentity || hcFoundPeer1 != peer || hcPeerIdentity.GetId() != peer.Id) { return null; }
        if (!hcPeerPlayer.IsAlive() || hcPeerPlayer.IsUnconscious()) { return null; }
        return HCGroupRules.FindGroup(m_State, peer.Id);
    }
    bool HCPresentationRange(string uid, vector position, map<string, PlayerBase> hcPlayers)
    {
        HCGroupPeer recipient = Peer(uid);
        HCGroupRecord recipientGroup = HCPingGroup(recipient, hcPlayers);
        if (!recipientGroup || !HasGPS(recipient, hcPlayers)) { return false; }
        // Reuse validated operator MaxIconDistance (default ~1 km network bubble).
        PlayerBase hcRecipientPlayer;
        if (recipient) hcRecipientPlayer = HCPlayerOf(hcPlayers, recipient.Id);
        return HCGroupVisibility.HCWithinRange(position, hcRecipientPlayer.GetPosition(), m_Config.MaxIconDistance);
    }
    bool HCPresentationAllows(string uid, HCGroupPlace pin, map<string, PlayerBase> hcPlayers)
    {
        if (!pin) { return false; }
        if (pin.Id.IndexOf("hc-ping:") == 0)
        {
            if (!HCPresentationRange(uid, pin.Position, hcPlayers)) { return false; }
            HCTeamPingModule pings = HCTeamPingModule.Get();
            return pings && pings.HCVisible(uid, pin, hcPlayers);
        }
        // Corpse-run pins are gated on membership/life only, never on the
        // recipient's distance: a respawned teammate kilometres away still
        // needs the pin (MapIcons semantics, HCGroupService member rows).
        HCGroupPeer hcFoundPeer1 = Peer(uid);
        HCGroupRecord foundGroup = HCPingGroup(hcFoundPeer1, hcPlayers);
        if (!foundGroup) { return false; }
        // No live corpse-session observation exists for cached death pins.
        // Never invent corpse LOS/radio; refuse when either is required.
        if (m_Config.RequireLOS || m_Config.RequireRadio)
        {
            HCDeathPins deaths = HCDeathPins.Get();
            if (deaths) { deaths.HCLog("death_los_radio_unavailable"); }
            return false;
        }
        return true;
    }
    int HCPingDeliver(HCGroupRecord group, HCGroupPeer source, string label, map<string, PlayerBase> hcPlayers)
    {
        HCGroupRecord current = HCPingGroup(source, hcPlayers);
        if (!group || !current || current.Id != group.Id || current.Epoch != group.Epoch) { return 0; }
        int count = 0;
        HCGroupStringIndex members = new HCGroupStringIndex(group.Members);
        array<ref HCGroupPeer> hcRows3 = m_Peers;
        foreach (HCGroupPeer recipient : hcRows3)
        {
            HCGroupRecord deliveryGroup = HCPingGroup(recipient, hcPlayers);
            if (!deliveryGroup || !members.Has(recipient.Id)) { continue; }
            PlayerBase hcSourcePlayer;
            if (source) hcSourcePlayer = HCPlayerOf(hcPlayers, source.Id);
            if (!HCPresentationRange(recipient.Id, hcSourcePlayer.GetPosition(), hcPlayers) || !VisibilityAllows(source, recipient, hcPlayers)) { continue; }
            // The sender sees its own marker but is not told about itself.
            PlayerBase hcRecipientPlayer;
            if (recipient) hcRecipientPlayer = HCPlayerOf(hcPlayers, recipient.Id);
            if (recipient.Id != source.Id) { NotificationSystem.SendNotificationToPlayerExtended(hcRecipientPlayer, 5, "Teammate status", source.Name + ": " + label); }
            SendSnapshot(recipient, HCGroupSnapshotKind.FULL, 0, hcPlayers);
            count++;
        }
        return count;
    }
    override void SendSnapshot(HCGroupPeer peer, int kind, int requestId, map<string, PlayerBase> hcPlayers, PlayerBase hint = null)
    {
        if (!peer) return;
        // Gate at collection, independently of KnownPlaces modded-link order.
        bool previousActive = HCGroupVisibility.HCSnapshotActive();
        string previousUid = HCGroupVisibility.HCRecipient();
        string uid = "";
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(hcPlayers, peer.Id, hint);
        PlayerIdentity hcPeerIdentity;
        if (hcPeerPlayer) hcPeerIdentity = hcPeerPlayer.GetIdentity();
        HCGroupPeer hcFoundPeer1 = Peer(peer.Id);
        if (Live(peer, hcPlayers, hint) && hcFoundPeer1 == peer && hcPeerIdentity.GetId() == peer.Id) { uid = peer.Id; }
        HCGroupVisibility.HCSnapshot(true, uid);
        super.SendSnapshot(peer, kind, requestId, hcPlayers, hint);
        HCGroupVisibility.HCSnapshot(previousActive, previousUid);
    }
    override void Broadcast(map<string, PlayerBase> hcPlayers)
    {
        HCTeamPingModule pings = HCTeamPingModule.Get();
        if (pings) { pings.HCInvalidate(hcPlayers); }
        HCDeathPins deaths = HCDeathPins.Get();
        if (deaths) { deaths.HCInvalidate(hcPlayers); }
        super.Broadcast(hcPlayers);
    }
    override void Connected(PlayerIdentity identity, PlayerBase player, map<string, PlayerBase> hcPlayers = null)
    {
        map<string, PlayerBase> ownedPlayers = hcPlayers;
        if (!ownedPlayers) { ownedPlayers = HCGroupService.HCBuildPlayers(); }
        PlayerIdentity connectedIdentity;
        if (player) connectedIdentity = player.GetIdentity();
        if (m_Healthy && identity && player && HCPlayerIdentity.Same(connectedIdentity, identity))
        {
            HCTeamPingModule pings = HCTeamPingModule.Get();
            if (pings) { pings.HCForget(identity.GetId()); }
        }
        super.Connected(identity, player, ownedPlayers);
    }
    override void Disconnected(PlayerIdentity identity, map<string, PlayerBase> hcPlayers = null)
    {
        map<string, PlayerBase> ownedPlayers = hcPlayers;
        if (!ownedPlayers) { ownedPlayers = HCGroupService.HCBuildPlayers(); }
        if (identity)
        {
            HCGroupPeer peer = Peer(identity.GetId());
            HCTeamPingModule pings = HCTeamPingModule.Get();
            if (pings && peer) { pings.HCForget(peer.Id); }
        }
        super.Disconnected(identity, ownedPlayers);
    }
    void HCPresentationFell(PlayerBase player, map<string, PlayerBase> hcPlayers = null)
    {
        map<string, PlayerBase> ownedPlayers = hcPlayers;
        if (!ownedPlayers) { ownedPlayers = HCGroupService.HCBuildPlayers(); }
        if (!m_Healthy || !player || !player.GetIdentity()) { return; }
        PlayerIdentity playerIdentity = player.GetIdentity();
        if (!playerIdentity) return;
        HCGroupPeer peer = Peer(playerIdentity.GetId());
        PlayerBase hcPeerPlayer;
        if (peer) hcPeerPlayer = HCPlayerOf(ownedPlayers, peer.Id);
        if (!Live(peer, ownedPlayers) || hcPeerPlayer != player) { return; }
        HCTeamPingModule pings = HCTeamPingModule.Get();
        if (pings) { pings.HCForget(peer.Id); Broadcast(ownedPlayers); }
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTeamPingModule);
    }
}
