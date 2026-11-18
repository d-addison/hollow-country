// W6 #123/#133. Native scripts-1.30.164289: 3_Game/DayZGame.c:991
// Event_OnRPC; gameplay.c:104-117 ScriptRPC.Send; Global/Game.c:914
// GetTickTime, :1120 IsServer; Entities/Object.c:517 IsAlive;
// 3_Game/Entities/Man.c:63 IsUnconscious;
// Global/Game.c:944 GetPlayer, :943 GetUIManager; gameplay.c:636 GetGame;
// 3_Game/tools/UIManager.c:4 EnterScriptedMenu, :59 GetMenu;
// 1_Core/proto/EnScript.c:94 Class.Cast;
// 1_Core/proto/Serializer.c:57-58 Write/Read; EnScript.c:380,385,394,407
// arrays; EnString.c:199 Length; EnDebug.c:96 Print;
// 3_Game/Client/Notifications/NotificationSystem.c:215 AddNotificationExtended.
// Lazy key-only construction. Per frame: O(1) player/expiry checks; no polling.
// Reply validation <=512 vertices, <=64 lines; server-only auth controls UI.
class HCAdminClient
{
    protected static ref HCAdminClient s_Instance;
    protected bool m_Listening;
    protected bool m_OpenRequested;
    protected bool m_Authorized;
    protected int m_Ticket;
    protected int m_Expected;
    protected int m_SnapshotTicket;
    protected float m_NextSend;
    protected float m_LastReply;
    protected float m_SnapshotUntil;
    protected float m_OpenUntil;
    protected float m_WaitNoticeAt;
    protected bool m_WaitNoticeShown;
    protected PlayerBase m_Player;
    ref HCAdminReply View;
    ref array<string> Hidden;
    int Revision;
    string Notice;

    static HCAdminClient HCGet()
    {
        if (!s_Instance) { s_Instance = new HCAdminClient; }
        return s_Instance;
    }

    void HCListen()
    {
        if (m_Listening || GetGame().IsServer()) { return; }
        Hidden = new array<string>;
        DayZGame.Event_OnRPC.Insert(HCReceive);
        m_Listening = true;
    }

    bool HCValid()
    {
        if (!m_Listening || !m_Authorized || !m_Player) { return false; }
        if (m_Player != GetGame().GetPlayer() || !m_Player.IsAlive() || m_Player.IsUnconscious()) { return false; }
        float now = GetGame().GetTickTime();
        return now >= m_LastReply && now - m_LastReply <= 60;
    }

    bool HCSend(string command, int value = 0)
    {
        if (!m_Listening) { return false; }
        float now = GetGame().GetTickTime();
        if (now < m_NextSend || m_Ticket >= 1000000000) { return false; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return false; }
        if (command != "status" && !HCValid()) { return false; }
        if (m_Player != player)
        {
            m_Player = player;
            m_Authorized = false;
            View = null;
            m_SnapshotTicket = 0;
            Hidden.Clear();
        }
        m_NextSend = now + 1.1;
        m_Ticket++;
        m_Expected = m_Ticket;
        HCAdminRequest request = new HCAdminRequest;
        request.Ticket = m_Ticket;
        request.Command = command;
        request.Value = value;
        if (command == "snapshot") { m_SnapshotTicket = request.Ticket; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(request);
        rpc.Send(null, HCAdminWire.REQUEST, true);
        Notice = "Request sent; waiting for server. No retries or automatic gameplay commands.";
        Revision++;
        return true;
    }

    void HCOpen()
    {
        HCListen();
        m_OpenRequested = HCSend("status");
        m_OpenUntil = GetGame().GetTickTime() + 10;
        // The server answers admins only. Stay quiet while a normal reply is due and
        // say something only if it is slow (playtest: admins saw a toast on every open).
        if (m_OpenRequested) { m_WaitNoticeAt = GetGame().GetTickTime() + 2.5; m_WaitNoticeShown = false; }
        else { HCNotify("Admin request not sent: wait a second, and be alive and conscious.", 5); }
    }

    // Client-only native notification; no server state, no network.
    void HCNotify(string text, float seconds)
    {
        if (GetGame().IsServer()) { return; }
        NotificationSystem.AddNotificationExtended(seconds, "Hollow Country admin", text);
    }

    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Listening || GetGame().IsServer() || sender || target) { return; }
        if (rpcType != HCAdminWire.REPLY || !ctx) { return; }
        if (m_Player != GetGame().GetPlayer()) { HCStop(); return; }
        HCAdminReply reply;
        if (!ctx.Read(reply) || !reply || !reply.Authorized) { return; }
        bool current = reply.Ticket == m_Expected;
        bool capture = reply.Snapshot && reply.Ticket == m_SnapshotTicket;
        if (!current && !capture) { return; }
        if (!reply.Marks || !reply.Lines) { return; }
        if (reply.Marks.Count() > 512 || reply.Lines.Count() > 64 || reply.Notice.Length() > 1024) { return; }
        for (int markIndex = 0; markIndex < reply.Marks.Count(); markIndex++)
        {
            HCAdminMark mark = reply.Marks[markIndex];
            if (!mark || mark.Layer == "" || mark.Layer.Length() > 48) { return; }
            if (!HCDebugSnapshot.HCPositionValid(mark.Position)) { return; }
            if (mark.Label.Length() > 128 || mark.Detail.Length() > 256) { return; }
        }
        m_Authorized = true;
        m_LastReply = GetGame().GetTickTime();
        Notice = reply.Notice;
        if (reply.Snapshot)
        {
            if (View) { reply.Lines = View.Lines; }
            View = reply;
            m_SnapshotUntil = m_LastReply + 60;
            m_SnapshotTicket = 0;
        }
        else if (reply.Lines.Count() > 0)
        {
            if (!View) { View = new HCAdminReply; }
            View.Lines = reply.Lines;
        }
        Revision++;
    }

    void HCTick()
    {
        if (!m_Listening) { return; }
        float now = GetGame().GetTickTime();
        if (m_OpenRequested)
        {
            if (HCValid())
            {
                m_OpenRequested = false;
                if (!GetGame().GetUIManager().GetMenu()) { GetGame().GetUIManager().EnterScriptedMenu(HCAdminWire.MENU, null); }
            }
            else if (now >= m_WaitNoticeAt && !m_WaitNoticeShown)
            {
                m_WaitNoticeShown = true;
                HCNotify("Still waiting for the server's admin reply...", 4);
            }
            else if (now >= m_OpenUntil)
            {
                HCNotify("No admin reply from the server. Your Steam64 ID must be in the server's profiles/HollowCountry/admins.json (restart after editing) and EnableAdminMap must be true.", 12);
                HCStop();
                return;
            }
        }
        if (View && View.Marks.Count() > 0 && now >= m_SnapshotUntil)
        {
            View.Marks.Clear();
            Revision++;
        }
        if (m_Authorized && !HCValid()) { HCStop(); }
    }

    void HCStop()
    {
        if (m_Listening) { DayZGame.Event_OnRPC.Remove(HCReceive); }
        m_Listening = false;
        m_Authorized = false;
        m_OpenRequested = false;
        m_Player = null;
        m_SnapshotTicket = 0;
        View = null;
        Hidden = null;
        Notice = "Admin session expired; press the admin key to authenticate again.";
        Revision++;
    }
}
