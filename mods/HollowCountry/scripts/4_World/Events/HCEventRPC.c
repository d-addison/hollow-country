class HCEventPeer
{
    PlayerIdentity Identity;
    PlayerBase Player;
    string Session;
    int LastRequest = 0;
    int LastOp = 0;
    int LastEventId = 0;
    int LastCode = 0;
    int Sequence = 0;
    float RateWindow = 0;
    int RateCount = 0;
    float NextMutation = 0;
}
// Main attaches this adapter to the frozen module lifecycle. Context is always
// derived from that module; client fields never supply identity or authority.
class HCEventRPC
{
    protected HCEventModule m_Module;
    protected ref array<ref HCEventPeer> m_Peers = new array<ref HCEventPeer>();
    protected bool m_Started = false;
    protected string m_Boot;
    protected int m_Serial = 0;
    protected float m_GlobalWindow = 0;
    protected int m_GlobalCount = 0;
    protected float m_LastTime = 0;
    protected ref HCEventRuntimeState m_ProjectionState;

    bool Start(HCEventModule module)
    {
        if (m_Started || !GetGame().IsServer() || !module || !module.Runtime())
        {
            return false;
        }
        m_Module = module;
        int first = Math.RandomIntInclusive(1, 1000000000);
        int second = Math.RandomIntInclusive(1, 1000000000);
        m_Boot = first.ToString() + "-" + second.ToString();
        m_LastTime = GetGame().GetTickTime();
        if (m_LastTime != m_LastTime || m_LastTime < 0 || m_LastTime > 1000000000)
        {
            return false;
        }
        m_GlobalWindow = m_LastTime;
        m_GlobalCount = 0;
        m_ProjectionState = null;
        m_Started = true;
        DayZGame.Event_OnRPC.Insert(OnRPC);
        return true;
    }
    bool Live(HCEventPeer peer)
    {
        if (!peer || !peer.Identity || !peer.Player)
        {
            return false;
        }
        if (peer.Player.GetIdentity() != peer.Identity || peer.Identity.GetPlayer() != peer.Player)
        {
            return false;
        }
        return peer.Player.IsAlive() && !peer.Player.IsPendingDeletion() && !peer.Player.IsPlayerDisconnected();
    }
    HCEventPeer Authenticate(PlayerIdentity sender)
    {
        if (!sender || !HCEventDirector.TextValid(sender.GetId(), 96))
        {
            return null;
        }
        PlayerBase player = PlayerBase.Cast(sender.GetPlayer());
        if (!player || player.GetIdentity() != sender || !player.IsAlive() || player.IsPendingDeletion() || player.IsPlayerDisconnected())
        {
            return null;
        }
        Tick();
        int index = m_Peers.Count() - 1;
        while (index >= 0)
        {
            HCEventPeer existing = m_Peers[index];
            if (existing.Identity.GetId() == sender.GetId())
            {
                if (existing.Identity == sender && existing.Player == player)
                {
                    return existing;
                }
                m_Module.Runtime().Disconnect(existing.Player, m_Module.Context());
                m_Peers.Remove(index);
            }
            index = index - 1;
        }
        if (m_Peers.Count() >= 90 || m_Serial >= 1000000000)
        {
            return null;
        }
        HCEventPeer peer = new HCEventPeer;
        peer.Identity = sender;
        peer.Player = player;
        m_Serial = m_Serial + 1;
        peer.Session = m_Boot + ":" + m_Serial.ToString();
        // Authentication can run before Admit rejects an invalid clock sample.
        // Only a previously validated sample may initialize a peer baseline.
        peer.RateWindow = m_LastTime;
        m_Peers.Insert(peer);
        return peer;
    }
    bool Admit(HCEventPeer peer)
    {
        float now = GetGame().GetTickTime();
        if (now != now || now < 0 || now > 1000000000)
        {
            return false;
        }
        if (now < m_LastTime)
        {
            // GetTickTime rollback resets budgets; it must not detach the sole
            // listener behind the module's back or bypass mutation cooldowns.
            m_GlobalWindow = now;
            m_GlobalCount = 0;
            foreach (HCEventPeer tracked : m_Peers)
            {
                tracked.RateWindow = now;
                tracked.RateCount = 0;
                if (tracked.NextMutation > 0)
                {
                    tracked.NextMutation = now + 3;
                }
            }
        }
        m_LastTime = now;
        if (now - m_GlobalWindow >= 1)
        {
            m_GlobalWindow = now;
            m_GlobalCount = 0;
        }
        if (now - peer.RateWindow >= 1)
        {
            peer.RateWindow = now;
            peer.RateCount = 0;
        }
        if (m_GlobalCount >= 128 || peer.RateCount >= 4)
        {
            return false;
        }
        m_GlobalCount = m_GlobalCount + 1;
        peer.RateCount = peer.RateCount + 1;
        return true;
    }
    bool RequestValid(HCEventWireRequest request)
    {
        if (!request || request.Version != HCEventWire.VERSION || request.Session.Length() > 128)
        {
            return false;
        }
        if (request.Op == HCEventWireOp.BROWSE)
        {
            return request.RequestId == 0 && request.EventId == 0 && request.Ticket > 0 && request.Ticket <= 1000000000;
        }
        if (request.Op != HCEventWireOp.JOIN && request.Op != HCEventWireOp.LEAVE)
        {
            return false;
        }
        return request.Ticket == 0 && request.RequestId > 0 && request.RequestId <= 1000000000 && request.EventId > 0 && request.EventId <= 32;
    }
    string Title(int family)
    {
        if (family == HCEventFamily.RECOVERY) { return "Supply recovery"; }
        if (family == HCEventFamily.DELIVERY) { return "Supply delivery"; }
        if (family == HCEventFamily.INVESTIGATION) { return "Site investigation"; }
        if (family == HCEventFamily.STATIC_SALVAGE) { return "Salvage collection"; }
        return "Optional AI encounter";
    }
    HCEventPublicView Project(HCEventPeer peer, int ticket, int code)
    {
        HCEventPublicView view = new HCEventPublicView;
        view.Session = peer.Session;
        view.Ticket = ticket;
        view.Code = code;
        view.LastRequest = peer.LastRequest;
        view.ReceiptId = peer.LastRequest;
        view.ReceiptOp = peer.LastOp;
        view.ReceiptEventId = peer.LastEventId;
        view.ReceiptCode = peer.LastCode;
        HCEventRuntime runtime = m_Module.Runtime();
        HCEventContext context = m_Module.Context();
        view.Enabled = runtime && runtime.Allowed(context);
        if (!view.Enabled)
        {
            view.Code = HCEventWireCode.DISABLED;
            return view;
        }
        // Snapshot clones via JSON. Cache that immutable private projection
        // source once per revision, while rebuilding peer/time fields below.
        if (!m_ProjectionState || m_ProjectionState.Revision != runtime.Revision())
        {
            m_ProjectionState = runtime.Snapshot();
            if (!HCEventRuntimePolicy.StateValid(m_ProjectionState))
            {
                m_ProjectionState = null;
            }
        }
        HCEventRuntimeState state = m_ProjectionState;
        if (!state)
        {
            view.Enabled = false;
            view.Code = HCEventWireCode.DISABLED;
            return view;
        }
        int slot = 0;
        foreach (HCEventRun run : state.Runs)
        {
            HCEventRecord record = HCEventDirector.FindRecord(state.Director, run.EventId);
            // Previous sessions stay private; terminal current-session rows
            // remain visible so a participant can see expiry/completion.
            if (record.Session == context.Session)
            {
                slot = slot + 1;
                HCEventPublicRow row = new HCEventPublicRow;
                row.EventId = slot;
                row.Revision = record.Revision;
                row.Family = run.Mission.Family;
                row.Title = Title(row.Family);
                row.Status = record.Status;
                row.Progress = record.Progress;
                row.Goal = record.Definition.Goal;
                row.Participants = record.Participants.Count();
                row.MaxParticipants = record.Definition.MaxParticipants;
                row.Joined = record.Participants.Find(peer.Identity.GetId()) >= 0;
                if (!HCEventDirector.Terminal(record.Status))
                {
                    row.RemainingSeconds = Math.Max(0, Math.Min(86400, record.Expires - context.Now));
                }
                view.Rows.Insert(row);
            }
        }
        return view;
    }
    void Send(HCEventPeer peer, int ticket, int code)
    {
        if (!Live(peer) || peer.Sequence >= 1000000000)
        {
            return;
        }
        HCEventPublicView view = Project(peer, ticket, code);
        peer.Sequence = peer.Sequence + 1;
        view.Sequence = peer.Sequence;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(view);
        rpc.Send(peer.Player, HCEventWire.RPC_VIEW, true, peer.Identity);
    }
    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Started || !GetGame().IsServer() || target || rpcType != HCEventWire.RPC_REQUEST || !ctx)
        {
            return;
        }
        HCEventPeer peer = Authenticate(sender);
        if (!peer || !Admit(peer))
        {
            return;
        }
        HCEventWireRequest request;
        if (!ctx.Read(request) || !request)
        {
            return;
        }
        if (!RequestValid(request))
        {
            return;
        }
        if (request.Op == HCEventWireOp.BROWSE)
        {
            Send(peer, request.Ticket, HCEventCode.OK);
            return;
        }
        if (request.Session != peer.Session)
        {
            Send(peer, 0, HCEventWireCode.SESSION);
            return;
        }
        if (request.RequestId == peer.LastRequest && request.Op == peer.LastOp && request.EventId == peer.LastEventId)
        {
            Send(peer, 0, peer.LastCode);
            return;
        }
        if (request.RequestId != peer.LastRequest + 1)
        {
            Send(peer, 0, HCEventWireCode.ORDER);
            return;
        }
        peer.LastRequest = request.RequestId;
        peer.LastOp = request.Op;
        peer.LastEventId = request.EventId;
        peer.LastCode = HCEventCode.DENIED;
        HCEventRuntime runtime = m_Module.Runtime();
        HCEventContext context = m_Module.Context();
        float now = GetGame().GetTickTime();
        if (now < peer.NextMutation)
        {
            peer.LastCode = HCEventCode.LIMIT;
        }
        else
        {
            // Stored on the already bounded (90) native peer list, discarded
            // on disconnect. Consumed refusals also have replayable receipts.
            peer.NextMutation = now + 3;
            if (runtime)
            {
                int id = runtime.PublicEventId(request.EventId);
                if (request.Op == HCEventWireOp.LEAVE)
                {
                    peer.LastCode = runtime.Leave(id, peer.Player, context);
                }
                else
                {
                    if (!peer.Player.IsUnconscious())
                    {
                        peer.LastCode = runtime.Join(id, peer.Player, context);
                    }
                }
            }
        }
        Send(peer, 0, peer.LastCode);
    }
    void Tick()
    {
        if (!m_Started)
        {
            return;
        }
        int index = m_Peers.Count() - 1;
        while (index >= 0)
        {
            HCEventPeer peer = m_Peers[index];
            if (!Live(peer))
            {
                if (m_Module.Runtime())
                {
                    m_Module.Runtime().Disconnect(peer.Player, m_Module.Context());
                }
                m_Peers.Remove(index);
            }
            index = index - 1;
        }
    }
    void Stop()
    {
        if (m_Started)
        {
            DayZGame.Event_OnRPC.Remove(OnRPC);
        }
        m_Started = false;
        m_Peers.Clear();
        m_ProjectionState = null;
    }
}
