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
// HC-38 refusal-only adapter. Main attaches its existing bounded native
// authentication/rate admission to module lifetime; no quest payload is read.
// Native scripts-1.30.164289: Game.c:914,1120 GetTickTime/IsServer;
// gameplay.c:368,375 identity GetId/GetPlayer, :117 ScriptRPC.Send;
// 1_Core/proto/Serializer.c:57 Write; 3_Game/Entities/Man.c:21 GetIdentity;
// Object.c:215,517 IsPendingDeletion/IsAlive; PlayerBase.c:2638 disconnect.
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
    protected string m_Refusal;

    // Last refusal reason (Start or Admit). Logged once per reason change, so a
    // client flood cannot grow the log; the reason carries no player identity.
    string Refusal() { return m_Refusal; }
    bool HCRefuse(string reason)
    {
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Events] opt-in transport refused reason=" + reason);
        }
        return false;
    }
    bool Start(HCEventModule module)
    {
        if (m_Started) { return HCRefuse("already_started"); }
        if (!GetGame().IsServer()) { return HCRefuse("not_server"); }
        if (!module) { return HCRefuse("module_missing"); }
        m_Module = module;
        int first = Math.RandomIntInclusive(1, 1000000000);
        int second = Math.RandomIntInclusive(1, 1000000000);
        m_Boot = first.ToString() + "-" + second.ToString();
        m_LastTime = GetGame().GetTickTime();
        if (m_LastTime != m_LastTime || m_LastTime < 0 || m_LastTime > 1000000000)
        {
            return HCRefuse("tick_clock_invalid");
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
                if (m_Module.Runtime()) { m_Module.Runtime().Disconnect(existing.Player, m_Module.Context()); }
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
            return HCRefuse("clock_invalid");
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
            return HCRefuse("rate_limited");
        }
        m_GlobalCount = m_GlobalCount + 1;
        peer.RateCount = peer.RateCount + 1;
        return true;
    }
    // HC-38: the old wire IDs remain reserved; no client quest/reward operation.
    bool RequestValid(HCEventWireRequest request)
    {
        return false;
    }
    string Title(int family)
    {
        return "";
    }
    HCEventPublicView Project(HCEventPeer peer, int ticket, int code)
    {
        HCEventPublicView view = new HCEventPublicView;
        view.Session = peer.Session;
        view.Code = HCEventWireCode.DISABLED;
        // Empty default Rows and Enabled=false also revoke cached task markers.
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
    // Native identity and existing bounded rate admission precede refusal.
    // Never deserialize a retired request or call Join/Leave/reward handlers.
    // Native scripts-1.30.164289: Game.c:1120 IsServer; ScriptRPC transport is
    // unchanged (Serializer.c:57 Write; gameplay.c:117 Send; Game.c:211 OnRPC).
    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Started || !GetGame().IsServer() || target || rpcType != HCEventWire.RPC_REQUEST || !ctx)
        {
            return;
        }
        HCEventPeer peer = Authenticate(sender);
        if (!peer || !Admit(peer)) { return; }
        Send(peer, 0, HCEventWireCode.DISABLED);
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
