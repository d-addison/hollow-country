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
// #203 API-neutral server permission seam. No client UI/profile role data is trusted.
// Native evidence: scripts-1.30.164289/3_Game/Global/Game.c:1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnSystem.c:397 FileExist;
// 1_Core/proto/EnDebug.c:96 Print. No COT/Expansion engine call is guessed here.
// Optional COT binding lives in HCXCotPermissions.c; the base has no vendor types.
class HCAdminPermissionPort
{
    string HCProblem() { return "cot_permission_provider_unavailable"; }
    bool HCReady() { return false; }
    bool HCAllowed(PlayerIdentity sender, string permission) { return false; }
}

class HCAdminPermissionAdapter
{
    static const string PERMISSION = "HollowCountry.Admin";
    protected bool m_Running;
    protected bool m_Enabled;
    protected ref HCAdminPermissionPort m_Port;
    protected string m_Reason;
    protected float m_NextPortRefusalAt;
    protected int m_PortRefusals;
    int HCPortRefusals() { return m_PortRefusals; }
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    HCOperationalStatus HCGetOperationalStatus()
    {
        HCRefresh();
        return m_Status;
    }

    // Declared on the earliest link: optional addons supply a server-owned port.
    HCAdminPermissionPort HCDefaultPort() { return null; }

    void HCStart()
    {
        if (m_Running) { return; }
        m_Port = null;
        m_Running = GetGame() && GetGame().IsServer();
        m_Enabled = m_Running && !FileExist("$profile:HollowCountry/acceptance/COTAuthorization.disable");
        // Keep an unavailable default provider attached so live readiness can recover.
        if (m_Enabled) { m_Port = HCDefaultPort(); }
        if (m_Running) { Print(HCV2Admission.Line("COTAuthorization", m_Enabled, "203", false) + " runtime=PENDING"); }
        HCRefresh();
    }

    void HCStop()
    {
        m_Running = false;
        m_Enabled = false;
        m_Port = null;
        HCRefresh();
    }

    bool HCBind(HCAdminPermissionPort port)
    {
        if (!m_Running || !m_Enabled || !GetGame() || !GetGame().IsServer() || !port || !port.HCReady()) { return false; }
        // Never replace another live owner. It must explicitly unbind first.
        if (m_Port && m_Port != port) { return false; }
        m_Port = port;
        HCRefresh();
        return true;
    }

    void HCUnbind(HCAdminPermissionPort port)
    {
        if (!port || m_Port != port) { return; }
        m_Port = null;
        HCRefresh();
    }

    bool HCAllowed(PlayerIdentity sender)
    {
        if (!m_Running || !m_Enabled || !GetGame() || !GetGame().IsServer() || !m_Port) { return false; }
        if (!sender) { HCRefuse("IDENTITY_REQUIRED", true); return false; }
        if (!m_Port.HCReady()) { HCRefuse(m_Port.HCProblem(), true); return false; }
        if (!m_Port.HCAllowed(sender, HCAdminPermissionAdapter.PERMISSION))
        {
            HCRefuse(m_Port.HCProblem(), true);
            return false;
        }
        return true;
    }

    protected void HCRefuse(string reason, bool portRefusal = false)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (portRefusal)
        {
            // Count every refused check, even repeated or rate-limited failures.
            if (m_PortRefusals < 2147483647) { m_PortRefusals++; }
            // Ordinary authorization outcomes do not describe provider health.
            if (reason == "COT_PERMISSION_DENIED" || reason == "COT_PLAYER_MISSING" || reason == "IDENTITY_REQUIRED") { return; }
        }
        if (m_Reason == reason) { return; }
        // Bound not-ready/provider failures separately from readiness transitions.
        if (portRefusal)
        {
            float now = GetGame().GetTickTime();
            if (now < m_NextPortRefusalAt) { return; }
            m_NextPortRefusalAt = now + 60;
        }
        m_Reason = reason;
        // No peer identity or role contents; at most one port refusal per minute.
        Print("[HC Admin] COTAuthorization reason=" + reason + " runtime=PENDING");
    }

    void HCRefresh()
    {
        if (!GetGame() || !GetGame().IsServer())
        {
            m_Running = false;
            m_Enabled = false;
            m_Port = null;
        }
        string state = "off";
        string reason = "server_stopped";
        if (m_Running && !m_Enabled) { reason = "operator_opt_out"; }
        if (m_Running && m_Enabled)
        {
            state = "degraded";
            reason = "cot_permission_binding_missing";
            if (m_Port)
            {
                reason = "cot_permission_provider_unavailable";
                if (m_Port.HCReady()) { state = "ready"; reason = "server_permission_provider_bound_runtime_pending"; }
            }
        }
        m_Status.HCPublish(state, reason);
        HCRefuse(reason);
    }
}

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
    protected ref HCAdminPermissionAdapter m_Permissions;
    HCAdminPermissionAdapter HCPermissionAdapter() { return m_Permissions; }
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
    protected bool m_LootMapRootReady;
    // Native EnScript.c:857,902,917 map Clear/Set/Contains.
    protected ref map<string, bool> m_SeenAdmins = new map<string, bool>;
    protected bool m_OperatorControls;
    protected float m_DeniedOverflowAt;
    protected ref HCAdminLootMap m_LootMap;
    protected PlayerIdentity m_LootMapSender;
    protected int m_LootMapTicket;
    protected float m_LootMapAfter;
    // Running value of the cadence HCServer delivers to OnTick (ms, HCSmoothTickMs); sizes the lootmap ack deadline.
    protected int m_ObservedTickMs;
    // HC-1 status the core reads after OnStart (#160): every start refusal publishes
    // its reason here instead of returning silently.
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    override string GetName() { return "AdminMap"; }
    bool HCOperatorControls() { return m_OperatorControls; }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        // Core polling refreshes the adapter's derived lifecycle receipt too.
        if (m_Permissions) { m_Permissions.HCGetOperationalStatus(); }
        return m_Status;
    }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableAdminMap;
        if (!enabled) { m_Status.HCPublish("off", "module_not_enabled"); }
        return enabled;
    }

    // OnStart runs once per server start, so this one line per refusal is bounded.
    // Never prints an admin ID.
    protected void HCStartRefused(string reason)
    {
        m_Status.HCPublish("refused", reason);
        Print("[HC Admin] allowlist refused: reason=" + reason + "; admin map off; IDs withheld");
    }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || m_Running || !GetGame().IsServer()) { return; }
        if (!m_Printed)
        {
            Print(HCV2Admission.Line("AdminMap", true, "W6-123-133", false));
            m_Printed = true;
        }
        if (!HCV2ThreatStore<HCAdminAllowlist>.CanOpen(PATH)) { HCStartRefused("admin_allowlist_store_recovery_required"); return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCAdminAllowlist>.Load(PATH, 4096, m_Admins)) { HCStartRefused("admin_allowlist_load_failed"); return; }
        }
        else
        {
            m_Admins = new HCAdminAllowlist;
            if (!HCV2ThreatStore<HCAdminAllowlist>.Save(PATH, m_Admins, 4096)) { HCStartRefused("admin_allowlist_save_failed"); return; }
        }
        if (!m_Admins || !m_Admins.PlainIds) { HCStartRefused("admin_allowlist_missing_after_load"); return; }
        if (m_Admins.PlainIds.Count() > 32) { HCStartRefused("admin_allowlist_count_exceeds_32"); return; }
        m_SeenAdmins.Clear();
        for (int idIndex = 0; idIndex < m_Admins.PlainIds.Count(); idIndex++)
        {
            string plainId = m_Admins.PlainIds[idIndex];
            if (plainId == "" || plainId.Length() > 64 || m_SeenAdmins.Contains(plainId))
            {
                HCStartRefused("admin_allowlist_invalid_or_duplicate_entry");
                m_Admins = null;
                return;
            }
            m_SeenAdmins.Set(plainId, true);
        }
        m_Permissions = new HCAdminPermissionAdapter;
        m_Permissions.HCStart();
        m_Denied = new array<ref HCAdminDeniedPeer>;
        m_CommandAt = new array<float>;
        m_SnapshotAt = new array<float>;
        m_Tickets = new array<int>;
        m_Identities = new array<PlayerIdentity>;
        m_Players = new array<Man>;
        for (int slot = 0; slot < 32; slot++)
        {
            m_CommandAt.Insert(0);
            m_SnapshotAt.Insert(0);
            m_Tickets.Insert(0);
            m_Identities.Insert(null);
        }
        m_DebugEnabled = settings.EnableDebugSnapshot;
        HCAdminFixtures.HCConfigure(settings.EnableSmokeFixtures);
        // Profile directories are admitted once at module start, never per command.
        m_LootMapRootReady = false;
        if (m_DebugEnabled)
        {
            string root = "$profile:HollowCountry/debug";
            m_LootMapRootReady = FileExist(root) || MakeDirectory(root);
        }
        m_OperatorControls = !FileExist("$profile:HollowCountry/acceptance/AdminControls.disable");
        Print(HCV2Admission.Line("AdminControls", m_OperatorControls, "203", false) + " runtime=PENDING");
        m_Running = true;
        DayZGame.Event_OnRPC.Insert(HCReceive);
        m_Status.HCPublish("ready", "allowlist_loaded_native_acceptance_pending");
        Print("[HC Admin] allowlist count=" + m_Admins.PlainIds.Count().ToString() + "; native acceptance pending");
    }

    bool HCAuthorized(PlayerIdentity sender)
    {
        if (!m_Running || !sender || !m_Admins || !GetGame() || !GetGame().IsServer()) { return false; }
        if (m_Admins.PlainIds.Find(sender.GetPlainId()) >= 0) { return true; }
        return m_Permissions && m_Permissions.HCAllowed(sender);
    }

    // Existing fixed ingress/session arrays serve both authorization sources.
    // No COT id is appended to the durable allowlist. Revocation is checked on
    // every request, queued dispatch and delayed send; reconnect resets tickets.
    protected int HCAuthSlot(PlayerIdentity sender)
    {
        if (!HCAuthorized(sender)) { return -1; }
        int reusable = -1;
        for (int authIndex = 0; authIndex < m_Identities.Count(); authIndex++)
        {
            PlayerIdentity known = m_Identities[authIndex];
            if (known && known.GetPlainId() == sender.GetPlainId()) { return authIndex; }
            if (reusable < 0 && (!known || !HCAuthorized(known))) { reusable = authIndex; }
        }
        return reusable;
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
        if (command == "tp" || command == "tplist" || command == "tprefresh") { return HCCommand(sender, command, value, ticket); }
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
        if (!HCV2ThreatStore<HCAdminLootDocument>.CanOpen(HCAdminLootMap.PATH))
        {
            HCReply(sender, ticket, "lootmap", false, "lootmap_store_recovery_required"); return false;
        }
        if (!m_LootMapRootReady) { HCReply(sender, ticket, "lootmap", false, "lootmap_export_directory"); return false; }
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
        startLine += " min_rows_per_tick=" + limits.MinRowUnitsPerTick.ToString();
        startLine += " positions=0 query_cost=unmeasured runtime=PENDING";
        Print("" + startLine);
        // Immediate ack, the snapshot pattern: the client is freed at once, then the
        // one final marks RPC follows by this ticket (no automatic retries). If the
        // client session ends first the final reply is dropped client-side.
        // budget_ms is the server's own expected deadline (tick cap x the slower of the
        // configured and the last observed cadence); the client window derives from it.
        int budgetMs = HCAdminLootMap.HCBudgetMs(job.HCMaxTicks(), tickMs, m_ObservedTickMs);
        string ack = "started ticket=" + ticket.ToString() + " est_ticks=" + job.HCMaxTicks().ToString();
        ack += " cells=" + job.HCTotalCells().ToString() + " tick_ms=" + tickMs.ToString() + " budget_ms=" + budgetMs.ToString();
        ack += " final_reply=by_ticket; query_cost=unmeasured";
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
            // After the ack the client expects only the final reply by ticket, so the
            // failure is that final reply (Snapshot=true): it clears the client ticket
            // and shows the notice instead of being dropped as an unexpected reply.
            string failureLine = "[HC Admin] cmd=lootmap result=refused reason=lootmap_export_failed";
            Print("" + failureLine);
            HCAdminReply failure = new HCAdminReply;
            failure.Ticket = m_LootMapTicket;
            failure.Snapshot = true;
            failure.Notice = failureLine;
            HCSend(m_LootMapSender, failure);
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
        int slot = HCAuthSlot(sender);
        if (slot < 0) { HCRefused(sender); return; }
        if (m_Identities[slot] != sender)
        {
            m_Identities[slot] = sender;
            m_Tickets[slot] = 0;
            m_CommandAt[slot] = 0;
            m_SnapshotAt[slot] = 0;
        }
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
        if (command.IndexOf("fx_") == 0) { line += " fixture=1"; }
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
        string summary;
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { summary += "\n" + reply.Lines[lineIndex]; }
        if (summary != "") { Print("" + summary); }
        Print("[HC Admin] cmd=status result=ok reason=bounded-module-status");
        HCSend(sender, reply);
    }

    // Add-ons install their trusted server fixture provider through admin ownership.
    static bool HCRegisterFixtureProvider(HCAdminFixtureProvider provider)
    {
        return HCAdminFixtures.HCRegister(provider);
    }

    // Test-kit availability: one line per allowlisted command, read-only.
    void HCKit(PlayerIdentity sender, int ticket)
    {
        HCAdminReply reply = new HCAdminReply;
        reply.Ticket = ticket;
        reply.Notice = "Kit: available=0 names the reason. Runtime acceptance pending.";
        HCServer.Get().HCAdminKit(reply);
        HCAdminFixtures.HCFixtureKit(reply.Lines);
        string summary;
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { summary += "\n" + reply.Lines[lineIndex]; }
        if (summary != "") { Print("" + summary); }
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
        string summary;
        for (int lineIndex = 0; lineIndex < reply.Lines.Count(); lineIndex++) { summary += "\n" + reply.Lines[lineIndex]; }
        if (summary != "") { Print("" + summary); }
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

    // Catalog integration is owned by the lead. New commands use this same RPC,
    // authorization, replay protection and single-command core-tick queue.
    protected bool HCOperatorCommand(vector pos, string command, int value, out string reason)
    {
        if (command != "camptier" && command != "campvisit" && command != "campraid") { return false; }
        if (!m_OperatorControls) { reason = "AdminControls.disable"; return false; }
        HCCampModule camps = HCCampModule.Get();
        if (!camps) { reason = "camp-service-unavailable"; return false; }
        if (command == "camptier") { return camps.HCAdminTier(pos, value, reason); }
        if (command == "campvisit") { return camps.HCAdminArrival(pos, false, reason); }
        if (command == "campraid") { return camps.HCAdminArrival(pos, true, reason); }
        return false;
    }

    bool HCCommand(PlayerIdentity sender, string command, int value, int ticket)
    {
        PlayerBase player = HCPlayer(sender);
        if (!player) { HCReply(sender, ticket, command, false, "live-sender-unavailable-or-player-cap=32"); return false; }
        if (command.IndexOf("fx_") == 0)
        {
            string fixtureReason;
            bool fixtureOK = HCAdminFixtures.HCFixture(command, player.GetPosition(), fixtureReason);
            HCReply(sender, ticket, command, fixtureOK, fixtureReason);
            return fixtureOK;
        }
        if (command == "kit") { HCKit(sender, ticket); return true; }
        if (command == "list") { HCList(sender, ticket, player.GetPosition()); return true; }
        if (command == "snapshot")
        {
            int slot = HCAuthSlot(sender);
            if (slot < 0) { HCRefused(sender); return false; }
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
        else if (command == "dormant")
        {
            if (!m_OperatorControls) { reason = "AdminControls.disable"; }
            else if (infected) { ok = infected.HCAdminDormant(pos, reason); }
        }
        else if (command == "horde" && infected) { ok = infected.HCAdminHorde(pos, reason); }
        else if (command == "event" && events) { ok = events.HCAdminEvent(pos, reason); }
        else if (command == "scene") { ok = HCScenesModule.HCAdminScene(pos, reason); }
        else if (command == "camp" && camps) { ok = camps.HCAdminCamp(pos, m_Players, reason); }
        else if (command == "holdout" && holdouts) { ok = holdouts.HCAdminHoldout(pos, reason); }
        else if (command == "day") { ok = HCEscalationClock.HCAdminDay(value, reason); }
        else
        {
            ok = HCExtra(player, pos, command, value, reason);
            if (!ok && reason == "module-unavailable") { ok = HCOperatorCommand(pos, command, value, reason); }
        }
        HCReply(sender, ticket, command, ok, reason);
        return ok;
    }

    override void OnTick(float deltaTime)
    {
        // Cheap cadence note (HCServer passes the real elapsed seconds), kept while idle.
        // #194: a bounded running value (HCAdminLootMap.HCSmoothTickMs), not one sample.
        int sampleMs = deltaTime * 1000;
        m_ObservedTickMs = HCAdminLootMap.HCSmoothTickMs(m_ObservedTickMs, sampleMs);
        if (!m_Running) { return; }
        if (!m_Pending && !m_Capture && !m_LootMap) { return; }
        m_Players.Clear();
        HCReached.Mark("admin.request");
        HCModuleReadiness.HCUse("AdminMap", "request");
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
        if (m_Permissions) { m_Permissions.HCStop(); }
        m_Permissions = null;
        m_OperatorControls = false;
        HCAdminFixtures.HCConfigure(false);
        m_Status.HCPublish("off", "server_stopped");
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

// The pump owns scheduling only; catalogue cursors and row/time bounds stay here.
class HCStartupAdminTeleport : HCStartupOwner
{
    HCAdminTeleport Catalog;
    override bool HCNeedsWork() { return Catalog && Catalog.HCBuilding(); }
    override void HCSlice() { if (Catalog) { Catalog.HCStep(); } }
}
