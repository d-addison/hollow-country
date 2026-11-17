class HCGroupClock
{
    static int Utc()
    {
        int year, month, day, hour, minute, second;
        GetYearMonthDayUTC(year, month, day);
        GetHourMinuteSecondUTC(hour, minute, second);
        if (year < 2026 || year > 2032 || month < 1 || month > 12 || day < 1 || day > 31) return -1;
        int days;
        for (int y = 1970; y < year; y++)
        {
            days += 365;
            if (y % 4 == 0) days++;
        }
        for (int m = 1; m < month; m++)
        {
            int length = 31;
            if (m == 4 || m == 6 || m == 9 || m == 11) length = 30;
            if (m == 2)
            {
                length = 28;
                if (year % 4 == 0) length = 29;
            }
            days += length;
        }
        return (days + day - 1) * 86400 + hour * 3600 + minute * 60 + second;
    }
}

class HCGroupPeer
{
    string Id;
    string Name;
    string Session;
    PlayerIdentity Identity;
    PlayerBase Player;
    int LastRequest;
    string LastPayload;
    ref HCGroupReply LastReply;
    int Sequence;
    int LastGroup;
    float RateWindow;
    int RateCount;
}

// All authenticated identity comes from the engine sender. Client fields select
// targets only; neither group identity, ownership nor position comes from them.
class HCGroupService
{
    protected static ref HCGroupService s_Instance;
    protected ref HCGroupSettings m_Config;
    protected ref HCGroupState m_State;
    protected ref HCGroupStore m_Store;
    protected ref array<ref HCGroupPeer> m_Peers = new array<ref HCGroupPeer>();
    protected ref map<string, string> m_Names = new map<string, string>();
    protected bool m_Healthy;
    protected string m_Boot;
    protected int m_Serial;
    protected int m_LastUtc;
    protected float m_PositionTime;
    protected float m_GlobalWindow;
    protected int m_GlobalCount;

    static HCGroupService Get() { return s_Instance; }

    bool Start(HCGroupSettings config)
    {
        if (!GetGame().IsServer() || !HCGroupRules.SettingsValid(config) || !config.Enabled || s_Instance) return false;
        m_Config = config;
        m_LastUtc = HCGroupClock.Utc();
        float worldSize = GetGame().GetWorld().GetWorldSize();
        if (m_LastUtc < 1 || worldSize < 1 || worldSize > 50000) return false;
        m_Store = new HCGroupStore;
        if (!m_Store.Open(config, m_State)) return false;
        foreach (HCGroupRecord group : m_State.Groups)
        {
            foreach (HCGroupMarker marker : group.Markers)
            {
                if (marker.Position[0] > worldSize || marker.Position[2] > worldSize) return false;
            }
        }
        // Fresh anti-stale receipt, not a credential: authority is sender.GetId.
        m_Boot = m_LastUtc.ToString() + "-" + Math.RandomIntInclusive(1, 1000000000).ToString();
        m_Healthy = true;
        s_Instance = this;
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        if (players.Count() > 90) { Stop(); return false; }
        foreach (Man man : players)
        {
            PlayerBase player = PlayerBase.Cast(man);
            if (player && player.GetIdentity()) Connected(player.GetIdentity(), player);
        }
        return true;
    }

    HCGroupPeer Peer(string uid)
    {
        foreach (HCGroupPeer peer : m_Peers)
        {
            if (peer.Id == uid) return peer;
        }
        return null;
    }

    bool Live(HCGroupPeer peer)
    {
        return peer && peer.Identity && peer.Player && peer.Player.GetIdentity() == peer.Identity;
    }

    void Connected(PlayerIdentity identity, PlayerBase player)
    {
        if (!m_Healthy || !identity || !player || player.GetIdentity() != identity) return;
        string uid = identity.GetId();
        if (!HCGroupRules.TextValid(uid, 128, false)) return;
        HCGroupPeer previous = Peer(uid);
        if (previous) m_Peers.Remove(m_Peers.Find(previous));
        if (m_Peers.Count() >= 90 || m_Serial >= 1000000000) return;
        HCGroupPeer peer = new HCGroupPeer;
        peer.Id = uid;
        peer.Identity = identity;
        peer.Player = player;
        peer.Name = identity.GetName();
        if (!HCGroupRules.TextValid(peer.Name, 64, false)) peer.Name = "Survivor";
        m_Serial++;
        peer.Session = m_Boot + "-" + m_Serial.ToString();
        if (m_Names.Count() >= 180) m_Names.Clear();
        m_Names.Set(uid, peer.Name);
        m_Peers.Insert(peer);
        SendSnapshot(peer, HCGroupSnapshotKind.FULL, 0);
        Broadcast();
    }

    // Called at the disconnect event BEFORE native delayed body logout. The
    // body may remain in-world; it is no longer a live position source/recipient.
    void Disconnected(PlayerIdentity identity)
    {
        if (!identity) return;
        HCGroupPeer peer = Peer(identity.GetId());
        if (!peer || peer.Identity != identity) return;
        m_Peers.Remove(m_Peers.Find(peer));
        HCGroupRules.DropInvites(m_State, 0, peer.Id);
        peer.Identity = null;
        peer.Player = null;
        Broadcast();
    }

    void Stop()
    {
        m_Healthy = false;
        foreach (HCGroupPeer peer : m_Peers) SendSnapshot(peer, HCGroupSnapshotKind.CLEAR, 0);
        m_Peers.Clear();
        if (s_Instance == this) s_Instance = null;
    }

    void Reply(HCGroupPeer peer, int requestId, int code, bool cache = false)
    {
        if (!Live(peer)) return;
        HCGroupReply reply = new HCGroupReply;
        reply.RequestId = requestId;
        reply.Code = code;
        reply.Session = peer.Session;
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (group) reply.Revision = group.Revision;
        // Only the result of a newly consumed request may replace its receipt.
        // A mismatched replay/session/invalid packet cannot poison the cache.
        if (cache) peer.LastReply = reply;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(reply);
        rpc.Send(null, HCGroupProtocol.RPC_REPLY, true, peer.Identity);
    }

    bool Admit(HCGroupPeer peer)
    {
        float now = GetGame().GetTickTime();
        if (!(now >= 0.0)) return false;
        if (now - peer.RateWindow >= 1.0) { peer.RateWindow = now; peer.RateCount = 0; }
        if (now - m_GlobalWindow >= 1.0) { m_GlobalWindow = now; m_GlobalCount = 0; }
        if (peer.RateCount >= m_Config.MaxRequestsPerSecond || m_GlobalCount >= m_Config.MaxRequestsPerSecond * 2) return false;
        peer.RateCount++;
        m_GlobalCount++;
        return true;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Healthy || !GetGame().IsServer() || rpcType != HCGroupProtocol.RPC_REQUEST || target || !sender) return;
        string uid = sender.GetId();
        HCGroupPeer peer = Peer(uid);
        if (!peer)
        {
            Connected(sender, PlayerBase.Cast(sender.GetPlayer()));
            peer = Peer(uid);
        }
        if (!Live(peer) || peer.Identity != sender) return;
        if (!Admit(peer)) { Reply(peer, 0, HCGroupCode.RATE); return; }
        HCGroupRequest request;
        if (!ctx.Read(request) || !request) { Reply(peer, 0, HCGroupCode.INVALID); return; }
        if (request.Version != 1 || request.Session.Length() > 80 || request.Name.Length() > 64 || request.Note.Length() > 512 || request.TargetId.Length() > 128 || request.RequestId < 0 || request.RequestId > 1000000)
        { Reply(peer, request.RequestId, HCGroupCode.INVALID); return; }
        if (request.Op == HCGroupOp.SYNC)
        {
            SendSnapshot(peer, HCGroupSnapshotKind.FULL, request.RequestId);
            return;
        }
        if (request.Session != peer.Session || request.RequestId < 1)
        { Reply(peer, request.RequestId, HCGroupCode.SESSION); return; }
        string payload;
        string error;
        if (!JsonFileLoader<HCGroupRequest>.MakeData(request, payload, error) || payload.Length() > 4096)
        { Reply(peer, request.RequestId, HCGroupCode.INVALID); return; }
        if (request.RequestId == peer.LastRequest)
        {
            if (payload != peer.LastPayload || !peer.LastReply)
            { Reply(peer, request.RequestId, HCGroupCode.CONFLICT); return; }
            ScriptRPC repeat = new ScriptRPC;
            repeat.Write(peer.LastReply);
            repeat.Send(null, HCGroupProtocol.RPC_REPLY, true, peer.Identity);
            return;
        }
        if (request.RequestId != peer.LastRequest + 1)
        { Reply(peer, request.RequestId, HCGroupCode.CONFLICT); return; }
        peer.LastRequest = request.RequestId;
        peer.LastPayload = payload;
        peer.LastReply = null;
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc) { Stop(); return; }
        if (request.Op == HCGroupOp.INVITE && !Live(Peer(request.TargetId)))
        { Reply(peer, request.RequestId, HCGroupCode.NOT_FOUND, true); return; }
        if ((request.Op == HCGroupOp.MARKER_CREATE || request.Op == HCGroupOp.MARKER_UPDATE) && (request.Position[0] > GetGame().GetWorld().GetWorldSize() || request.Position[2] > GetGame().GetWorld().GetWorldSize()))
        { Reply(peer, request.RequestId, HCGroupCode.INVALID, true); return; }
        HCGroupState candidate;
        if (!Clone(candidate)) { Reply(peer, request.RequestId, HCGroupCode.STORAGE, true); Stop(); return; }
        int result = HCGroupRules.Apply(candidate, m_Config, request, uid, now);
        if (result == HCGroupCode.OK) result = Commit(candidate);
        if (result == HCGroupCode.STORAGE)
        { Reply(peer, request.RequestId, HCGroupCode.STORAGE, true); Stop(); return; }
        Reply(peer, request.RequestId, result, true);
        if (result == HCGroupCode.OK) Broadcast();
        if (result == HCGroupCode.CONFLICT) SendSnapshot(peer, HCGroupSnapshotKind.FULL, request.RequestId);
    }

    bool Clone(out HCGroupState candidate)
    {
        string text;
        string error;
        return JsonFileLoader<HCGroupState>.MakeData(m_State, text, error) && text.Length() <= m_Config.MaxStoreBytes && JsonFileLoader<HCGroupState>.LoadData(text, candidate, error) && candidate;
    }

    int Commit(HCGroupState candidate)
    {
        candidate.Revision = m_State.Revision + 1;
        if (!HCGroupRules.StateValid(candidate, m_Config, GetGame().GetWorldName())) return HCGroupCode.STORAGE;
        // Quota is admission control, not a damaged store. This check happens
        // before Save can create an intent; rejected clones never replace live
        // state. Include ephemeral invitations so Clone stays within its bound.
        string text;
        string error;
        bool serialized = JsonFileLoader<HCGroupState>.MakeData(candidate, text, error);
        if (!serialized) return HCGroupCode.STORAGE;
        if (text.Length() > m_Config.MaxStoreBytes) return HCGroupCode.LIMIT;
        if (!m_Store.Save(candidate)) return HCGroupCode.STORAGE;
        m_State = candidate;
        return HCGroupCode.OK;
    }

    bool HasGPS(HCGroupPeer peer)
    {
        if (!m_Config.RequireGPS) return true;
        if (!Live(peer) || !peer.Player.GetMapNavigationBehaviour()) return false;
        int navigation = peer.Player.GetMapNavigationBehaviour().GetNavigationType();
        return (navigation & EMapNavigationType.GPS) != 0 || (navigation & EMapNavigationType.ALL) != 0;
    }

    HCGroupMember Member(string uid, HCGroupPeer recipient, bool position)
    {
        HCGroupMember member = new HCGroupMember;
        member.Id = uid;
        member.Name = m_Names.Get(uid);
        if (member.Name == "") member.Name = "Offline member";
        HCGroupPeer source = Peer(uid);
        member.Online = Live(source);
        // Candidates disclose invitation selection/availability only. The
        // default Alive=false means undisclosed here, not a death report.
        if (!position) return member;
        member.Alive = member.Online && source.Player.IsAlive();
        if (position && member.Alive && Live(recipient) && recipient.Player.IsAlive() && HasGPS(source) && HasGPS(recipient) && (m_Config.MapIcons || m_Config.WorldIcons))
        {
            vector actual = source.Player.GetPosition();
            vector viewer = recipient.Player.GetPosition();
            float dx = actual[0] - viewer[0];
            float dy = actual[1] - viewer[1];
            float dz = actual[2] - viewer[2];
            if (HCGroupRules.PositionValid(actual) && (m_Config.MapIcons || dx * dx + dy * dy + dz * dz <= m_Config.MaxIconDistance * m_Config.MaxIconDistance))
            {
                member.Position = actual;
                member.HasPosition = true;
                member.SampleUtc = m_LastUtc;
            }
        }
        return member;
    }

    void SendSnapshot(HCGroupPeer peer, int kind, int requestId)
    {
        if (!Live(peer) || peer.Sequence >= 1000000000) return;
        HCGroupSnapshot snapshot = new HCGroupSnapshot;
        snapshot.Settings = m_Config;
        snapshot.Enabled = m_Healthy;
        snapshot.Kind = kind;
        snapshot.RequestId = requestId;
        snapshot.Session = peer.Session;
        peer.Sequence++;
        snapshot.Sequence = peer.Sequence;
        HCGroupRecord group;
        if (m_Healthy) group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group && peer.LastGroup != 0) snapshot.Kind = HCGroupSnapshotKind.CLEAR;
        if (group && kind != HCGroupSnapshotKind.CLEAR)
        {
            snapshot.GroupId = group.Id;
            snapshot.Revision = group.Revision;
            snapshot.Epoch = group.Epoch;
            snapshot.Name = group.Name;
            snapshot.OwnerId = group.OwnerId;
            foreach (string uid : group.Members) snapshot.Members.Insert(Member(uid, peer, true));
            if (kind == HCGroupSnapshotKind.FULL)
            {
                foreach (HCGroupMarker marker : group.Markers)
                {
                    if (marker.ExpiresUtc == 0 || marker.ExpiresUtc > m_LastUtc) snapshot.Markers.Insert(marker);
                }
            }
        }
        if (m_Healthy && kind != HCGroupSnapshotKind.POSITIONS)
        {
            foreach (HCGroupPeer candidate : m_Peers)
            {
                if (Live(candidate) && candidate.Id != peer.Id) snapshot.Candidates.Insert(Member(candidate.Id, peer, false));
            }
            foreach (HCGroupInvitation invitation : m_State.Invitations)
            {
                if (invitation.InviteeId == peer.Id && invitation.ExpiresUtc > m_LastUtc) snapshot.Invitations.Insert(invitation);
            }
        }
        peer.LastGroup = snapshot.GroupId;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(snapshot);
        rpc.Send(null, HCGroupProtocol.RPC_SNAPSHOT, true, peer.Identity);
    }

    void Broadcast()
    {
        if (!m_Healthy) return;
        foreach (HCGroupPeer peer : m_Peers) SendSnapshot(peer, HCGroupSnapshotKind.FULL, 0);
    }

    void Tick(float deltaTime)
    {
        if (!m_Healthy) return;
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc || now > 1990000000 || !(deltaTime > 0.0) || deltaTime > 300.0) { Stop(); return; }
        m_LastUtc = now;
        // Invitations are ephemeral; removing them needs no disk transaction.
        for (int i = m_State.Invitations.Count() - 1; i >= 0; i--)
        {
            if (m_State.Invitations.Get(i).ExpiresUtc <= now) m_State.Invitations.Remove(i);
        }
        HCGroupState expired;
        bool changed;
        foreach (HCGroupRecord group : m_State.Groups)
        {
            foreach (HCGroupMarker marker : group.Markers)
            {
                if (marker.ExpiresUtc > 0 && marker.ExpiresUtc <= now) changed = true;
            }
        }
        if (changed)
        {
            if (!Clone(expired)) { Stop(); return; }
            foreach (HCGroupRecord record : expired.Groups)
            {
                bool touched;
                for (int n = record.Markers.Count() - 1; n >= 0; n--)
                {
                    HCGroupMarker old = record.Markers.Get(n);
                    if (old.ExpiresUtc > 0 && old.ExpiresUtc <= now) { record.Markers.Remove(n); touched = true; }
                }
                if (touched) HCGroupRules.Touch(record, false);
            }
            int expiryResult = Commit(expired);
            if (expiryResult == HCGroupCode.STORAGE) { Stop(); return; }
            if (expiryResult == HCGroupCode.OK) Broadcast();
        }
        m_PositionTime += deltaTime;
        if (m_PositionTime >= m_Config.PositionIntervalSeconds)
        {
            m_PositionTime = 0;
            foreach (HCGroupPeer peer : m_Peers)
            {
                if (HCGroupRules.FindGroup(m_State, peer.Id)) SendSnapshot(peer, HCGroupSnapshotKind.POSITIONS, 0);
            }
        }
    }
}
