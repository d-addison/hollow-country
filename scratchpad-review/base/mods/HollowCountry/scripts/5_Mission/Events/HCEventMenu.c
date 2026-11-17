class HCEventMenu : UIScriptedMenu
{
    protected TextListboxWidget m_List;
    protected TextWidget m_Status;
    protected TextWidget m_Detail;
    protected ButtonWidget m_Join;
    protected ButtonWidget m_Leave;
    protected ButtonWidget m_Refresh;
    protected ButtonWidget m_Close;
    protected ref array<ref HCEventPublicRow> m_Rows = new array<ref HCEventPublicRow>();
    protected float m_Elapsed = 0;
    protected int m_Sequence = 0;
    protected string m_Session;
    protected bool m_Opening = true;

    override Widget Init()
    {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_events.layout");
        if (!layoutRoot) { return null; }
        m_List = TextListboxWidget.Cast(layoutRoot.FindAnyWidget("HCEventRows"));
        m_Status = TextWidget.Cast(layoutRoot.FindAnyWidget("HCEventStatus"));
        m_Detail = TextWidget.Cast(layoutRoot.FindAnyWidget("HCEventDetail"));
        m_Join = ButtonWidget.Cast(layoutRoot.FindAnyWidget("HCEventJoin"));
        m_Leave = ButtonWidget.Cast(layoutRoot.FindAnyWidget("HCEventLeave"));
        m_Refresh = ButtonWidget.Cast(layoutRoot.FindAnyWidget("HCEventRefresh"));
        m_Close = ButtonWidget.Cast(layoutRoot.FindAnyWidget("HCEventClose"));
        if (!m_List || !m_Status || !m_Detail || !m_Join || !m_Leave || !m_Refresh || !m_Close)
        {
            layoutRoot.Unlink();
            layoutRoot = null;
            return null;
        }
        m_Join.Enable(false);
        m_Leave.Enable(false);
        return layoutRoot;
    }
    override void OnShow()
    {
        super.OnShow();
        m_Opening = true;
        HCEventClient.Get().SetBrowsing(true);
    }
    int SelectedId()
    {
        if (!m_List) { return 0; }
        int index = m_List.GetSelectedRow();
        if (index < 0 || index >= m_Rows.Count()) { return 0; }
        return m_Rows[index].EventId;
    }
    string StatusName(int status)
    {
        if (status == HCEventStatus.ANNOUNCED) { return "Available"; }
        if (status == HCEventStatus.ACTIVE) { return "In progress"; }
        if (status == HCEventStatus.RESOLVING) { return "Resolving"; }
        if (status == HCEventStatus.COMPLETED) { return "Completed"; }
        if (status == HCEventStatus.EXPIRED) { return "Expired"; }
        return "Cancelled";
    }
    void Render(HCEventPublicView view)
    {
        int selected = SelectedId();
        m_List.ClearItems();
        m_Rows.Clear();
        if (!view) { return; }
        int index = 0;
        foreach (HCEventPublicRow row : view.Rows)
        {
            m_Rows.Insert(row);
            m_List.AddItem("#" + row.EventId.ToString() + " " + row.Title + " - " + StatusName(row.Status), null, 0);
            if (row.EventId == selected) { m_List.SelectRow(index); }
            index = index + 1;
        }
        m_Sequence = view.Sequence;
        m_Session = view.Session;
    }
    void Controls()
    {
        HCEventClient client = HCEventClient.Get();
        int id = SelectedId();
        m_Join.Enable(client.CanSend(HCEventWireOp.JOIN, id));
        m_Leave.Enable(client.CanSend(HCEventWireOp.LEAVE, id));
        if (!client.Fresh())
        {
            m_Status.SetText("Event connection stale or unavailable; actions disabled");
        }
        else
        {
            HCEventPublicView view = client.GetView();
            if (!view.Enabled) { m_Status.SetText("Event service unavailable"); }
            else
            {
                if (view.Rows.Count() == 0) { m_Status.SetText("No missions available"); }
                else { m_Status.SetText(client.GetNotice()); }
            }
        }
        int index = m_List.GetSelectedRow();
        if (index >= 0 && index < m_Rows.Count())
        {
            HCEventPublicRow row = m_Rows[index];
            string membership = "Not joined";
            if (row.Joined) { membership = "Participation recorded"; }
            m_Detail.SetText(membership + " | " + row.Progress.ToString() + "/" + row.Goal.ToString() + " | Participants " + row.Participants.ToString() + "/" + row.MaxParticipants.ToString() + "\nLast reported time left " + row.RemainingSeconds.ToString() + " s");
        }
        else { m_Detail.SetText("Select an event. Joining and leaving are optional; no rewards are issued."); }
    }
    override void Update(float timeslice)
    {
        super.Update(timeslice);
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.IsAlive() || viewer.IsUnconscious()) { Close(); return; }
        m_Elapsed = m_Elapsed + timeslice;
        if (m_Elapsed >= 0.25)
        {
            m_Elapsed = 0;
            HCEventPublicView view = HCEventClient.Get().GetView();
            if (!view || view.Sequence != m_Sequence || view.Session != m_Session) { Render(view); }
            Controls();
        }
        if (m_Opening) { m_Opening = false; return; }
        if (GetUApi())
        {
            UAInput input = GetUApi().GetInputByName("UAHollowCountryEvents");
            if (input && input.LocalPress()) { Close(); }
        }
    }
    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w) { return false; }
        if (w == m_Close) { Close(); return true; }
        if (w == m_Refresh) { HCEventClient.Get().Browse(); return true; }
        if (w == m_Join) { HCEventClient.Get().Send(HCEventWireOp.JOIN, SelectedId()); return true; }
        if (w == m_Leave) { HCEventClient.Get().Send(HCEventWireOp.LEAVE, SelectedId()); return true; }
        if (w == m_List) { Controls(); return true; }
        return super.OnClick(w, x, y, button);
    }
    override void OnHide()
    {
        HCEventClient.Get().SetBrowsing(false);
        if (m_List) { m_List.ClearItems(); }
        if (m_Status) { m_Status.SetText(""); }
        if (m_Detail) { m_Detail.SetText(""); }
        m_Rows.Clear();
        m_Sequence = 0;
        m_Session = "";
        m_Opening = true;
        // Native OnShow locks controls; native OnHide releases exactly once.
        super.OnHide();
    }
}
