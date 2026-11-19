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
    protected float m_LootUntil;
    protected float m_LootViewUntil;
    // #194: filter of the job in flight, filter of the marks now on the map, and whether
    // those marks were kept after a refused final reply (previous run).
    protected string m_LootRunFilter;
    protected string m_LootShownFilter;
    protected bool m_LootStale;
    // #195: lootmap marks are on the map. Its own flag, so an unfiltered run (empty filter) is
    // still labelled (filter=all) instead of the label depending on a non-empty filter text.
    protected bool m_LootMarksShown;
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
        if (m_LootTicket != 0) { return "admin | ready | lootmap job running on the server"; }
        string layer = HCLootLayerStatus();
        if (layer != "") { return "admin | ready | " + layer; }
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
        // An acknowledged lootmap job answers once more, much later, by ticket. The
        // session (UI gating only; the server re-checks the admin allowlist) stays
        // valid until the derived job window (HCExpireLoot) ends.
        if (m_LootTicket != 0 && now <= m_LootUntil) { return true; }
        return now - m_LastReply <= 60;
    }

    // Read-only text command `lootmap <class-or-prefix>`. The server remains the
    // only authority: admin allowlist, EnableDebugSnapshot, cooldown, one job.
    // The client only pre-checks the same bounded filter the server enforces.
    // Like `snapshot`, the server acks at once (started, ticket, estimated ticks)
    // so the client is free; the marks arrive later and are matched by ticket.
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
            m_LootUntil = 0;
            Hidden.Clear();
        }
        m_NextSend = now + 1.1;
        m_Ticket++;
        m_Expected = m_Ticket;
        m_Pending = true;
        m_RequestUntil = now + 10;
        m_Command = command;
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
        if (!current && !capture && !loot)
        {
            // Session ended or client timed out first: the server may still finish.
            if (reply.Snapshot) { Print("" + "[HC Admin] client dropped late reply ticket=" + reply.Ticket.ToString() + " reason=no_matching_request; server outcome unknown"); }
            return;
        }
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
            // The ack of an accepted lootmap request starts tracking its final reply.
            // A refusal (including `lootmap_job_running`) leaves any running job tracked.
            if (!reply.Snapshot && HCAdminWire.HCIsLootMap(command) && reply.Notice.IndexOf("result=refused") < 0)
            {
                // Window sized from the deadline the SERVER sent (ack budget_ms; floor and
                // ceiling in HCClientWindowSeconds); an unreadable ack gets the ceiling.
                int budgetMs = HCAdminLootMap.HCAckInt(reply.Notice, "budget_ms=");
                m_LootTicket = reply.Ticket;
                m_LootRunFilter = HCLootFilterOf(command);
                m_LootUntil = GetGame().GetTickTime() + HCAdminLootMap.HCClientWindowSeconds(budgetMs);
            }
        }
        // Log the received body before the snapshot reuses the previous status.
        HCLogReply(reply, command);
        m_Authorized = true;
        m_LastReply = GetGame().GetTickTime();
        Notice = reply.Notice;
        if (loot)
        {
            // A refused or failed final reply keeps the previous lootmap marks (owner-safe
            // default) and shows its reason; only an ok reply replaces the layer.
            if (reply.Notice.IndexOf("result=refused") < 0)
            {
                HCMergeLootMap(reply);
                m_LootShownFilter = m_LootRunFilter;
                m_LootMarksShown = true;
                m_LootStale = false;
            }
            else if (HCLootMarkCount() > 0)
            {
                // The kept layer is labelled with the filter of the run that drew it (#194).
                m_LootStale = true;
                Notice = Notice + "; previous lootmap marks kept; previous run filter=" + HCLootFilterLabel(m_LootShownFilter);
            }
            m_LootTicket = 0;
        }
        else if (reply.Snapshot)
        {
            if (View) { reply.Lines = View.Lines; }
            HCCarryLootMarks(reply);
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

    // The filter text of a `lootmap <filter>` command (bounded by Length()).
    protected string HCLootFilterOf(string command)
    {
        int length = command.Length();
        if (length <= 8) { return ""; }
        return command.Substring(8, length - 8);
    }

    // Status text for the lootmap layer on the map: the filter its marks came from,
    // and that they are from the previous run when a refused final reply kept them.
    // Empty when no lootmap marks are shown.
    string HCLootLayerStatus()
    {
        if (!m_LootMarksShown || HCLootMarkCount() < 1) { return ""; }
        string text = "lootmap marks: filter=" + HCLootFilterLabel(m_LootShownFilter);
        if (m_LootStale) { text = text + " (previous run)"; }
        return text;
    }

    // Layer list row text (#196). Only the lootmap row is labelled: the filter its marks came
    // from, and `previous run` when a refused or failed final reply kept them. Other layers and an
    // empty lootmap layer read as their plain name. The toggle still uses the raw layer name.
    string HCLayerRowLabel(string layer)
    {
        if (layer != "lootmap" || !m_LootMarksShown) { return layer; }
        string text = layer + " [filter=" + HCLootFilterLabel(m_LootShownFilter);
        if (m_LootStale) { text = text + ", previous run"; }
        return text + "]";
    }

    // Label text for a run's filter: the filter itself, or `all` for an empty (unfiltered) one.
    protected string HCLootFilterLabel(string filter)
    {
        if (filter == "") { return "all"; }
        return filter;
    }

    protected int HCLootMarkCount()
    {
        if (!View) { return 0; }
        int found = 0;
        for (int markIndex = 0; markIndex < View.Marks.Count(); markIndex++)
        {
            if (View.Marks[markIndex].Layer == "lootmap") { found++; }
        }
        return found;
    }

    // Final lootmap reply: its marks replace only the `lootmap` layer, so a captured
    // debug snapshot keeps its layers. Reads the reply marks (already validated:
    // <=512, bounded labels, valid positions); the server stays the only authority.
    // At most MaxPositionsPerReply lootmap marks are kept, 512 snapshot marks + those.
    protected void HCMergeLootMap(HCAdminReply reply)
    {
        if (!View) { View = new HCAdminReply; }
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        int oldIndex = View.Marks.Count() - 1;
        while (oldIndex >= 0)
        {
            if (View.Marks[oldIndex].Layer == "lootmap") { View.Marks.RemoveOrdered(oldIndex); }
            oldIndex--;
        }
        int kept = 0;
        for (int markIndex = 0; markIndex < reply.Marks.Count(); markIndex++)
        {
            if (kept >= limits.MaxPositionsPerReply) { break; }
            if (reply.Marks[markIndex].Layer == "lootmap") { View.Marks.Insert(reply.Marks[markIndex]); kept++; }
        }
        m_LootViewUntil = m_LastReply + limits.ViewSeconds;
    }

    // A later snapshot replaces the view; its marks are merged with, not over, the
    // lootmap layer (which keeps its own, longer ViewSeconds timer).
    protected void HCCarryLootMarks(HCAdminReply fresh)
    {
        if (!View) { return; }
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        int cap = 512 + limits.MaxPositionsPerReply;
        for (int markIndex = 0; markIndex < View.Marks.Count(); markIndex++)
        {
            if (fresh.Marks.Count() >= cap) { break; }
            if (View.Marks[markIndex].Layer == "lootmap") { fresh.Marks.Insert(View.Marks[markIndex]); }
        }
    }

    // Per-layer expiry: snapshot layers after their 60 s, the lootmap layer after
    // ViewSeconds. O(1) per frame until a timer is due.
    protected void HCExpireMarks(float now)
    {
        if (!View) { return; }
        bool snapshotDue = m_SnapshotUntil > 0 && now >= m_SnapshotUntil;
        bool lootDue = m_LootViewUntil > 0 && now >= m_LootViewUntil;
        if (!snapshotDue && !lootDue) { return; }
        int index = View.Marks.Count() - 1;
        while (index >= 0)
        {
            bool isLoot = View.Marks[index].Layer == "lootmap";
            if (isLoot && lootDue) { View.Marks.RemoveOrdered(index); }
            else if (!isLoot && snapshotDue) { View.Marks.RemoveOrdered(index); }
            index--;
        }
        if (snapshotDue) { m_SnapshotUntil = 0; }
        if (lootDue)
        {
            m_LootViewUntil = 0;
            m_LootShownFilter = "";
            m_LootMarksShown = false;
            m_LootStale = false;
        }
        Revision++;
        Changed.Invoke();
    }

    // The derived job window passed without the final reply: stop tracking it.
    protected void HCExpireLoot(float now)
    {
        if (m_LootTicket == 0 || now <= m_LootUntil) { return; }
        m_LootTicket = 0;
        HCLog("lootmap", false, "client-timeout: no final reply within the derived job window; server outcome unknown");
        Revision++;
        Changed.Invoke();
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
        HCExpireMarks(now);
        HCExpireLoot(now);
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
        if (m_LootTicket != 0) { Print("" + "[HC Admin] client lootmap ticket=" + m_LootTicket.ToString() + " dropped: session ended; server may still finish; final reply ignored"); }
        m_LootTicket = 0;
        View = null;
        Hidden = null;
        Notice = "Admin session expired; press the admin key to authenticate again.";
        Revision++;
        Changed.Invoke();
    }
}
