// #131. No periodic scan/tick work. Per admitted ping: <=90 cache rows and
// <=90 connected peers, bounded existing group lookup; <=90 pins per collection.
// Feature disabled: service returns DISABLED before any ping allocation.
// Native scripts-1.30.164289: 3_Game/gameplay.c:636 GetGame;
// 3_Game/Global/Game.c:1120 IsServer;
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
    int GroupId;
    int Epoch;
    int At;
    ref HCGroupPlace Pin;
}
class HCTeamPingModule : HCModule
{
    protected static HCTeamPingModule s_Instance;
    protected ref array<ref HCTeamPingRow> m_Rows;
    protected bool m_AdmissionPrinted;
    static HCTeamPingModule Get() { return s_Instance; }
    override string GetName() { return "TeamPing"; }
    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableTeamPing) { return false; }
        return settings.EnableGroups;
    }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || !GetGame().IsServer() || s_Instance) { return; }
        m_Rows = new array<ref HCTeamPingRow>;
        s_Instance = this;
        HCGroupService groups = HCGroupService.Get();
        if (groups) { groups.HCPingPreference(true); }
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
    int HCReceive(HCGroupPeer peer, int status)
    {
        if (s_Instance != this || !GetGame().IsServer()) { return HCGroupCode.DISABLED; }
        HCGroupService service = HCGroupService.Get();
        if (!service) { return HCGroupCode.DISABLED; }
        HCGroupRecord group = service.HCPingGroup(peer);
        if (!group) { return HCGroupCode.DENIED; }
        string label = HCStatus(status);
        if (label == "") { return HCGroupCode.INVALID; }
        int now = HCGroupClock.Utc();
        if (now < 1) { return HCGroupCode.DENIED; }
        HCTeamPingRow previous;
        for (int index = m_Rows.Count() - 1; index >= 0; index--)
        {
            HCTeamPingRow cached = m_Rows.Get(index);
            if (now < cached.At) { return HCGroupCode.RATE; }
            if (now - cached.At >= 60) { m_Rows.RemoveOrdered(index); continue; }
            if (cached.Account == peer.Id) { previous = cached; }
        }
        if (previous && now - previous.At < 10) { return HCGroupCode.RATE; }
        vector actual = peer.Player.GetPosition();
        if (!HCGroupRules.PositionValid(actual)) { return HCGroupCode.INVALID; }
        if (!previous)
        {
            if (m_Rows.Count() >= 90) { return HCGroupCode.LIMIT; }
            previous = new HCTeamPingRow;
            previous.Account = peer.Id;
            m_Rows.Insert(previous);
        }
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
        previous.Pin.Radius = 5;
        previous.Pin.HCPinExpiresUtc = now + 60;
        service.HCPingDeliver(group, peer, label);
        Print("[HollowCountry] W5 team-ping group=" + group.Id.ToString() + " status=" + label + " ttl=60 rate=10");
        return HCGroupCode.OK;
    }
    void HCCollect(HCGroupRecord group, int cap, array<ref HCGroupPlace> output)
    {
        if (s_Instance != this || !group || !output) { return; }
        int now = HCGroupClock.Utc();
        if (now < 1) { return; }
        foreach (HCTeamPingRow row : m_Rows)
        {
            if (output.Count() >= cap) { break; }
            if (row.GroupId != group.Id || row.Epoch != group.Epoch) { continue; }
            if (group.Members.Find(row.Account) < 0 || now < row.At || now - row.At >= 60) { continue; }
            output.Insert(row.Pin);
        }
    }
    override void OnStop()
    {
        if (s_Instance == this) { s_Instance = null; }
        HCGroupService groups = HCGroupService.Get();
        if (groups) { groups.HCPingPreference(false); }
        m_Rows = null;
    }
}
modded class HCGroupService
{
    void HCPingPreference(bool enabled)
    {
        if (m_Config) { m_Config.HCTeamPingEnabled = enabled; }
    }
    HCGroupRecord HCPingGroup(HCGroupPeer peer)
    {
        if (!m_Healthy || !Live(peer) || !m_State) { return null; }
        if (!peer.Player.IsAlive() || peer.Player.IsUnconscious()) { return null; }
        return HCGroupRules.FindGroup(m_State, peer.Id);
    }
    void HCPingDeliver(HCGroupRecord group, HCGroupPeer source, string label)
    {
        if (!m_Healthy || !group || !Live(source)) { return; }
        foreach (HCGroupPeer recipient : m_Peers)
        {
            if (!Live(recipient) || group.Members.Find(recipient.Id) < 0) { continue; }
            NotificationSystem.SendNotificationToPlayerExtended(recipient.Player, 5, "Teammate status", source.Name + ": " + label);
            // Only the current group gets the fresh pin, no global broadcast.
            SendSnapshot(recipient, HCGroupSnapshotKind.FULL, 0);
        }
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
