// W6 #123/#133. Native scripts-1.30.164289:
// 3_Game/DayZGame.c:991 Event_OnRPC; gameplay.c:104-117 ScriptRPC.Send,
// :370 PlayerIdentity.GetPlainId, :636 GetGame; Entities/Man.c:21 GetIdentity;
// Entities/Object.c:287 GetPosition, :517 IsAlive; Global/Game.c:914 GetTickTime,
// :612 ConfigIsExisting, :945 GetPlayers, :1120 IsServer;
// 1_Core/proto/Serializer.c:57-58 Read/Write;
// EnScript.c:94 Class.Cast, :380,394,407 Count/Find/Insert;
// EnString.c:199 Length; EnConvert.c:30 ToString; EnDebug.c:96 Print;
// EnSystem.c:397 FileExist. JSON/file operations reuse HCV2ThreatStore/HCGroupJson.
// Tick bound: ONE command, ONE Describe (<=64 points/8 routes), <=32 sender
// matches; final snapshot visits <=1024 points +128*64 vertices, emits <=512
// vertices, <=16 layers. Request-only capture; one global pending capture.
// Ingress: <=1 queued command per core tick; per-admin 1s commands/5s snapshot.
// Off: no allocations, RPC subscription, profile reads or tick work.
class HCAdminDeniedPeer
{
    string PlainId;
    float Until;
}

class HCAdminModule : HCModule
{
    static const string PATH = "$profile:HollowCountry/admins.json";
    protected bool m_Running;
    protected bool m_Printed;
    protected ref HCAdminAllowlist m_Admins;
    protected ref array<ref HCAdminDeniedPeer> m_Denied;
    protected ref array<float> m_CommandAt;
    protected ref array<float> m_SnapshotAt;
    protected ref array<int> m_Tickets;
    protected ref array<PlayerIdentity> m_Identities;
    protected ref array<Man> m_Players;
    protected PlayerIdentity m_PendingSender;
    protected ref HCAdminRequest m_Pending;
    protected PlayerIdentity m_CaptureSender;
    protected int m_CaptureTicket;
    protected ref HCDebugSnapshot m_Capture;
    protected bool m_DebugEnabled;
    protected float m_DeniedOverflowAt;
    protected ref HCAdminLootMap m_LootMap;
    protected PlayerIdentity m_LootMapSender;
    protected int m_LootMapTicket;
    protected float m_LootMapAfter;

    override string GetName() { return "AdminMap"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableAdminMap; }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || m_Running || !GetGame().IsServer()) { return; }
        if (!m_Printed)
        {
            Print(HCV2Admission.Line("AdminMap", true, "W6-123-133", false));
            m_Printed = true;
        }
        if (!HCV2ThreatStore<HCAdminAllowlist>.CanOpen(PATH)) { return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCAdminAllowlist>.Load(PATH, 4096, m_Admins)) { return; }
        }
        else
        {
            m_Admins = new HCAdminAllowlist;
            if (!HCV2ThreatStore<HCAdminAllowlist>.Save(PATH, m_Admins, 4096)) { return; }
        }
        if (!m_Admins || !m_Admins.PlainIds) { return; }
        if (m_Admins.PlainIds.Count() > 32) { Print("[HC Admin] allowlist refused: count exceeds 32"); return; }
        array<string> seen = new array<string>;
        for (int idIndex = 0; idIndex < m_Admins.PlainIds.Count(); idIndex++)
        {
            string plainId = m_Admins.PlainIds[idIndex];
            if (plainId == "" || plainId.Length() > 64 || seen.Find(plainId) >= 0)
            {
                Print("[HC Admin] allowlist refused: invalid or duplicate entry; IDs withheld");
                m_Admins = null;
                return;
            }
            seen.Insert(plainId);
        }
        m_Denied = new array<ref HCAdminDeniedPeer>;
        m_CommandAt = new array<float>;
        m_SnapshotAt = new array<float>;
        m_Tickets = new array<int>;
        m_Identities = new array<PlayerIdentity>;
        m_Players = new array<Man>;
        for (int slot = 0; slot < m_Admins.PlainIds.Count(); slot++)
        {
            m_CommandAt.Insert(0);
            m_SnapshotAt.Insert(0);
            m_Tickets.Insert(0);
            m_Identities.Insert(null);
        }
        m_DebugEnabled = settings.EnableDebugSnapshot;
        m_Running = true;
        DayZGame.Event_OnRPC.Insert(HCReceive);
        Print("[HC Admin] allowlist count=" + m_Admins.PlainIds.Count().ToString() + "; native acceptance pending");
    }

    bool HCAuthorized(PlayerIdentity sender)
    {
        if (!m_Running || !sender || !m_Admins) { return false; }
        return m_Admins.PlainIds.Find(sender.GetPlainId()) >= 0;
    }

    // A fixed 64-peer quarantine retains opaque IDs, never prints them.
    // At saturation one anonymous aggregate line/minute replaces per-peer logs.
    void HCRefused(PlayerIdentity sender)
    {
        if (!m_Running || !sender) { return; }
        float now = GetGame().GetTickTime();
        string plainId = sender.GetPlainId();
        int reusable = -1;
        for (int denyIndex = 0; denyIndex < m_Denied.Count(); denyIndex++)
        {
            HCAdminDeniedPeer peer = m_Denied[denyIndex];
            if (peer.PlainId == plainId && now < peer.Until) { return; }
            if (now >= peer.Until) { reusable = denyIndex; }
        }
        if (reusable < 0 && m_Denied.Count() >= 64)
        {
            if (now >= m_DeniedOverflowAt)
            {
                m_DeniedOverflowAt = now + 60;
                Print("[HC Admin] cmd=request result=refused reason=non-admin; refusal-log-cap");
            }
            return;
        }
        HCAdminDeniedPeer denied = new HCAdminDeniedPeer;
        denied.PlainId = plainId;
        denied.Until = now + 60;
        if (reusable >= 0) { m_Denied[reusable] = denied; }
        else { m_Denied.Insert(denied); }
        Print("[HC Admin] cmd=request result=refused reason=non-admin");
    }

    bool HCDispatch(PlayerIdentity sender, string command, int value, int ticket)
    {
        if (!HCAuthorized(sender)) { HCRefused(sender); return false; }
        if (command == "status") { HCStatus(sender, ticket); return true; }
        if (HCAdminWire.HCIsLootMap(command)) { return HCStartLootMap(sender, command, ticket); }
        return HCCommand(sender, command, value, ticket);
    }

    protected bool HCKnown(string command)
    {
        return HCAdminCatalog.HCKnown(command);
    }

    // Text-only read command registered on the existing RPC; no new wire data.
    // Native EnString.c:113,199 Substring/Length; EnSystem.c:397,525
    // FileExist/MakeDirectory. Profile export reuses verified intent/backup IO.
    protected bool HCStartLootMap(PlayerIdentity sender, string command, int ticket)
    {
        if (!GetGame().IsServer() || !HCAuthorized(sender)) { return false; }
        if (!m_DebugEnabled) { HCReply(sender, ticket, "lootmap", false, "EnableDebugSnapshot-off"); return false; }
        if (command.Length() <= 8) { HCReply(sender, ticket, "lootmap", false, "usage_lootmap_class_or_prefix"); return false; }
        if (m_LootMap) { HCReply(sender, ticket, "lootmap", false, "lootmap_job_running; one job at a time"); return false; }
        float now = GetGame().GetTickTime();
        if (now < m_LootMapAfter) { HCReply(sender, ticket, "lootmap", false, "lootmap_cooldown"); return false; }
        HCAdminLootMapLimits limits = new HCAdminLootMapLimits;
        m_LootMapAfter = now + limits.CooldownSeconds;
        HCAdminLootMap job = new HCAdminLootMap;
        string filter = command.Substring(8, command.Length() - 8);
        int tickMs = HCServer.Get().GetSettings().TickIntervalMs;
        bool started = job.HCStart(filter, tickMs);
        string root = "$profile:HollowCountry/debug";
        if (!HCV2ThreatStore<HCAdminLootDocument>.CanOpen(HCAdminLootMap.PATH))
        {
            HCReply(sender, ticket, "lootmap", false, "lootmap_store_recovery_required"); return false;
        }
        if (!FileExist(root) && !MakeDirectory(root)) { HCReply(sender, ticket, "lootmap", false, "lootmap_export_directory"); return false; }
        // Replace any previous export with pending/refused, before work begins.
        if (!HCV2ThreatStore<HCAdminLootDocument>.Save(HCAdminLootMap.PATH, job.HCDocument(), HCAdminLootMap.MAX_BYTES))
        {
            HCReply(sender, ticket, "lootmap", false, "lootmap_export_failed"); return false;
        }
        if (!started)
        {
            // A refusal is an ordinary reply, not the final-marks reply (Snapshot).
            HCAdminReply refusal = job.HCReply(ticket);
            refusal.Snapshot = false;
            HCSend(sender, refusal);
            return false;
        }
        m_LootMap = job;
        m_LootMapSender = sender;
        m_LootMapTicket = ticket;
        string startLine = "[HC Plan] wp=168-5 state=started cells=" + job.HCTotalCells().ToString() + " sub_cell_m=" + limits.SubCellM.ToString();
        startLine += " max_ticks=" + job.HCMaxTicks().ToString() + " rows_per_tick=" + limits.MaxRowsPerStep.ToString();
        startLine += " positions=0 query_cost=unmeasured runtime=PENDING";
        Print("" + startLine);
        // Immediate ack, the snapshot pattern: the client is freed at once, then the
        // one final marks RPC follows by this ticket (no automatic retries). If the
        // client session ends first the final reply is dropped client-side.
        string ack = "started ticket=" + ticket.ToString() + " est_ticks=" + job.HCMaxTicks().ToString();
        ack += " cells=" + job.HCTotalCells().ToString() + " final_reply=by_ticket; query_cost=unmeasured";
        HCReply(sender, ticket, "lootmap", true, ack);
        return true;
    }

    protected void HCLootMapTick()
    {
        if (!m_LootMap) { return; }
        if (!GetGame().IsServer() || !HCAuthorized(m_LootMapSender) || !HCPlayer(m_LootMapSender))
        {
            // Leave the export pending, never relabel cancelled work complete.
            Print("[HC Plan] wp=168-5 state=refused reason=sender_unavailable runtime=PENDING");
            m_LootMap = null;
            m_LootMapSender = null;
            return;
        }
        if (!m_LootMap.HCStep()) { return; }
        HCAdminLootDocument data = m_LootMap.HCDocument();
        if (!HCV2ThreatStore<HCAdminLootDocument>.Save(HCAdminLootMap.PATH, data, HCAdminLootMap.MAX_BYTES))
        {
            HCReply(m_LootMapSender, m_LootMapTicket, "lootmap", false, "lootmap_export_failed");
        }
        else
        {
            HCAdminReply reply = m_LootMap.HCReply(m_LootMapTicket);
            Print(reply.Notice);
            Print("[HC Plan] wp=168-5 state=" + data.state + " reason=" + data.reason + " positions=" + data.points.Count().ToString() + " runtime=PENDING");
            HCSend(m_LootMapSender, reply);
        }
        m_LootMap = null;
        m_LootMapSender = null;
    }

    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Running || rpcType != HCAdminWire.REQUEST || !GetGame().IsServer()) { return; }
        if (!HCAuthorized(sender)) { HCRefused(sender); return; }
        if (target || !ctx) { return; }
        int slot = m_Admins.PlainIds.Find(sender.GetPlainId());
        float now = GetGame().GetTickTime();
        if (now < m_CommandAt[slot]) { return; }
        m_CommandAt[slot] = now + 1;
        HCAdminRequest request;
        if (!ctx.Read(request) || !request) { HCReply(sender, 0, "request", false, "malformed"); return; }
        if (!HCKnown(request.Command) || request.Ticket < 1)
        {
            HCReply(sender, request.Ticket, "request", false, "unknown-command-or-ticket");
            return;
        }
        if (m_Identities[slot] != sender) { m_Identities[slot] = sender; m_Tickets[slot] = 0; }
        if (request.Ticket <= m_Tickets[slot])
        {
            HCReply(sender, request.Ticket, request.Command, false, "replayed-ticket");
            return;
        }
        m_Tickets[slot] = request.Ticket;
        if (m_Pending) { HCReply(sender, request.Ticket, request.Command, false, "command-queue-cap=1"); return; }
        m_PendingSender = sender;
        m_Pending = request;
    }

    protected PlayerBase HCPlayer(PlayerIdentity sender)
    {
        if (m_Players.Count() > 32) { return null; }
        for (int playerIndex = 0; playerIndex < m_Players.Count(); playerIndex++)
        {
            PlayerBase player = PlayerBase.Cast(m_Players[playerIndex]);
            if (!player || !player.IsAlive()) { continue; }
            // Match by identity id: the RPC sender and the player's identity are not
            // guaranteed to be the same script reference (playtest: kit/list refused).
            PlayerIdentity identity = player.GetIdentity();
            if (identity && sender && identity.GetId() == sender.GetId()) { return player; }
        }
        return null;
    }

    protected void HCSend(PlayerIdentity sender, HCAdminReply reply)
    {
        if (!HCAuthorized(sender)) { return; }
        reply.Authorized = true;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(reply);
        rpc.Send(null, HCAdminWire.REPLY, true, sender);
    }

    protected void HCReply(PlayerIdentity sender, int ticket, string command, bool ok, string reason)
    {
        string result = "refused";
        if (ok) { result = "ok"; }
        string line = "[HC Admin] cmd=" + command + " result=" + result + " reason=" + reason;
        Print("" + line);
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = line;
        HCSend(sender, reply);
    }

    void HCStatus(PlayerIdentity sender, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = "Status: enabled means requested; n/a means no public metric. Runtime acceptance pending.";
        reply.Authorized = HCAuthorized(sender);
        HCServer.Get().HCAdminDescribe(reply);
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { Print(reply.Lines[lineIndex]); }
        Print("[HC Admin] cmd=status result=ok reason=bounded-module-status");
        HCSend(sender, reply);
    }

    // Test-kit availability: one line per allowlisted command, read-only.
    void HCKit(PlayerIdentity sender, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = "Kit: available=0 names the reason. Runtime acceptance pending.";
        HCServer.Get().HCAdminKit(reply);
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { Print(reply.Lines[lineIndex]); }
        Print("[HC Admin] cmd=kit result=ok reason=bounded-command-list");
        HCSend(sender, reply);
    }

    // Read-only state near the admin: sitter, memory heat, drops, forage, decay.
    void HCList(PlayerIdentity sender, int ticket, vector pos)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = "List: state near you, read-only. Runtime acceptance pending.";
        HCServer.Get().HCAdminNearby(reply, pos);
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { Print(reply.Lines[lineIndex]); }
        Print("[HC Admin] cmd=list result=ok reason=bounded-nearby-state");
        HCSend(sender, reply);
    }

    protected HCModule HCNamed(string name)
    {
        return HCServer.Get().HCAdminModuleNamed(name);
    }

    // Test-kit hooks; each calls its owner's normal bounded path and never spawns.
    protected bool HCExtra(PlayerBase player, vector pos, string command, int value, out string reason)
    {
        reason = "module-unavailable";
        if (command == "clear")
        {
            HCInfectedModule infected = HCInfectedModule.Instance;
            if (infected) { return infected.HCAdminClearSitter(reason); }
        }
        else if (command == "memory") { return HCInfectedMemory.HCAdminHeat(pos, value, reason); }
        else if (command == "radio")
        {
            HCRadioChatter radio = HCRadioChatter.Get();
            if (radio) { return radio.HCAdminRadio(player, reason); }
        }
        else if (command == "deaddrop")
        {
            HCDeadDrops drops = HCDeadDrops.Get();
            if (drops) { return drops.HCAdminDeadDrop(pos, reason); }
        }
        else if (command == "loot")
        {
            HCSearchRefreshModule loot = HCSearchRefreshModule.Cast(HCNamed("LootRefresh"));
            if (loot) { return loot.HCAdminDue(reason); }
        }
        else if (command == "forage")
        {
            HCForageModule forage = HCForageModule.Cast(HCNamed("Forage"));
            if (forage) { return forage.HCAdminForage(player, reason); }
        }
        else if (command == "decay")
        {
            HCSettlementDecay decay = HCSettlementDecay.Cast(HCNamed("SettlementDecay"));
            if (decay) { return decay.HCAdminTown(pos, reason); }
        }
        else if (command == "weather")
        {
            HCWeatherDaysModule weather = HCWeatherDaysModule.Cast(HCNamed("WeatherDays"));
            if (weather) { return weather.HCAdminWeather(value, reason); }
        }
        return false;
    }

    bool HCCommand(PlayerIdentity sender, string command, int value, int ticket)
    {
        PlayerBase player = HCPlayer(sender);
        if (!player) { HCReply(sender, ticket, command, false, "live-sender-unavailable-or-player-cap=32"); return false; }
        if (command == "kit") { HCKit(sender, ticket); return true; }
        if (command == "list") { HCList(sender, ticket, player.GetPosition()); return true; }
        if (command == "snapshot")
        {
            int slot = m_Admins.PlainIds.Find(sender.GetPlainId());
            float now = GetGame().GetTickTime();
            if (!m_DebugEnabled) { HCReply(sender, ticket, command, false, "EnableDebugSnapshot-off; contributors-unavailable"); return false; }
            if (now < m_SnapshotAt[slot]) { HCReply(sender, ticket, command, false, "snapshot-cooldown=5s"); return false; }
            if (m_Capture) { HCReply(sender, ticket, command, false, "snapshot-queue-cap=1"); return false; }
            m_SnapshotAt[slot] = now + 5;
            m_Capture = new HCDebugSnapshot(0);
            m_CaptureSender = sender;
            m_CaptureTicket = ticket;
            HCReply(sender, ticket, command, true, "capture-queued; one-contributor-per-tick");
            return true;
        }
        string reason = "module-unavailable";
        bool ok = false;
        vector pos = player.GetPosition();
        HCInfectedModule infected = HCInfectedModule.Instance;
        HCEventModule events = HCEventModule.Get();
        HCCampModule camps = HCCampModule.Get();
        HCHoldouts holdouts = HCHoldouts.Get();
        if (command == "sitter")
        {
            if (!GetGame().ConfigIsExisting("CfgVehicles HC_ZmbM_Sitter")) { reason = "class-missing-HC_ZmbM_Sitter"; }
            else if (infected) { ok = infected.HCAdminSitter(player, reason); }
        }
        else if (command == "dormant") { reason = "InfectedVariety-fresh-spawn-skipped; no-shared-body-lease-or-dormant-spawn-policy"; }
        else if (command == "horde" && infected) { ok = infected.HCAdminHorde(pos, reason); }
        else if (command == "event" && events) { ok = events.HCAdminEvent(pos, reason); }
        else if (command == "scene") { ok = HCScenesModule.HCAdminScene(pos, reason); }
        else if (command == "camp" && camps) { ok = camps.HCAdminCamp(pos, m_Players, reason); }
        else if (command == "holdout" && holdouts) { ok = holdouts.HCAdminHoldout(pos, reason); }
        else if (command == "day") { ok = HCEscalationClock.HCAdminDay(value, reason); }
        else { ok = HCExtra(player, pos, command, value, reason); }
        HCReply(sender, ticket, command, ok, reason);
        return ok;
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running) { return; }
        if (!m_Pending && !m_Capture && !m_LootMap) { return; }
        m_Players.Clear();
        GetGame().GetPlayers(m_Players);
        if (m_Pending)
        {
            HCAdminRequest request = m_Pending;
            PlayerIdentity sender = m_PendingSender;
            m_Pending = null;
            m_PendingSender = null;
            HCDispatch(sender, request.Command, request.Value, request.Ticket);
        }
        if (m_Capture)
        {
            if (!HCAuthorized(m_CaptureSender) || !HCPlayer(m_CaptureSender)) { m_Capture = null; m_CaptureSender = null; }
            else if (m_Capture.HCCaptureNext())
            {
                HCAdminReply snapshot = HCAdminSnapshotWire.HCBuild(m_Capture, m_CaptureTicket);
                HCSend(m_CaptureSender, snapshot);
                m_Capture = null;
                m_CaptureSender = null;
            }
        }
        HCLootMapTick();
        m_Players.Clear();
    }

    override void OnStop()
    {
        if (m_Running) { DayZGame.Event_OnRPC.Remove(HCReceive); }
        m_Running = false;
        m_Pending = null;
        m_Capture = null;
        m_PendingSender = null;
        m_CaptureSender = null;
        m_Admins = null;
        m_Denied = null;
        m_CommandAt = null;
        m_SnapshotAt = null;
        m_Tickets = null;
        m_Identities = null;
        m_Players = null;
        m_LootMap = null;
        m_LootMapSender = null;
        m_LootMapTicket = 0;
        m_LootMapAfter = 0;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCAdminModule());
    }
}
