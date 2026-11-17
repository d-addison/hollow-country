class HCEventWireCodec
{
    static HCEventPublicView CloneView(HCEventPublicView value)
    {
        string text;
        string error;
        HCEventPublicView clone;
        if (!JsonFileLoader<HCEventPublicView>.MakeData(value, text, error, false)) return null;
        if (!JsonFileLoader<HCEventPublicView>.LoadData(text, clone, error)) return null;
        return clone;
    }
    static HCEventWireRequest CloneRequest(HCEventWireRequest value)
    {
        string text;
        string error;
        HCEventWireRequest clone;
        if (!JsonFileLoader<HCEventWireRequest>.MakeData(value, text, error, false)) return null;
        if (!JsonFileLoader<HCEventWireRequest>.LoadData(text, clone, error)) return null;
        return clone;
    }
}
// Cache and original-intent retries only. Server runtime owns participation.
class HCEventClient
{
    protected static ref HCEventClient s_Instance;
    protected ref HCEventPublicView m_View;
    protected ref HCEventWireRequest m_Pending;
    protected PlayerBase m_LocalPlayer;
    protected string m_Session;
    protected int m_Sequence = 0;
    protected int m_Floor = 0;
    // Never reset on death, session change or mission finish.
    protected int m_TicketCounter = 0;
    protected int m_BrowseTicket = 0;
    protected float m_ReceivedAt = 0;
    protected float m_LastSend = 0;
    protected float m_NextBrowse = 0;
    protected float m_LastClock = 0;
    protected int m_Retries = 0;
    protected bool m_Listening = false;
    protected bool m_Browsing = false;
    protected string m_Notice = "Waiting for event service";

    static HCEventClient Get()
    {
        if (!s_Instance) { s_Instance = new HCEventClient; }
        return s_Instance;
    }
    void Start()
    {
        if (m_Listening || GetGame().IsServer()) { return; }
        m_Listening = true;
        m_LastClock = GetGame().GetTickTime();
        DayZGame.Event_OnRPC.Insert(OnRPC);
    }
    void Reset()
    {
        m_View = null;
        m_Pending = null;
        m_Session = "";
        m_Sequence = 0;
        m_Floor = 0;
        m_BrowseTicket = 0;
        m_Retries = 0;
        m_NextBrowse = 0;
        m_Notice = "Waiting for event service";
    }
    void Stop()
    {
        if (m_Listening) { DayZGame.Event_OnRPC.Remove(OnRPC); }
        m_Listening = false;
        m_Browsing = false;
        Reset();
        m_LocalPlayer = null;
    }
    void SetBrowsing(bool browsing)
    {
        m_Browsing = browsing;
        if (!browsing && !m_Pending) { m_BrowseTicket = 0; }
        if (browsing && m_BrowseTicket == 0 && !m_Pending) { Browse(); }
    }
    bool Fresh()
    {
        float now = GetGame().GetTickTime();
        return m_View && now >= m_ReceivedAt && now - m_ReceivedAt <= 15;
    }
    bool IsBusy()
    {
        return m_Pending != null || m_BrowseTicket != 0;
    }
    string GetNotice()
    {
        return m_Notice;
    }
    HCEventPublicView GetView()
    {
        if (!m_View) { return null; }
        return HCEventWireCodec.CloneView(m_View);
    }
    void Transmit(HCEventWireRequest request)
    {
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(request);
        rpc.Send(null, HCEventWire.RPC_REQUEST, true);
        m_LastSend = GetGame().GetTickTime();
    }
    bool Browse()
    {
        if (!m_Listening || m_BrowseTicket != 0 || m_TicketCounter >= 1000000000) { return false; }
        if (m_Pending && m_Retries < 2) { return false; }
        m_TicketCounter = m_TicketCounter + 1;
        m_BrowseTicket = m_TicketCounter;
        HCEventWireRequest request = new HCEventWireRequest;
        request.Session = m_Session;
        request.Ticket = m_BrowseTicket;
        Transmit(request);
        m_NextBrowse = GetGame().GetTickTime() + 5;
        return true;
    }
    HCEventPublicRow Row(int id)
    {
        if (!m_View) { return null; }
        foreach (HCEventPublicRow row : m_View.Rows)
        {
            if (row.EventId == id) { return row; }
        }
        return null;
    }
    bool CanSend(int op, int id)
    {
        if (!m_Listening || !Fresh() || !m_View.Enabled || IsBusy() || m_Floor >= 1000000000) { return false; }
        HCEventPublicRow row = Row(id);
        if (!row || row.RemainingSeconds <= 0 || row.Status < HCEventStatus.ANNOUNCED || row.Status > HCEventStatus.ACTIVE) { return false; }
        if (op == HCEventWireOp.JOIN) { return !row.Joined && row.Participants < row.MaxParticipants; }
        return op == HCEventWireOp.LEAVE && row.Joined;
    }
    bool Send(int op, int id)
    {
        if (!CanSend(op, id)) { return false; }
        HCEventWireRequest request = new HCEventWireRequest;
        request.Op = op;
        request.EventId = id;
        request.Session = m_Session;
        request.RequestId = m_Floor + 1;
        m_Pending = HCEventWireCodec.CloneRequest(request);
        if (!m_Pending) { return false; }
        m_Retries = 0;
        m_Notice = "Waiting for server confirmation";
        Transmit(request);
        return true;
    }
    bool ViewValid(HCEventPublicView view)
    {
        if (!view || view.Version != HCEventWire.VERSION || !HCEventDirector.TextValid(view.Session, 128)) { return false; }
        if (view.Sequence < 1 || view.Sequence > 1000000000 || view.Ticket < 0 || view.Ticket > 1000000000) { return false; }
        if (view.LastRequest < 0 || view.LastRequest > 1000000000 || view.ReceiptId != view.LastRequest) { return false; }
        if (view.Code < 0 || view.Code > 11 || view.ReceiptCode < 0 || view.ReceiptCode > 7) { return false; }
        if (view.LastRequest == 0)
        {
            if (view.ReceiptOp != 0 || view.ReceiptEventId != 0 || view.ReceiptCode != 0) { return false; }
        }
        else
        {
            if (view.ReceiptOp < 1 || view.ReceiptOp > 2 || view.ReceiptEventId < 1 || view.ReceiptEventId > 32) { return false; }
        }
        if (!view.Rows || view.Rows.Count() > 32 || (!view.Enabled && view.Rows.Count() != 0)) { return false; }
        array<int> ids = new array<int>();
        foreach (HCEventPublicRow row : view.Rows)
        {
            if (!row || row.EventId < 1 || row.EventId > 32 || ids.Find(row.EventId) >= 0) { return false; }
            if (row.Revision < 1 || row.Revision > 1000000 || row.Family < 1 || row.Family > 7) { return false; }
            if (!HCEventDirector.TextValid(row.Title, 96) || row.Status < 1 || row.Status > 6) { return false; }
            if (row.Briefing.Length() > 768) { return false; }
            if (row.Goal != 1 || row.Progress < 0 || row.Progress > row.Goal) { return false; }
            if (row.MaxParticipants < 1 || row.MaxParticipants > 90 || row.Participants < 0 || row.Participants > row.MaxParticipants) { return false; }
            if (row.Joined && row.Participants == 0) { return false; }
            if ((row.Status == HCEventStatus.RESOLVING || row.Status == HCEventStatus.COMPLETED) && row.Progress != row.Goal) { return false; }
            if ((row.Status == HCEventStatus.ANNOUNCED || row.Status == HCEventStatus.ACTIVE) && row.Progress != 0) { return false; }
            if (row.RemainingSeconds < 0 || row.RemainingSeconds > 86400) { return false; }
            if (row.Status >= HCEventStatus.COMPLETED && row.RemainingSeconds != 0) { return false; }
            ids.Insert(row.EventId);
        }
        return true;
    }
    bool Receive(HCEventPublicView view)
    {
        if (!ViewValid(view)) { return false; }
        bool browse = view.Ticket > 0 && view.Ticket == m_BrowseTicket;
        if (view.Ticket > 0 && !browse) { return false; }
        bool changed = view.Session != m_Session;
        if (changed && !browse) { return false; }
        if (!changed && (view.Sequence <= m_Sequence || view.LastRequest < m_Floor)) { return false; }
        HCEventPublicView detached = HCEventWireCodec.CloneView(view);
        if (!detached) { return false; }
        if (changed)
        {
            if (m_Pending) { m_Notice = "Previous request unconfirmed; event session changed"; }
            else { m_Notice = "Event list received; participation is optional"; }
            m_Pending = null;
            m_Retries = 0;
        }
        if (m_Pending)
        {
            bool exact = view.ReceiptId == m_Pending.RequestId && view.ReceiptOp == m_Pending.Op && view.ReceiptEventId == m_Pending.EventId;
            if (exact)
            {
                m_Notice = "Request result " + view.ReceiptCode.ToString();
                m_Pending = null;
                m_Retries = 0;
            }
            else
            {
                if (view.LastRequest >= m_Pending.RequestId)
                {
                    m_Notice = "Previous request unconfirmed; refreshed authoritative view";
                    m_Pending = null;
                    m_Retries = 0;
                }
            }
        }
        m_View = detached;
        m_Session = view.Session;
        m_Sequence = view.Sequence;
        m_Floor = view.LastRequest;
        m_ReceivedAt = GetGame().GetTickTime();
        if (browse) { m_BrowseTicket = 0; }
        return true;
    }
    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || GetGame().IsServer() || sender || rpcType != HCEventWire.RPC_VIEW || !ctx) { return; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || target != viewer || viewer != m_LocalPlayer || !viewer.IsAlive()) { return; }
        HCEventPublicView view;
        if (!ctx.Read(view) || !view) { return; }
        Receive(view);
    }
    void Update()
    {
        if (!m_Listening) { return; }
        float now = GetGame().GetTickTime();
        if (now != now || now < m_LastClock || now > 1000000000)
        {
            Reset();
            m_Notice = "Event clock unavailable; no request replayed";
            return;
        }
        m_LastClock = now;
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (viewer != m_LocalPlayer) { Reset(); m_LocalPlayer = viewer; }
        if (!viewer || !viewer.IsAlive()) { Reset(); return; }
        if (m_BrowseTicket != 0)
        {
            if (now - m_LastSend >= 3)
            {
                HCEventWireRequest browse = new HCEventWireRequest;
                browse.Session = m_Session;
                browse.Ticket = m_BrowseTicket;
                Transmit(browse);
            }
            return;
        }
        if (m_Pending)
        {
            if (now - m_LastSend >= 3)
            {
                if (m_Retries < 2)
                {
                    m_Retries = m_Retries + 1;
                    Transmit(HCEventWireCodec.CloneRequest(m_Pending));
                }
                else
                {
                    m_Notice = "Waiting for receipt; refreshing view, no new participation request";
                    Browse();
                }
            }
            return;
        }
        if (m_Browsing && now >= m_NextBrowse) { Browse(); }
    }
}
