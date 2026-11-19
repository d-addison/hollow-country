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
// UI console and request scheduler only; gameplay remains server-owned.
// Native: 2_GameLib/tools.c ScriptInvoker; EnSystem.c GetHourMinuteSecond;
// EnScript.c array.InsertAt/RemoveOrdered; EnConvert.c int.ToString.
class HCAdminConsoleLine
{
    string Text;
    bool Ok;
}

class HCAdminClient
{
    protected static ref HCAdminClient s_Instance;
    protected bool m_Listening;
    protected bool m_OpenRequested;
    protected bool m_Authorized;
    protected int m_Ticket;
    protected int m_Expected;
    protected int m_SnapshotTicket;
    protected int m_LootTicket;
    protected float m_NextSend;
    protected float m_LastReply;
    protected float m_SnapshotUntil;
    protected float m_OpenUntil;
    protected float m_WaitNoticeAt;
    protected bool m_WaitNoticeShown;
    protected PlayerBase m_Player;
    protected bool m_Pending;
    protected float m_RequestUntil;
    protected string m_Command;
    protected ref array<string> m_Checks = new array<string>;
    protected ref array<ref HCAdminConsoleLine> m_Console = new array<ref HCAdminConsoleLine>;
    ref ScriptInvoker Changed = new ScriptInvoker;
    ref HCAdminReply View;
    ref array<string> Hidden;
    int Revision;
    string Notice;

    static string HCStamp()
    {
        int hour;
        int minute;
        int second;
        GetHourMinuteSecond(hour, minute, second);
        return hour.ToStringLen(2) + ":" + minute.ToStringLen(2) + ":" + second.ToStringLen(2);
    }

    array<ref HCAdminConsoleLine> HCConsole()
    {
        return m_Console;
    }

    void HCFeedback(string text)
    {
        Notice = text;
        HCLog("input", false, "local-validation: " + text);
        Changed.Invoke();
    }

    protected void HCLog(string command, bool ok, string text)
    {
        HCAdminConsoleLine line = new HCAdminConsoleLine;
        string result = "refused";
        if (ok) { result = "ok"; }
        line.Text = "[" + HCStamp() + "] " + command + " | " + result + " | " + text;
        line.Ok = ok;
        m_Console.InsertAt(line, 0);
        while (m_Console.Count() > 50) { m_Console.RemoveOrdered(m_Console.Count() - 1); }
    }

    protected void HCLogReply(HCAdminReply reply, string command)
    {
        bool ok = reply.Notice.IndexOf("result=refused") < 0;
        // Insert backwards so the summary precedes its readable body lines.
        for (int index = reply.Lines.Count() - 1; index >= 0; index--)
        {
            HCLog(command, ok, reply.Lines[index]);
        }
        HCLog(command, ok, reply.Notice);
    }

    bool HCBusy()
    {
        return m_Pending || m_Checks.Count() > 0 || GetGame().GetTickTime() < m_NextSend;
    }

    string HCState()
    {
        if (m_Pending) { return "admin | waiting for server: " + m_Command; }
        if (!HCValid()) { return "refused / not an admin: session unavailable"; }
        if (HCBusy()) { return "admin | busy: waiting for throttle"; }
        return "admin | ready";
    }

    bool HCChecks()
    {
        if (!HCValid() || HCBusy()) { return false; }
        m_Checks.Insert("status");
        m_Checks.Insert("kit");
        m_Checks.Insert("list");
        HCRequestTick();
        return true;
    }

    // Called by the existing gameplay tick; at most one request in flight.
    // Timeout cancels the read-only batch. No automatic gameplay or retry.
    protected void HCRequestTick()
    {
        float now = GetGame().GetTickTime();
        if (m_Pending)
        {
            if (now < m_RequestUntil) { return; }
            m_Pending = false;
            m_Expected = 0;
            m_Checks.Clear();
            Notice = "No server reply: request timeout; remaining checks cancelled. No retry.";
            HCLog(m_Command, false, "client-timeout; server outcome unknown; no retry");
            Revision++;
            Changed.Invoke();
            return;
        }
        if (m_Checks.Count() == 0 || now < m_NextSend || !HCValid()) { return; }
        if (HCSend(m_Checks[0], 0)) { m_Checks.RemoveOrdered(0); }
    }

    void HCCancelChecks()
    {
        m_Checks.Clear();
    }

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
        if (now < m_LastReply) { return false; }
        // The multi-tick lootmap job answers once, at the end. The session stays
        // valid for the derived request wait; HCSend required a fresh session.
        if (m_Pending && m_LootTicket == m_Ticket) { return now <= m_RequestUntil; }
        return now - m_LastReply <= 60;
    }

    // Request wait in seconds: the ordinary 10 s, except the lootmap job whose
    // single final reply is derived from the server job arithmetic (HCAdminLootMap).
    protected float HCWaitSeconds(string command)
    {
        if (HCAdminWire.HCIsLootMap(command)) { return HCAdminLootMap.HCClientWaitSeconds(); }
        return 10;
    }

    // Read-only text command `lootmap <class-or-prefix>`. The server remains the
    // only authority: admin allowlist, EnableDebugSnapshot, cooldown, one job.
    // The client only pre-checks the same bounded filter the server enforces.
    bool HCLootMap(string filter)
    {
        string name = filter;
        if (name.Length() > 1 && name.Get(name.Length() - 1) == "*") { name = name.Substring(0, name.Length() - 1); }
        if (!HCAdminLootMap.HCValidFilter(name)) { HCFeedback("lootmap needs a class name or prefix (letters, digits, _; up to 96; optional trailing *)."); return false; }
        string command = "lootmap " + filter;
        if (!HCAdminWire.HCIsLootMap(command)) { HCFeedback("lootmap request is longer than the wire limit."); return false; }
        return HCSend(command);
    }

    bool HCSend(string command, int value = 0)
    {
        if (!m_Listening) { return false; }
        float now = GetGame().GetTickTime();
        if (m_Pending || now < m_NextSend || m_Ticket >= 1000000000) { return false; }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return false; }
        if (command != "status" && !HCValid()) { return false; }
        if (m_Player != player)
        {
            m_Player = player;
            m_Authorized = false;
            View = null;
            m_SnapshotTicket = 0;
            m_LootTicket = 0;
            Hidden.Clear();
        }
        m_NextSend = now + 1.1;
        m_Ticket++;
        m_Expected = m_Ticket;
        m_Pending = true;
        m_RequestUntil = now + HCWaitSeconds(command);
        m_Command = command;
        HCAdminRequest request = new HCAdminRequest;
        request.Ticket = m_Ticket;
        request.Command = command;
        request.Value = value;
        if (command == "snapshot") { m_SnapshotTicket = request.Ticket; }
        // A late final lootmap reply (after a client timeout) is still accepted by ticket.
        if (HCAdminWire.HCIsLootMap(command)) { m_LootTicket = request.Ticket; }
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(request);
        rpc.Send(null, HCAdminWire.REQUEST, true);
        Notice = "Request sent; waiting for server. No retries or automatic gameplay commands.";
        Revision++;
        Changed.Invoke();
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
        bool loot = reply.Snapshot && m_LootTicket != 0 && reply.Ticket == m_LootTicket;
        if (!current && !capture && !loot) { return; }
        if (!reply.Marks || !reply.Lines) { return; }
        if (reply.Marks.Count() > 512 || reply.Lines.Count() > 64 || reply.Notice.Length() > 1024) { return; }
        for (int markIndex = 0; markIndex < reply.Marks.Count(); markIndex++)
        {
            HCAdminMark mark = reply.Marks[markIndex];
            if (!mark || mark.Layer == "" || mark.Layer.Length() > 48) { return; }
            if (!HCDebugSnapshot.HCPositionValid(mark.Position)) { return; }
            if (mark.Label.Length() > 128 || mark.Detail.Length() > 256) { return; }
        }
        string command = "snapshot";
        if (loot) { command = "lootmap"; }
        if (current)
        {
            command = m_Command;
            m_Pending = false;
            m_Expected = 0;
            // A non-snapshot answer to the lootmap request (a refusal) ends it.
            if (!reply.Snapshot && reply.Ticket == m_LootTicket) { m_LootTicket = 0; }
        }
        // Log the received body before the snapshot reuses the previous status.
        HCLogReply(reply, command);
        m_Authorized = true;
        m_LastReply = GetGame().GetTickTime();
        Notice = reply.Notice;
        if (loot)
        {
            HCMergeLootMap(reply);
            m_LootTicket = 0;
        }
        else if (reply.Snapshot)
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
        Changed.Invoke();
    }

    // Final lootmap reply: its marks replace only the `lootmap` layer, so a captured
    // debug snapshot keeps its layers. Reads the reply marks (already validated:
    // <=512, bounded labels, valid positions); the server stays the only authority.
    protected void HCMergeLootMap(HCAdminReply reply)
    {
        if (!View) { View = new HCAdminReply; }
        int oldIndex = View.Marks.Count() - 1;
        while (oldIndex >= 0)
        {
            if (View.Marks[oldIndex].Layer == "lootmap") { View.Marks.RemoveOrdered(oldIndex); }
            oldIndex--;
        }
        for (int markIndex = 0; markIndex < reply.Marks.Count(); markIndex++)
        {
            if (View.Marks.Count() >= 512) { break; }
            if (reply.Marks[markIndex].Layer == "lootmap") { View.Marks.Insert(reply.Marks[markIndex]); }
        }
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        float keepUntil = m_LastReply + limits.ViewSeconds;
        if (keepUntil > m_SnapshotUntil) { m_SnapshotUntil = keepUntil; }
    }

    void HCTick()
    {
        if (!m_Listening) { return; }
        HCRequestTick();
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
            Changed.Invoke();
        }
        if (m_Authorized && !HCValid()) { HCStop(); }
    }

    void HCStop()
    {
        if (m_Listening) { DayZGame.Event_OnRPC.Remove(HCReceive); }
        m_Listening = false;
        m_Authorized = false;
        m_OpenRequested = false;
        m_Pending = false;
        m_Expected = 0;
        m_Checks.Clear();
        m_Player = null;
        m_SnapshotTicket = 0;
        m_LootTicket = 0;
        View = null;
        Hidden = null;
        Notice = "Admin session expired; press the admin key to authenticate again.";
        Revision++;
        Changed.Invoke();
    }
}
