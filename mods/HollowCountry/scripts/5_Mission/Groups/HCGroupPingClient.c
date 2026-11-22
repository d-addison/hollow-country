// #256. Native 1.30: Game.c camera/screen projection; DayZPhysics.c:199;
// UAInput.c LocalPress/GetInputByName. Reuses HC group icon layout and RPC listener.
// Three widgets maximum; no local prediction, teammate positions or map layer.
modded class HCGroupClient
{
    protected ref HCGroupPingWire m_HCLookFrame;
    protected ref array<Widget> m_HCLookWidgets = new array<Widget>;
    protected ref array<TextWidget> m_HCLookLabels = new array<TextWidget>;

    override void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (rpcType != HCGroupPingWire.RPC) { super.OnRPC(sender, target, rpcType, ctx); return; }
        if (!m_Listening || GetGame().IsServer() || sender || target || !ctx) { return; }
        HCGroupPingWire incoming;
        if (!ctx.Read(incoming) || !incoming || !incoming.Points || !incoming.Expires) { return; }
        HCGroupSnapshot view = GetSnapshot();
        if (!view || !view.Enabled || incoming.GroupId != view.GroupId || incoming.Epoch != view.Epoch || incoming.Session != view.Session) { return; }
        if (incoming.Points.Count() > 3 || incoming.Expires.Count() != incoming.Points.Count()) { return; }
        int now = HCGroupClock.Utc();
        for (int i = 0; i < incoming.Points.Count(); i++)
        {
            if (!HCGroupRules.PositionValid(incoming.Points.Get(i))) { return; }
            // Server and client clocks may differ: rebase to the client clock
            // using the remaining lifetime the server measured at send.
            int remaining = incoming.Expires.Get(i) - incoming.Now;
            if (now < 1 || incoming.Now < 1 || remaining < 1 || remaining > 10) { return; }
            incoming.Expires.Set(i, now + remaining);
        }
        m_HCLookFrame = incoming;
    }

    void HCClearLookPing()
    {
        foreach (Widget root : m_HCLookWidgets)
        {
            if (root) { root.Unlink(); }
        }
        m_HCLookWidgets.Clear();
        m_HCLookLabels.Clear();
        m_HCLookFrame = null;
    }

    override void Stop()
    {
        HCClearLookPing();
        super.Stop();
    }

    void HCUpdateLookPing()
    {
        HCGroupSnapshot view = GetSnapshot();
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!m_HCLookFrame) { return; }
        if (!view || !view.Enabled || !view.Settings || !view.Settings.HCTeamPingEnabled || !viewer || !viewer.IsAlive() || viewer.IsUnconscious()) { HCClearLookPing(); return; }
        if (view.GroupId != m_HCLookFrame.GroupId || view.Epoch != m_HCLookFrame.Epoch || view.Session != m_HCLookFrame.Session) { HCClearLookPing(); return; }
        int now = HCGroupClock.Utc();
        vector camera = GetGame().GetCurrentCameraPosition();
        vector forward = GetGame().GetCurrentCameraDirection();
        int used;
        bool active;
        // <=3 points. Hidden behind camera/offscreen; never clamped to an edge.
        for (int i = 0; i < m_HCLookFrame.Points.Count() && i < 3; i++)
        {
            if (now < 1 || m_HCLookFrame.Expires.Get(i) <= now) { continue; }
            active = true;
            vector point = m_HCLookFrame.Points.Get(i);
            float distance = vector.Distance(viewer.GetPosition(), point);
            if (distance > 1000 || GetGame().GetUIManager().GetMenu()) { continue; }
            vector facing = point - camera;
            if (vector.Dot(facing, forward) <= 0) { continue; }
            vector relative = GetGame().GetScreenPosRelative(point);
            if (relative[0] < 0 || relative[0] > 1 || relative[1] < 0 || relative[1] > 1) { continue; }
            if (used == m_HCLookWidgets.Count())
            {
                Widget created = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_group_icon.layout");
                if (!created) { break; }
                TextWidget label = TextWidget.Cast(created.FindAnyWidget("HCLabel"));
                ImageWidget mark = ImageWidget.Cast(created.FindAnyWidget("HCMark"));
                if (!label || !mark) { created.Unlink(); break; }
                HCGroupWorldIcons.Scale(created, label, mark, view.Settings);
                mark.SetColor(ARGB(255,255,210,70));
                m_HCLookWidgets.Insert(created);
                m_HCLookLabels.Insert(label);
            }
            int metres = Math.Round(distance);
            m_HCLookLabels.Get(used).SetText("Group ping " + metres.ToString() + " m");
            vector screen = GetGame().GetScreenPos(point);
            Widget root = m_HCLookWidgets.Get(used);
            root.SetPos(screen[0] - 8, screen[1] - 12);
            root.Show(true);
            used++;
        }
        for (int j = used; j < m_HCLookWidgets.Count(); j++) { m_HCLookWidgets.Get(j).Show(false); }
        if (!active) { HCClearLookPing(); }
    }
}
modded class MissionGameplay
{
    protected UAInput m_HCLookPingInput;
    protected float m_HCLookPingAfter;
    override void OnInit()
    {
        super.OnInit();
        if (!GetGame().IsServer() && GetUApi()) { m_HCLookPingInput = GetUApi().GetInputByName("UAHollowCountryLookPing"); }
    }
    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (GetGame().IsServer()) { return; }
        HCGroupClient client = HCGroupClient.Get();
        if (!client) { return; }
        client.HCUpdateLookPing();
        if (IsControlDisabled() || GetGame().GetUIManager().GetMenu()) { return; }
        if (!m_HCLookPingInput || !m_HCLookPingInput.LocalPress()) { return; }
        float tick = GetGame().GetTickTime();
        if (tick < m_HCLookPingAfter) { return; }
        HCGroupSnapshot view = client.GetSnapshot();
        if (!view || !view.Enabled || !view.Settings || !view.Settings.HCTeamPingEnabled || view.GroupId < 1 || client.IsBusy()) { return; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return; }
        m_HCLookPingAfter = tick + 5;
        vector origin = GetGame().GetCurrentCameraPosition();
        vector finish = origin + GetGame().GetCurrentCameraDirection() * 300;
        vector contact;
        vector normal;
        int component;
        if (!DayZPhysics.RaycastRV(origin, finish, contact, normal, component, null, null, player, false, false, ObjIntersectView)) { return; }
        HCGroupRequest request = new HCGroupRequest;
        request.Op = HCGroupOp.TEAM_PING;
        request.Role = HCGroupPingWire.LOOK;
        request.Position = contact;
        client.Send(request);
    }
}
