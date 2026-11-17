// Client cache only. Membership, permissions and mutations remain server-owned.
class HCGroupClient
{
    protected static ref HCGroupClient s_Instance;
    protected ref HCGroupSnapshot m_View;
    protected ref HCGroupRequest m_Pending;
    protected string m_PendingPayload;
    protected PlayerBase m_LocalPlayer;
    protected string m_Session;
    protected int m_Sequence;
    protected int m_Revision;
    protected int m_GroupId;
    protected int m_Epoch;
    protected int m_RequestId;
    protected int m_SyncTicket;
    protected int m_LastSyncTicket;
    protected int m_ConfirmedMutationId;
    protected bool m_Quarantined;
    protected int m_MutationGeneration;
    protected int m_SyncGeneration;
    protected bool m_SyncIdle;
    protected int m_Retries;
    protected float m_NextSync;
    protected float m_LastSend;
    protected float m_PositionsReceived;
    protected bool m_Listening;
    protected string m_Notice = "Waiting for group service";

    static bool FrameOrder(int kind, int sequence, int lastSequence, int revision, int lastRevision, int groupId, int lastGroupId, int epoch, int lastEpoch)
    {
        if (sequence <= lastSequence || sequence > 1000000000)
        {
            return false;
        }
        if (kind == 2)
        {
            return groupId == 0 && revision == 0 && epoch == 0;
        }
        if (kind != 0 && kind != 1)
        {
            return false;
        }
        if (revision < 0 || epoch < 0 || epoch > revision)
        {
            return false;
        }
        if (kind == 1)
        {
            if (groupId < 1 || groupId != lastGroupId)
            {
                return false;
            }
            return revision == lastRevision && epoch == lastEpoch;
        }
        if (groupId == lastGroupId)
        {
            if (revision < lastRevision || epoch < lastEpoch)
            {
                return false;
            }
        }
        return true;
    }

    HCGroupSnapshot GetSnapshot()
    {
        return m_View;
    }

    string GetNotice()
    {
        return m_Notice;
    }

    bool IsBusy()
    {
        return m_Pending != null;
    }

    bool ReceiveSnapshot(HCGroupSnapshot frame)
    {
        if (!SnapshotValid(frame))
            return false;
        bool changed = frame.Session != m_Session;
        bool handshake = m_SyncTicket != 0 && frame.RequestId == m_SyncTicket && frame.Kind != HCGroupSnapshotKind.POSITIONS;
        if (m_Quarantined && !handshake)
            return false;
        // Only confirmed server consumption is monotonic. The issued client
        // counter may legitimately be ahead after an unconsumed rejection.
        if (!changed && frame.LastMutationId < m_ConfirmedMutationId)
            return false;
        bool ordered = false;
        if (changed)
        {
            if (!handshake)
            {
                ClearView();
                m_Quarantined = true;
                m_SyncTicket = 0;
                m_SyncGeneration = -1;
                m_SyncIdle = false;
                m_NextSync = 0;
                return false;
            }
            ordered = FrameOrder(frame.Kind, frame.Sequence, 0, frame.Revision, 0, frame.GroupId, 0, frame.Epoch, 0);
        }
        else
        {
            ordered = FrameOrder(frame.Kind, frame.Sequence, m_Sequence, frame.Revision, m_Revision, frame.GroupId, m_GroupId, frame.Epoch, m_Epoch);
        }
        if (!ordered)
            return false;
        if (changed)
        {
            ClearView();
            m_Session = frame.Session;
            m_Sequence = 0;
            m_Revision = 0;
            m_GroupId = 0;
            m_Epoch = 0;
            // A new session invalidates old receipts; never resubmit its command.
            m_RequestId = frame.LastMutationId;
            m_Pending = null;
            m_PendingPayload = "";
            m_Retries = 0;
        }
        if (frame.Kind == HCGroupSnapshotKind.POSITIONS)
        {
            if (!m_View)
            {
                m_NextSync = 0;
                return false;
            }
            // Positions never replace marker, invitation or candidate lists.
            m_View.Members = frame.Members;
            m_View.Sequence = frame.Sequence;
        }
        else
        {
            m_View = frame;
        }
        m_Sequence = frame.Sequence;
        m_Revision = frame.Revision;
        m_GroupId = frame.GroupId;
        m_Epoch = frame.Epoch;
        m_PositionsReceived = GetGame().GetTickTime();
        m_ConfirmedMutationId = frame.LastMutationId;
        if (handshake)
        {
            // The SYNC must have started idle and stayed free of new mutations.
            // A counter is not an acknowledgement of an uncertain payload.
            if (!changed && !m_Pending && m_SyncIdle && m_SyncGeneration == m_MutationGeneration)
                m_RequestId = frame.LastMutationId;
            m_SyncTicket = 0;
            m_Quarantined = false;
        }
        if (!frame.Enabled)
            ClearView();
        return true;
    }

    static HCGroupClient Get()
    {
        if (!GetGame() || GetGame().IsServer())
            return null;
        if (!s_Instance)
            s_Instance = new HCGroupClient;
        return s_Instance;
    }

    void Start()
    {
        if (m_Listening || GetGame().IsServer())
            return;
        DayZGame.Event_OnRPC.Insert(OnRPC);
        m_Listening = true;
    }

    void Stop()
    {
        if (m_Listening)
            DayZGame.Event_OnRPC.Remove(OnRPC);
        m_Listening = false;
        ResetSession();
        m_LocalPlayer = null;
        if (s_Instance == this)
            s_Instance = null;
    }

    void ClearView()
    {
        m_View = null;
        m_PositionsReceived = 0;
    }

    void ResetSession()
    {
        ClearView();
        m_Session = "";
        m_Sequence = 0;
        m_Revision = 0;
        m_GroupId = 0;
        m_Epoch = 0;
        m_RequestId = 0;
        m_SyncTicket = 0;
        m_Pending = null;
        // Never reuse a handshake ticket during this client's lifetime,
        // including across local resets and timing recovery.
        if (m_LastSyncTicket < 900000)
            m_LastSyncTicket = 900000;
        m_ConfirmedMutationId = 0;
        m_Quarantined = false;
        m_PendingPayload = "";
        m_MutationGeneration = 0;
        m_SyncGeneration = -1;
        m_SyncIdle = false;
        m_Retries = 0;
        m_NextSync = 0;
        m_LastSend = 0;
        m_Notice = "Waiting for group service";
    }

    // Recover transport timing without discarding an uncertain transaction.
    void Recover()
    {
        ClearView();
        m_Quarantined = true;
        m_SyncTicket = 0;
        m_SyncGeneration = -1;
        m_SyncIdle = false;
        m_NextSync = 0;
        m_LastSend = 0;
    }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || GetGame().IsServer() || sender || target)
            return;
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.IsAlive())
        {
            ClearView();
            return;
        }
        if (rpcType == HCGroupProtocol.RPC_SNAPSHOT)
        {
            HCGroupSnapshot frame;
            if (ctx.Read(frame) && frame)
                ReceiveSnapshot(frame);
        }
        else if (rpcType == HCGroupProtocol.RPC_REPLY)
        {
            HCGroupReply reply;
            if (ctx.Read(reply) && reply)
                ReceiveReply(reply);
        }
    }

    bool SnapshotValid(HCGroupSnapshot frame)
    {
        if (!frame || frame.Version != HCGroupProtocol.VERSION)
            return false;
        if (frame.LastMutationId < 0 || frame.LastMutationId > 1000000)
            return false;
        if (!HCGroupRules.TextValid(frame.Session, 80, false))
            return false;
        if (!frame.Settings || !HCGroupRules.SettingsValid(frame.Settings))
            return false;
        if (!frame.Members || !frame.Candidates || !frame.Markers || !frame.Invitations)
            return false;
        if (frame.Members.Count() > frame.Settings.MaxMembers)
            return false;
        if (frame.Candidates.Count() > 90 || frame.Markers.Count() > frame.Settings.MaxMarkers)
            return false;
        if (frame.Invitations.Count() > frame.Settings.MaxInvites)
            return false;
        if (frame.GroupId < 0 || frame.GroupId > 1000000000)
            return false;
        if (frame.Revision > 1000000000 || frame.Epoch > 1000000000)
            return false;
        if (frame.Kind == HCGroupSnapshotKind.CLEAR || frame.GroupId == 0)
        {
            if (frame.GroupId != 0 || frame.Revision != 0 || frame.Epoch != 0)
                return false;
            if (frame.Members.Count() != 0 || frame.Markers.Count() != 0)
                return false;
        }
        else
        {
            if (frame.Revision < 1 || frame.Epoch < 1 || frame.Members.Count() < 1)
                return false;
            if (!HCGroupRules.TextValid(frame.Name, 48, false))
                return false;
        }
        return ContentsValid(frame);
    }

    bool MemberValid(HCGroupMember member)
    {
        if (!member)
            return false;
        if (!HCGroupRules.TextValid(member.Id, 128, false))
            return false;
        if (!HCGroupRules.TextValid(member.Name, 64, false))
            return false;
        if (member.Alive && !member.Online)
            return false;
        if (member.HasPosition)
        {
            if (!member.Alive || !HCGroupRules.PositionValid(member.Position))
                return false;
            if (!HCGroupRules.TimestampValid(member.SampleUtc))
                return false;
        }
        return true;
    }

    bool ContentsValid(HCGroupSnapshot frame)
    {
        if (frame.RequestId < 0 || frame.RequestId > 1000000)
            return false;
        if (frame.Kind == HCGroupSnapshotKind.POSITIONS)
        {
            if (frame.Markers.Count() != 0 || frame.Candidates.Count() != 0)
                return false;
            if (frame.Invitations.Count() != 0)
                return false;
        }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.GetIdentity())
            return false;
        string localId = viewer.GetIdentity().GetId();
        array<string> memberIds = new array<string>();
        foreach (HCGroupMember member : frame.Members)
        {
            if (!MemberValid(member) || memberIds.Find(member.Id) >= 0)
                return false;
            memberIds.Insert(member.Id);
        }
        if (frame.GroupId > 0)
        {
            if (memberIds.Find(localId) < 0 || memberIds.Find(frame.OwnerId) < 0)
                return false;
        }
        array<string> candidateIds = new array<string>();
        foreach (HCGroupMember candidate : frame.Candidates)
        {
            if (!MemberValid(candidate) || candidate.HasPosition)
                return false;
            if (candidate.Id == localId || candidateIds.Find(candidate.Id) >= 0)
                return false;
            candidateIds.Insert(candidate.Id);
        }
        array<int> markerIds = new array<int>();
        foreach (HCGroupMarker marker : frame.Markers)
        {
            if (!marker || marker.Id < 1 || marker.Id > 1000000000)
                return false;
            if (markerIds.Find(marker.Id) >= 0)
                return false;
            markerIds.Insert(marker.Id);
            if (!HCGroupRules.TextValid(marker.CreatorId, 128, false))
                return false;
            if (!HCGroupRules.TextValid(marker.Name, 64, false))
                return false;
            if (!HCGroupRules.TextValid(marker.Note, 512, true))
                return false;
            if (!HCGroupRules.PositionValid(marker.Position))
                return false;
            if (marker.Icon < 0 || marker.Icon > 19)
                return false;
            if (marker.ExpiresUtc < 0 || marker.ExpiresUtc > 2147483647)
                return false;
        }
        array<int> inviteIds = new array<int>();
        foreach (HCGroupInvitation invitation : frame.Invitations)
        {
            if (!invitation || invitation.Id < 1 || invitation.GroupId < 1)
                return false;
            if (inviteIds.Find(invitation.Id) >= 0)
                return false;
            inviteIds.Insert(invitation.Id);
            if (invitation.InviteeId != localId)
                return false;
            if (!HCGroupRules.TextValid(invitation.InviterId, 128, false))
                return false;
            if (!HCGroupRules.TextValid(invitation.GroupName, 48, false))
                return false;
            if (!HCGroupRules.TimestampValid(invitation.ExpiresUtc))
                return false;
        }
        return true;
    }

    void Transmit(HCGroupRequest request)
    {
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(request);
        rpc.Send(null, HCGroupProtocol.RPC_REQUEST, true);
        m_LastSend = GetGame().GetTickTime();
    }

    bool Send(HCGroupRequest request)
    {
        if (!request || !m_View || !m_View.Enabled || m_Pending)
            return false;
        if (m_Session == "" || m_RequestId >= 1000000)
            return false;
        if (request.Op < 1 || request.Op > 12)
            return false;
        if (!HCGroupRules.TextValid(request.Name, 64, true))
            return false;
        if (!HCGroupRules.TextValid(request.Note, 512, true))
            return false;
        if (!HCGroupRules.TextValid(request.TargetId, 128, true))
            return false;
        request.Version = HCGroupProtocol.VERSION;
        request.Session = m_Session;
        request.RequestId = m_RequestId + 1;
        request.ExpectedRevision = m_Revision;
        string error;
        if (!JsonFileLoader<HCGroupRequest>.MakeData(request, m_PendingPayload, error))
            return false;
        if (m_PendingPayload.Length() > 4096)
        {
            m_PendingPayload = "";
            return false;
        }
        // Private clone and serialized receipt remain immutable until resolved.
        // Caller edits cannot change a retry's ID, session or payload.
        if (!JsonFileLoader<HCGroupRequest>.LoadData(m_PendingPayload, m_Pending, error) || !m_Pending)
        {
            m_Pending = null;
            m_PendingPayload = "";
            return false;
        }
        m_RequestId = m_Pending.RequestId;
        m_MutationGeneration++;
        m_Retries = 0;
        m_Notice = "Waiting for server";
        Transmit(m_Pending);
        return true;
    }

    void ReceiveReply(HCGroupReply reply)
    {
        if (!reply || reply.Version != HCGroupProtocol.VERSION || reply.Session != m_Session || !m_Pending)
            return;
        if (reply.RequestId != m_Pending.RequestId)
            return;
        if (reply.Code < 0 || reply.Code > 9)
            return;
        if (reply.LastMutationId < 0 || reply.LastMutationId > 1000000)
            return;
        if (reply.LastMutationId < m_ConfirmedMutationId)
            return;
        m_ConfirmedMutationId = reply.LastMutationId;
        // A correlated result resolves this request, including pre-consumption
        // denial. Unlike a snapshot floor, it identifies our pending command.
        m_RequestId = reply.LastMutationId;
        m_Pending = null;
        m_PendingPayload = "";
        m_Notice = "Server result: " + reply.Code.ToString();
        if (reply.Code == HCGroupCode.SESSION)
            ClearView();
        m_NextSync = 0;
    }

    void Sync(float now)
    {
        if (now - m_LastSend < 1.0)
            return;
        if (m_SyncTicket == 0)
        {
            // Bounded, non-repeating correlation within the existing ticket
            // range. Exhaustion requires a new client instance/connection.
            if (m_LastSyncTicket >= 1000000)
            {
                ClearView();
                m_Quarantined = true;
                m_Notice = "Sync ticket budget exhausted; reconnect required";
                m_NextSync = now + 10.0;
                return;
            }
            m_LastSyncTicket++;
            m_SyncTicket = m_LastSyncTicket;
            m_SyncGeneration = m_MutationGeneration;
            m_SyncIdle = !m_Pending;
        }
        HCGroupRequest request = new HCGroupRequest;
        request.Op = HCGroupOp.SYNC;
        request.RequestId = m_SyncTicket;
        request.Session = m_Session;
        Transmit(request);
        m_NextSync = now + 10.0;
    }

    void Retry(float now)
    {
        if (!m_Pending || now - m_LastSend < 3.0)
            return;
        if (m_Retries >= 3)
        {
            m_Notice = "No reply; mutations paused until reply or reconnect";
            return;
        }
        m_Retries++;
        Transmit(m_Pending);
    }

    void Update()
    {
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (player != m_LocalPlayer)
        {
            ResetSession();
            m_LocalPlayer = player;
        }
        if (!player || !player.GetIdentity() || !player.IsAlive())
        {
            ClearView();
            return;
        }
        float now = GetGame().GetTickTime();
        if (!(now >= 0.0) || now < m_LastSend)
        {
            Recover();
            return;
        }
        Retry(now);
        if (now >= m_NextSync)
            Sync(now);
        if (!m_View)
            return;
        int utc = HCGroupClock.Utc();
        foreach (HCGroupMember member : m_View.Members)
        {
            bool stale = now - m_PositionsReceived > m_View.Settings.PositionStaleSeconds;
            if (utc < member.SampleUtc || utc < 1)
                stale = true;
            if (utc - member.SampleUtc > m_View.Settings.PositionStaleSeconds)
                stale = true;
            if (stale || !member.HasPosition || !member.Alive || !member.Online)
            {
                member.HasPosition = false;
                member.Position = vector.Zero;
            }
        }
    }
}
