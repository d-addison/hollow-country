// Two-level keys keep account/place boundaries exact without concatenation.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:866,917,926.
class HCGroupPendingIndex
{
    protected ref map<string, ref HCGroupStringIndex> m_Explorers = new map<string, ref HCGroupStringIndex>;
    void Add(string account, string place)
    {
        HCGroupStringIndex places = m_Explorers.Get(account);
        if (!places)
        {
            array<string> empty = new array<string>;
            places = new HCGroupStringIndex(empty);
            m_Explorers.Insert(account, places);
        }
        places.Add(place);
    }
    bool Has(string account, string place)
    {
        HCGroupStringIndex places = m_Explorers.Get(account);
        return places && places.Has(place);
    }
}

// Directed pair cache: bounded, short-lived, tied to both connection sessions.
class HCGroupLOSResult
{
    string SourceId;
    string RecipientId;
    string SourceSession;
    string RecipientSession;
    float At;
    bool Visible;
}

// Server-only, in-memory discovery delta. Never sent or persisted itself;
// FlushBatch applies it through the ordinary Clone/RecordVisit/Commit path.
class HCGroupPendingVisit
{
    string ExplorerId;
    ref HCGroupPlace Place;
    vector Actual;
}

class HCGroupClock
{
    protected static int s_LastUtc = 0;

    static bool LeapYear(int year)
    {
        if (year < 1) return false;
        if (year % 400 == 0) return true;
        if (year % 100 == 0) return false;
        return year % 4 == 0;
    }

    static int DaysInMonth(int year, int month)
    {
        if (year < 1 || month < 1 || month > 12) return -1;
        if (month == 2)
        {
            if (HCGroupClock.LeapYear(year)) return 29;
            return 28;
        }
        if (month == 4 || month == 6 || month == 9 || month == 11) return 30;
        return 31;
    }

    static int CalendarUtc(int year, int month, int day, int hour, int minute, int second)
    {
        // Full positive native int epoch; at most 68 year/11 month iterations.
        if (year < 1970 || year > 2038) return -1;
        int monthDays = HCGroupClock.DaysInMonth(year, month);
        if (day < 1 || day > monthDays) return -1;
        if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return -1;
        if (second < 0 || second > 59) return -1;
        int days = 0;
        int y = 1970;
        while (y < year)
        {
            days += 365;
            if (HCGroupClock.LeapYear(y)) days++;
            y++;
        }
        int m = 1;
        while (m < month)
        {
            days += HCGroupClock.DaysInMonth(year, m);
            m++;
        }
        days = days + day - 1;
        int daytime = hour * 3600 + minute * 60 + second;
        // int.MAX = 24855 full days + 11647 seconds. Reject before multiply
        // or add so 2038-01-19 03:14:08 cannot wrap into a valid timestamp.
        if (days > 24855) return -1;
        if (days == 24855 && daytime > 11647) return -1;
        return days * 86400 + daytime;
    }

    // Validated sample without a watermark. Callers own their clock policy.
    // Native UTC ports: 1_Core/proto/EnSystem.c:76,100 (1.30.164289).
    static int SampleUtc()
    {
        // Native UTC date and time are separate calls, not an atomic snapshot.
        // At most two attempts/six native calls; never sleep or mix dates.
        int attempt = 0;
        while (attempt < 2)
        {
            int year, month, day, hour, minute, second;
            int afterYear, afterMonth, afterDay;
            GetYearMonthDayUTC(year, month, day);
            GetHourMinuteSecondUTC(hour, minute, second);
            GetYearMonthDayUTC(afterYear, afterMonth, afterDay);
            int candidate = HCGroupClock.CalendarUtc(year, month, day, hour, minute, second);
            int beforeDate = HCGroupClock.CalendarUtc(year, month, day, 0, 0, 0);
            int afterDate = HCGroupClock.CalendarUtc(afterYear, afterMonth, afterDay, 0, 0, 0);
            // Epoch-zero midnight is a valid bracket date, not a usable sample.
            if (candidate < 1 || beforeDate < 0 || afterDate < 0) return -1;
            if (afterDate < beforeDate) return -1;
            if (afterDate != beforeDate)
            {
                attempt++;
                continue;
            }
            return candidate;
        }
        return -1;
    }

    static int Utc()
    {
        int candidate = HCGroupClock.SampleUtc();
        // Preserve group callers' monotonic clock and stop/clear policy.
        if (candidate < 1 || candidate < s_LastUtc) return -1;
        s_LastUtc = candidate;
        return candidate;
    }
}

class HCGroupPeer
{
    string Id;
    string Name;
    string Session;
    PlayerIdentity Identity;
    PlayerBase Player;
    int LastRequest;
    string LastPayload;
    ref HCGroupReply LastReply;
    int Sequence;
    int LastGroup;
    ref HCGroupEquipment Gear;
    float GearAt;
    float RateWindow;
    int RateCount;
}

// All authenticated identity comes from the engine sender. Client fields select
// targets only; neither group identity, ownership nor position comes from them.
// w29-debugmap #194: detached read-only row for the `group-pins` debug layer. Kind,
// position and expiry only: the pin id (which can embed a group id or a session
// token), the pin name (which can be a player-chosen or place text), the owning
// group and any player identity are withheld by the owner.
class HCDebugGroupPinRow
{
    string Kind = "pin";
    vector Position;
    int ExpiresUtc;
}

class HCGroupService
{
    protected static ref HCGroupService s_Instance;
    protected ref HCGroupSettings m_Config;
    protected ref HCGroupState m_State;
    protected ref HCGroupStore m_Store;
    protected ref HCGroupBatchSaveJob m_SaveJob;
    protected ref HCGroupState m_PendingState;

    int HCStepBatchSave()
    {
        if (!m_Healthy || !m_PendingState) { return HCSaveJob.STEP_FAILED; }
        int result = m_Store.SaveStep(m_PendingState);
        if (result == HCSaveJob.STEP_FAILED) { m_Healthy = false; Stop(); return result; }
        if (result == HCSaveJob.STEP_DONE)
        {
            // Routine discovery changes no ACL/invitations. Preserve current
            // ephemeral invitation expiry/disconnect changes made during IO.
            m_PendingState.Invitations = m_State.Invitations;
            m_State = m_PendingState;
            m_PendingState = null;
            Broadcast();
            HCPostBatchSave();
        }
        return result;
    }

    protected ref array<ref HCGroupPeer> m_Peers = new array<ref HCGroupPeer>();
    protected ref map<string, string> m_Names = new map<string, string>();
    protected bool m_Healthy;
    protected string m_Boot;
    protected int m_Serial;
    protected int m_LastUtc;
    protected float m_PositionTime;
    protected int m_LOSRays;
    protected int m_PeerCursor;
    protected int m_RoundCursor;
    protected bool m_FullSent;
    protected float m_DiscoveryBlockedUntil;
    protected ref array<ref HCGroupLOSResult> m_LOSCache = new array<ref HCGroupLOSResult>();
    protected float m_DiscoveryTime;
    protected int m_DiscoveryCursor;
    protected ref HCGroupPlaceCatalog m_Places;
    protected float m_GlobalWindow;
    protected int m_GlobalCount;
    protected ref array<ref HCGroupPendingVisit> m_PendingVisits = new array<ref HCGroupPendingVisit>();
    protected float m_BatchTime;
    protected string m_Refusal;

    static HCGroupService Get() { return s_Instance; }

    // w29-debugmap #194: coarse pin kind from the id prefix; the id itself is
    // never exported. Unknown prefixes read as a plain `pin`.
    string HCDebugPinKind(string pinId)
    {
        if (pinId.IndexOf("hc-ping:") == 0) { return "ping"; }
        if (pinId.IndexOf("hc-death:") == 0) { return "death"; }
        if (pinId.IndexOf("hc-lead:") == 0) { return "lead"; }
        if (pinId.IndexOf("hc-found:") == 0) { return "trail"; }
        return "pin";
    }

    // Count the current bounded group catalogue without collecting any pins.
    int HCDebugPinGroupCount()
    {
        if (!m_Healthy || !HCGroupPins.Get() || !m_State || !m_Config) { return 0; }
        int count = m_State.Groups.Count();
        if (count > m_Config.MaxGroups) { count = m_Config.MaxGroups; }
        return count;
    }

    // Cursor is a group offset, groupCap bounds Collect calls per invocation.
    // Return the TRUE PAGE total even when output is already full. Collect's
    // producers are independently bounded (90 pings, 256 death rows, 5 leads,
    // 20 shelter entries); int.MAX prevents the display cap truncating counts.
    // Native scripts-1.30.164289: 1_Core/proto/EnConvert.c:27 int.MAX.
    // Detached anonymous rows only; no save/broadcast. Collect retains its
    // ordinary expired-death pruning. Catalogue edits during a sweep may shift
    // offsets; this is a rolling diagnostic sample, never an atomic world view.
    int HCDebugPins(int cursor, int groupCap, int cap, array<ref HCDebugGroupPinRow> output)
    {
        HCGroupPins pins = HCGroupPins.Get();
        if (cursor < 0 || groupCap < 1 || cap < 1 || !output || !pins) { return 0; }
        int scan = HCDebugPinGroupCount();
        int total = 0;
        int visited = 0;
        for (int groupIndex = cursor; groupIndex < scan; groupIndex++)
        {
            if (visited >= groupCap) { break; }
            visited++;
            array<ref HCGroupPlace> collected = new array<ref HCGroupPlace>;
            pins.Collect(m_State.Groups[groupIndex], int.MAX, collected);
            total += collected.Count();
            for (int pinIndex = 0; pinIndex < collected.Count(); pinIndex++)
            {
                if (output.Count() >= cap) { break; }
                HCDebugGroupPinRow row = new HCDebugGroupPinRow;
                row.Kind = HCDebugPinKind(collected[pinIndex].Id);
                row.Position = collected[pinIndex].Position;
                row.ExpiresUtc = collected[pinIndex].HCPinExpiresUtc;
                output.Insert(row);
            }
        }
        return total;
    }

    // Last Start/Admit refusal reason; the log line prints once per reason change,
    // so a request flood or a retry cannot grow the log. No player identity.
    string Refusal() { return m_Refusal; }
    bool HCRefuse(string reason)
    {
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Groups] refused reason=" + reason);
        }
        return false;
    }
    string HCStartBlock(HCGroupSettings config)
    {
        if (!GetGame().IsServer()) { return "not_server"; }
        if (!HCGroupRules.SettingsValid(config)) { return "settings_invalid"; }
        if (!config.Enabled) { return "disabled"; }
        if (s_Instance) { return "already_started"; }
        return "";
    }

    bool Start(HCGroupSettings config)
    {
        string blocked = HCStartBlock(config);
        if (blocked != "") { return HCRefuse(blocked); }
        m_Config = config;
        if (config.DiscoveryLayer)
        {
            m_Places = HCGroupPlaces.Load();
            if (!m_Places)
            {
                Print("[HC Groups] invalid or over-budget places catalog; start refused");
                return false;
            }
        }
        m_LastUtc = HCGroupClock.Utc();
        float worldSize = GetGame().GetWorld().GetWorldSize();
        if (m_LastUtc < 1) { return HCRefuse("utc_unavailable"); }
        if (worldSize < 1 || worldSize > 50000) { return HCRefuse("world_size_invalid"); }
        m_Store = new HCGroupStore;
        if (!m_Store.Open(config, m_State)) { return HCRefuse("store_unavailable"); }
        if (!HCGroupRules.ClockAllows(m_State, m_LastUtc))
        {
            Print("[HC Groups] startup refused: UTC precedes last committed mutation; state preserved");
            return false;
        }
        if (m_State.LastMutationUtc == 0)
            Print("[HC Groups] no durable UTC watermark yet; next mutation will establish it");
        foreach (HCGroupRecord group : m_State.Groups)
        {
            foreach (HCGroupMarker marker : group.Markers)
            {
                if (marker.Position[0] > worldSize || marker.Position[2] > worldSize) { return HCRefuse("saved_marker_outside_world"); }
            }
        }
        // Fresh anti-stale receipt, not a credential: authority is sender.GetId.
        m_Boot = m_LastUtc.ToString() + "-" + Math.RandomIntInclusive(1, 1000000000).ToString();
        m_Healthy = true;
        m_SaveJob = new HCGroupBatchSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        s_Instance = this;
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        if (players.Count() > 90) { Stop(); return false; }
        foreach (Man man : players)
        {
            PlayerBase player = PlayerBase.Cast(man);
            if (player && player.GetIdentity()) Connected(player.GetIdentity(), player);
        }
        m_Refusal = "";
        return true;
    }

    HCGroupPeer Peer(string uid)
    {
        foreach (HCGroupPeer peer : m_Peers)
        {
            if (peer.Id == uid) return peer;
        }
        return null;
    }

    bool Live(HCGroupPeer peer)
    {
        return peer && peer.Identity && peer.Player && HCPlayerIdentity.Same(peer.Player.GetIdentity(), peer.Identity);
    }

    void Connected(PlayerIdentity identity, PlayerBase player)
    {
        if (!m_Healthy || !identity || !player || !HCPlayerIdentity.Same(player.GetIdentity(), identity)) return;
        string uid = identity.GetId();
        if (!HCGroupRules.TextValid(uid, 128, false)) return;
        HCGroupPeer previous = Peer(uid);
        if (previous) m_Peers.Remove(m_Peers.Find(previous));
        if (m_Peers.Count() >= 90 || m_Serial >= 1000000000) return;
        HCGroupPeer peer = new HCGroupPeer;
        peer.Id = uid;
        peer.Identity = identity;
        peer.Player = player;
        peer.Name = identity.GetName();
        if (!HCGroupRules.TextValid(peer.Name, 64, false)) peer.Name = "Survivor";
        m_Serial++;
        peer.Session = m_Boot + "-" + m_Serial.ToString();
        if (m_Names.Count() >= 180) m_Names.Clear();
        m_Names.Set(uid, peer.Name);
        m_Peers.Insert(peer);
        SendSnapshot(peer, HCGroupSnapshotKind.FULL, 0);
        Broadcast();
    }

    // Called at the disconnect event BEFORE native delayed body logout. The
    // body may remain in-world; it is no longer a live position source/recipient.
    void Disconnected(PlayerIdentity identity)
    {
        if (!identity) return;
        HCGroupPeer peer = Peer(identity.GetId());
        // A cleared weak identity still belongs to this id-keyed disconnect cleanup.
        if (!peer || (peer.Identity && !HCPlayerIdentity.Same(peer.Identity, identity))) return;
        // Persist batched discovery while the leaving explorer is still live.
        if (m_Healthy && FlushBatch() == HCGroupCode.STORAGE) { Stop(); return; }
        m_Peers.Remove(m_Peers.Find(peer));
        HCGroupRules.DropInvites(m_State, 0, peer.Id);
        peer.Identity = null;
        peer.Player = null;
        Broadcast();
    }

    void Stop()
    {
        // Best-effort final discovery flush. FlushBatch never calls Stop, and
        // a failed or faulted Commit leaves the last durable revision intact.
        if (m_SaveJob && m_Healthy)
        {
            if (!HCSaveScheduler.HCFlush(m_SaveJob)) { m_Healthy = false; }
            if (m_Healthy && m_PendingVisits.Count() > 0)
            {
                FlushBatch();
                if (!HCSaveScheduler.HCFlush(m_SaveJob)) { m_Healthy = false; }
            }
        }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        if (m_SaveJob) { m_SaveJob.Owner = null; }
        m_SaveJob = null;
        m_Healthy = false;
        foreach (HCGroupPeer peer : m_Peers) SendSnapshot(peer, HCGroupSnapshotKind.CLEAR, 0);
        m_Peers.Clear();
        if (s_Instance == this) s_Instance = null;
    }

    void Reply(HCGroupPeer peer, int requestId, int code, bool cache = false)
    {
        if (!Live(peer)) return;
        if (!HCGroupRules.MutationIdValid(peer.LastRequest)) return;
        HCGroupReply reply = new HCGroupReply;
        reply.RequestId = requestId;
        reply.LastMutationId = peer.LastRequest;
        reply.Code = code;
        reply.Session = peer.Session;
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (group) reply.Revision = group.Revision;
        // Only the result of a newly consumed request may replace its receipt.
        // A mismatched replay/session/invalid packet cannot poison the cache.
        if (cache) peer.LastReply = reply;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(reply);
        rpc.Send(null, HCGroupProtocol.RPC_REPLY, true, peer.Identity);
    }

    bool Admit(HCGroupPeer peer)
    {
        float now = GetGame().GetTickTime();
        if (!(now >= 0.0 && now <= 2147483647.0)) { return HCRefuse("clock_invalid"); }
        if (now < peer.RateWindow || now < m_GlobalWindow) { return HCRefuse("clock_rollback"); }
        if (now - peer.RateWindow >= 1.0) { peer.RateWindow = now; peer.RateCount = 0; }
        if (now - m_GlobalWindow >= 1.0) { m_GlobalWindow = now; m_GlobalCount = 0; }
        if (peer.RateCount >= m_Config.MaxRequestsPerSecond || m_GlobalCount >= m_Config.MaxRequestsPerSecond * 2) { return HCRefuse("rate_limited"); }
        peer.RateCount++;
        m_GlobalCount++;
        m_Refusal = "";
        return true;
    }

    // Same-module extension hook; base declaration keeps modded-link resolution safe.
    int HCLookPing(HCGroupPeer peer, HCGroupRequest request) { return HCGroupCode.DISABLED; }

    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (!m_Healthy || !GetGame().IsServer() || rpcType != HCGroupProtocol.RPC_REQUEST || target || !sender) return;
        string uid = sender.GetId();
        HCGroupPeer peer = Peer(uid);
        if (!peer)
        {
            Connected(sender, PlayerBase.Cast(sender.GetPlayer()));
            peer = Peer(uid);
        }
        if (!Live(peer) || !HCPlayerIdentity.Same(peer.Identity, sender)) return;
        // Over-budget packets must not allocate/serialize a reliable reply.
        if (!Admit(peer)) { return; }
        HCGroupRequest request;
        if (!ctx || !ctx.Read(request) || !request) { Reply(peer, 0, HCGroupCode.INVALID); return; }
        if (request.Version != HCGroupProtocol.VERSION || request.Session.Length() > 80 || request.Name.Length() > 64 || request.Note.Length() > 512 || request.TargetId.Length() > 128 || !HCGroupRules.MutationIdValid(request.RequestId))
        { Reply(peer, request.RequestId, HCGroupCode.INVALID); return; }
        if (request.Op == HCGroupOp.SYNC)
        {
            SendSnapshot(peer, HCGroupSnapshotKind.FULL, request.RequestId);
            return;
        }
        if (request.Session != peer.Session || request.RequestId < 1)
        { Reply(peer, request.RequestId, HCGroupCode.SESSION); return; }
        string payload;
        string error;
        if (!JsonFileLoader<HCGroupRequest>.MakeData(request, payload, error) || payload.Length() > 4096)
        { Reply(peer, request.RequestId, HCGroupCode.INVALID); return; }
        if (request.RequestId == peer.LastRequest)
        {
            if (payload != peer.LastPayload || !peer.LastReply)
            { Reply(peer, request.RequestId, HCGroupCode.CONFLICT); return; }
            ScriptRPC repeat = new ScriptRPC;
            repeat.Write(peer.LastReply);
            repeat.Send(null, HCGroupProtocol.RPC_REPLY, true, peer.Identity);
            return;
        }
        if (request.RequestId != peer.LastRequest + 1)
        { Reply(peer, request.RequestId, HCGroupCode.CONFLICT); return; }
        peer.LastRequest = request.RequestId;
        peer.LastPayload = payload;
        peer.LastReply = null;
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc) { Stop(); return; }
        m_LastUtc = now;
        // #131 uses the same authenticated nonce/session/replay envelope.
        // It never clones or commits inventory/group state; position is server-read.
        if (request.Op == HCGroupOp.TEAM_PING)
        {
            int pingResult = HCGroupCode.DISABLED;
            if (request.Role == HCGroupPingWire.LOOK) { pingResult = HCLookPing(peer, request); }
            else if (HCTeamPingModule.Get()) { pingResult = HCTeamPingModule.Get().HCReceive(peer, request.Role); }
            Reply(peer, request.RequestId, pingResult, true);
            return;
        }
        if (request.Op == HCGroupOp.INVITE && !Live(Peer(request.TargetId)))
        { Reply(peer, request.RequestId, HCGroupCode.NOT_FOUND, true); return; }
        if ((request.Op == HCGroupOp.MARKER_CREATE || request.Op == HCGroupOp.MARKER_UPDATE) && (request.Position[0] > GetGame().GetWorld().GetWorldSize() || request.Position[2] > GetGame().GetWorld().GetWorldSize()))
        { Reply(peer, request.RequestId, HCGroupCode.INVALID, true); return; }
        int result = HCApplyMutation(request, uid, now);
        if (result == HCGroupCode.STORAGE)
        { Reply(peer, request.RequestId, HCGroupCode.STORAGE, true); Stop(); return; }
        Reply(peer, request.RequestId, result, true);
        if (result == HCGroupCode.OK) Broadcast();
        if (result == HCGroupCode.CONFLICT) SendSnapshot(peer, HCGroupSnapshotKind.FULL, request.RequestId);
    }

    // Shared transaction for map requests and the native nearby interaction.
    // Every path retains INVITE's ACL, group/invite caps, expiry and persistence.
    protected int HCApplyMutation(HCGroupRequest request, string uid, int now)
    {
        // The staged candidate must publish before another revision is cloned.
        if (m_PendingState) { return HCGroupCode.CONFLICT; }
        HCGroupState candidate;
        if (!Clone(candidate)) return HCGroupCode.STORAGE;
        HCGroupRules.ExpireMarkers(candidate, now, false);
        int result = HCGroupRules.Apply(candidate, m_Config, request, uid, now);
        if (result == HCGroupCode.OK) result = Commit(candidate);
        return result;
    }

    // Native 1.30.164289: 3_Game/Entities/Man.c:21 GetIdentity;
    // gameplay.c:368 GetId; Entities/Object.c:287,517 GetPosition/IsAlive;
    // 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious.
    int HCInviteNearby(PlayerBase actor, PlayerBase target)
    {
        if (!m_Healthy || !GetGame().IsServer()) return HCGroupCode.DISABLED;
        if (!actor || !actor.GetIdentity() || !actor.IsAlive() || actor.IsUnconscious()) return HCGroupCode.DENIED;
        HCGroupPeer peer = Peer(actor.GetIdentity().GetId());
        if (!Live(peer) || peer.Player != actor || !HCPlayerIdentity.Same(peer.Identity, actor.GetIdentity())) return HCGroupCode.DENIED;
        if (!Admit(peer)) return HCGroupCode.RATE;
        if (!target || target == actor || !target.IsAlive() || !target.GetIdentity()) return HCGroupCode.NOT_FOUND;
        HCGroupPeer invitee = Peer(target.GetIdentity().GetId());
        if (!Live(invitee) || invitee.Player != target || !HCPlayerIdentity.Same(invitee.Identity, target.GetIdentity())) return HCGroupCode.NOT_FOUND;
        vector reach = target.GetPosition() - actor.GetPosition();
        if (reach[0] * reach[0] + reach[1] * reach[1] + reach[2] * reach[2] > 9.0) return HCGroupCode.DENIED;
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group) return HCGroupCode.DENIED;
        int now = HCGroupClock.Utc();
        if (now < m_LastUtc) { Stop(); return HCGroupCode.DISABLED; }
        m_LastUtc = now;
        HCGroupRequest request = new HCGroupRequest;
        request.Op = HCGroupOp.INVITE;
        request.TargetId = invitee.Id;
        request.ExpectedRevision = group.Revision;
        int result = HCApplyMutation(request, peer.Id, now);
        if (result == HCGroupCode.STORAGE) Stop();
        if (result == HCGroupCode.OK) Broadcast();
        return result;
    }

    bool Clone(out HCGroupState candidate)
    {
        string text;
        string error;
        return JsonFileLoader<HCGroupState>.MakeData(m_State, text, error) && text.Length() <= m_Config.MaxStoreBytes && JsonFileLoader<HCGroupState>.LoadData(text, candidate, error) && candidate;
    }

    int Commit(HCGroupState candidate)
    {
        if (m_PendingState) { return HCGroupCode.CONFLICT; }
        int result = HCPrepareCommit(candidate);
        if (result != HCGroupCode.OK) { return result; }
        // Authenticated action durability barrier; routine discovery never calls it.
        if (!m_Store.Save(candidate)) { return HCGroupCode.STORAGE; }
        m_State = candidate;
        HCModuleReadiness.HCUse("Groups", "group_mutated");
        return HCGroupCode.OK;
    }

    void HCPostBatchSave() {}

    int HCQueueCommit(HCGroupState candidate)
    {
        if (m_PendingState || !m_SaveJob) { return HCGroupCode.CONFLICT; }
        int result = HCPrepareCommit(candidate);
        if (result != HCGroupCode.OK) { return result; }
        m_PendingState = candidate;
        m_SaveJob.HCDirty = true;
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
        return HCGroupCode.OK; // accepted, publication is HCStepBatchSave's responsibility
    }

    protected int HCPrepareCommit(HCGroupState candidate)
    {
        if (!candidate || !HCGroupRules.ClockAllows(m_State, m_LastUtc)) return HCGroupCode.STORAGE;
        EvictExplorers(candidate, false);
        candidate.LastMutationUtc = m_LastUtc;
        candidate.Revision = m_State.Revision + 1;
        if (!HCGroupRules.StateValid(candidate, m_Config, GetGame().GetWorldName())) return HCGroupCode.STORAGE;
        // Quota is admission control, not a damaged store. This check happens
        // before Save can create an intent; rejected clones never replace live
        // state. Include ephemeral invitations so Clone stays within its bound.
        string text;
        string error;
        bool serialized = JsonFileLoader<HCGroupState>.MakeData(candidate, text, error);
        if (!serialized) return HCGroupCode.STORAGE;
        int evicted = 0;
        while (text.Length() > m_Config.MaxStoreBytes && evicted < m_Config.MaxExplorers)
        {
            if (!EvictExplorers(candidate, true)) return HCGroupCode.LIMIT;
            evicted++;
            bool resized = JsonFileLoader<HCGroupState>.MakeData(candidate, text, error);
            if (!resized) return HCGroupCode.STORAGE;
        }
        if (text.Length() > m_Config.MaxStoreBytes) return HCGroupCode.LIMIT;
        return HCGroupCode.OK;
    }

    bool HasGPS(HCGroupPeer peer)
    {
        if (!m_Config.RequireGPS) return true;
        if (!Live(peer) || !peer.Player.GetMapNavigationBehaviour()) return false;
        int navigation = peer.Player.GetMapNavigationBehaviour().GetNavigationType();
        return (navigation & EMapNavigationType.GPS) != 0 || (navigation & EMapNavigationType.ALL) != 0;
    }

    bool VisibilityAllows(HCGroupPeer source, HCGroupPeer recipient)
    {
        if (source.Id == recipient.Id) return true;
        if (source.Player.IsUnconscious() || recipient.Player.IsUnconscious()) return false;
        if (m_Config.RequireRadio)
        {
            HCGroupEquipment sourceGear = Equipment(source);
            HCGroupEquipment recipientGear = Equipment(recipient);
            if (!HCGroupVisibility.RadioMatches(sourceGear, recipientGear)) return false;
        }
        if (m_Config.RequireLOS)
        {
            return LOSAllows(source, recipient);
        }
        return true;
    }

    HCGroupEquipment Equipment(HCGroupPeer peer)
    {
        float now = GetGame().GetTickTime();
        if (!peer.Gear || now < peer.GearAt || now - peer.GearAt >= 1.0)
        {
            peer.Gear = HCGroupEquipment.Read(peer.Player);
            peer.GearAt = now;
        }
        return peer.Gear;
    }

    bool LOSAllows(HCGroupPeer source, HCGroupPeer recipient)
    {
        float now = GetGame().GetTickTime();
        foreach (HCGroupLOSResult cached : m_LOSCache)
        {
            if (cached.SourceId == source.Id && cached.RecipientId == recipient.Id && cached.SourceSession == source.Session && cached.RecipientSession == recipient.Session && now >= cached.At && now - cached.At < 1.0)
                return cached.Visible;
        }
        if (m_LOSRays >= m_Config.MaxLOSRaysPerTick) return false;
        m_LOSRays++;
        HCGroupLOSResult verdict = new HCGroupLOSResult;
        verdict.SourceId = source.Id;
        verdict.RecipientId = recipient.Id;
        verdict.SourceSession = source.Session;
        verdict.RecipientSession = recipient.Session;
        verdict.At = now;
        verdict.Visible = HCGroupVisibility.HasLOS(source.Player, recipient.Player);
        if (m_LOSCache.Count() >= 256) m_LOSCache.RemoveOrdered(0);
        m_LOSCache.Insert(verdict);
        return verdict.Visible;
    }

    void BeginVisibilityTick()
    {
        m_LOSRays = 0;
        m_FullSent = false;
        if (m_Peers.Count() > 0) m_PeerCursor = (m_PeerCursor + 1) % m_Peers.Count();
        foreach (HCGroupPeer peer : m_Peers) peer.Gear = null;
        float now = GetGame().GetTickTime();
        for (int index = m_LOSCache.Count() - 1; index >= 0; index--)
        {
            HCGroupLOSResult cached = m_LOSCache.Get(index);
            if (now < cached.At || now - cached.At >= 1.0) m_LOSCache.Remove(index);
        }
    }

    void SendRound(int kind)
    {
        // Advance emitted rounds independently of Tick cadence: e.g. an
        // eight-peer list sampled every second Tick must not visit only evens.
        if (m_Peers.Count() > 0)
        {
            m_PeerCursor = m_RoundCursor % m_Peers.Count();
            m_RoundCursor = (m_RoundCursor + 1) % m_Peers.Count();
        }
        int sent = 0;
        while (sent < m_Peers.Count())
        {
            HCGroupPeer peer = m_Peers.Get((m_PeerCursor + sent) % m_Peers.Count());
            sent++;
            if (kind == HCGroupSnapshotKind.FULL || HCGroupRules.FindGroup(m_State, peer.Id)) SendSnapshot(peer, kind, 0);
        }
    }

    // Enqueue only: no Clone/Commit on the discovery cadence. FlushBatch
    // persists the bounded queue at most once per 60 s, on disconnect and Stop.
    void Discover()
    {
        if (!m_Config.DiscoveryLayer || !m_Places || m_Peers.Count() == 0) return;
        float now = GetGame().GetTickTime();
        if (now < m_DiscoveryBlockedUntil) return;
        HCGroupPendingIndex queuedVisits = new HCGroupPendingIndex;
        foreach (HCGroupPendingVisit pending : m_PendingVisits)
        {
            queuedVisits.Add(pending.ExplorerId, pending.Place.Id);
        }
        int examined = 0;
        while (examined < 6 && examined < m_Peers.Count())
        {
            if (m_DiscoveryCursor >= m_Peers.Count()) m_DiscoveryCursor = 0;
            HCGroupPeer explorer = m_Peers.Get(m_DiscoveryCursor);
            m_DiscoveryCursor++;
            examined++;
            if (!Live(explorer) || !explorer.Player.IsAlive() || explorer.Player.IsUnconscious()) continue;
            vector actual = explorer.Player.GetPosition();
            foreach (HCGroupPlace place : m_Places.Places)
            {
                float dx = actual[0] - place.Position[0];
                float dz = actual[2] - place.Position[2];
                if (dx * dx + dz * dz > place.Radius * place.Radius) continue;
                if (HCGroupRules.HasVisit(m_State, explorer.Id, place.Id)) continue;
                // Full queue: skip; the visit is observed again after a flush.
                if (m_PendingVisits.Count() >= 256) continue;
                if (queuedVisits.Has(explorer.Id, place.Id)) continue;
                HCGroupPendingVisit visit = new HCGroupPendingVisit;
                visit.ExplorerId = explorer.Id;
                visit.Place = place;
                visit.Actual = actual;
                m_PendingVisits.Insert(visit);
                queuedVisits.Add(explorer.Id, place.Id);
            }
        }
    }

    // One Clone and one Commit for every queued visit plus marker expiry.
    // A crash loses only this unflushed window; the durable revision chain
    // is untouched. NOT_FOUND means nothing to write. Never calls Stop.
    int FlushBatch()
    {
        if (m_PendingState) { return HCGroupCode.NOT_FOUND; }
        m_BatchTime = 0;
        if (m_PendingVisits.Count() == 0 && !HCGroupRules.MarkersExpired(m_State, m_LastUtc)) return HCGroupCode.NOT_FOUND;
        HCGroupState candidate;
        if (!Clone(candidate))
        {
            m_PendingVisits.Clear();
            return HCGroupCode.STORAGE;
        }
        bool changed = HCGroupRules.ExpireMarkers(candidate, m_LastUtc, true);
        EvictExplorers(candidate, false);
        foreach (HCGroupPendingVisit visit : m_PendingVisits)
        {
            if (candidate.Explorers.Count() >= m_Config.MaxExplorers && !HCGroupRules.HasExplorer(candidate, visit.ExplorerId)) EvictExplorers(candidate, true);
            if (HCGroupRules.RecordVisit(candidate, m_Config, visit.ExplorerId, visit.Place, visit.Actual)) changed = true;
        }
        m_PendingVisits.Clear();
        if (!changed) return HCGroupCode.NOT_FOUND;
        foreach (HCGroupExplorer observer : candidate.Explorers)
        {
            if (Live(Peer(observer.Id))) observer.LastSeenUtc = m_LastUtc;
        }
        int result = HCQueueCommit(candidate);
        if (result == HCGroupCode.OK) { return HCGroupCode.NOT_FOUND; }
        if (result == HCGroupCode.LIMIT) m_DiscoveryBlockedUntil = GetGame().GetTickTime() + 60.0;
        return result;
    }

    // Group members and connected accounts retain their journals. Expire
    // ungrouped/offline accounts after 30 days; pressure evicts oldest first.
    bool EvictExplorers(HCGroupState candidate, bool pressure)
    {
        int oldest = -1;
        int oldestUtc = 2147483647;
        bool changed = false;
        for (int index = candidate.Explorers.Count() - 1; index >= 0; index--)
        {
            HCGroupExplorer explorer = candidate.Explorers.Get(index);
            if (HCGroupRules.FindGroup(candidate, explorer.Id) || Live(Peer(explorer.Id))) continue;
            if (!pressure && m_LastUtc - explorer.LastSeenUtc >= 2592000)
            {
                candidate.Explorers.Remove(index);
                changed = true;
            }
            if (pressure && explorer.LastSeenUtc <= oldestUtc)
            {
                oldestUtc = explorer.LastSeenUtc;
                oldest = index;
            }
        }
        if (pressure && oldest >= 0)
        {
            candidate.Explorers.Remove(oldest);
            changed = true;
        }
        return changed;
    }

    // Coarse quarter bands: zero is empty, 1..4 are the occupied quarters.
    static int HCStatusBand(float value, float maximum)
    {
        if (!(maximum > 0) || !(value >= 0)) { return -1; }
        if (value <= 0) { return 0; }
        if (value <= maximum * 0.25) { return 1; }
        if (value <= maximum * 0.5) { return 2; }
        if (value <= maximum * 0.75) { return 3; }
        return 4;
    }

    HCGroupMember Member(string uid, HCGroupPeer recipient, bool position)
    {
        HCGroupMember member = new HCGroupMember;
        member.Id = uid;
        member.Name = m_Names.Get(uid);
        if (member.Name == "") member.Name = "Offline member";
        HCGroupPeer source = Peer(uid);
        member.Online = Live(source);
        // Candidates disclose invitation selection/availability only. The
        // default Alive=false means undisclosed here, not a death report.
        if (!position) return member;
        member.Alive = member.Online && source.Player.IsAlive();
        if (position && member.Alive && Live(recipient) && recipient.Player.IsAlive() && HasGPS(source) && HasGPS(recipient) && (m_Config.MapIcons || m_Config.WorldIcons))
        {
            vector actual = source.Player.GetPosition();
            vector viewer = recipient.Player.GetPosition();
            float dx = actual[0] - viewer[0];
            float dy = actual[1] - viewer[1];
            float dz = actual[2] - viewer[2];
            if (HCGroupRules.PositionValid(actual) && (m_Config.MapIcons || dx * dx + dy * dy + dz * dz <= m_Config.MaxIconDistance * m_Config.MaxIconDistance) && VisibilityAllows(source, recipient))
            {
                member.Position = actual;
                member.HasPosition = true;
                member.SampleUtc = m_LastUtc;
                // Native 1.30.164289: 3_Game/Entities/Object.c:994,1008 health/max;
                // 4_World/Entities/ManBase/PlayerBase.c:2973,3925 bleeding/unconscious;
                // 4_World/Classes/BleedingSources/BleedingSourcesManagerBase.c:321 count.
                member.HealthBand = HCStatusBand(source.Player.GetHealth("", "Health"), source.Player.GetMaxHealth("", "Health"));
                member.BloodBand = HCStatusBand(source.Player.GetHealth("", "Blood"), source.Player.GetMaxHealth("", "Blood"));
                BleedingSourcesManagerServer bleeding = source.Player.GetBleedingManagerServer();
                member.Bleeding = bleeding && bleeding.GetBleedingSourcesCount() > 0;
                member.Unconscious = source.Player.IsUnconscious();
            }
        }
        return member;
    }

    void SendSnapshot(HCGroupPeer peer, int kind, int requestId)
    {
        if (!Live(peer) || peer.Sequence >= 1000000000) return;
        if (!HCGroupRules.MutationIdValid(peer.LastRequest)) return;
        HCGroupSnapshot snapshot = new HCGroupSnapshot;
        snapshot.Settings = m_Config;
        snapshot.Enabled = m_Healthy;
        snapshot.Kind = kind;
        snapshot.RequestId = requestId;
        snapshot.LastMutationId = peer.LastRequest;
        snapshot.Session = peer.Session;
        peer.Sequence++;
        snapshot.Sequence = peer.Sequence;
        HCGroupRecord group;
        if (m_Healthy) group = HCGroupRules.FindGroup(m_State, peer.Id);
        if (!group && peer.LastGroup != 0) snapshot.Kind = HCGroupSnapshotKind.CLEAR;
        if (group && kind != HCGroupSnapshotKind.CLEAR)
        {
            snapshot.GroupId = group.Id;
            snapshot.Revision = group.Revision;
            snapshot.Epoch = group.Epoch;
            snapshot.Name = group.Name;
            snapshot.OwnerId = group.OwnerId;
            foreach (string uid : group.Members)
            {
                HCGroupMember rosterMember = Member(uid, peer, true);
                rosterMember.Role = HCGroupRules.Role(group, uid);
                snapshot.Members.Insert(rosterMember);
            }
            if (kind == HCGroupSnapshotKind.FULL)
            {
                foreach (HCGroupMarker marker : group.Markers)
                {
                    if (marker.ExpiresUtc == 0 || marker.ExpiresUtc > m_LastUtc) snapshot.Markers.Insert(marker);
                }
            }
        }
        if (m_Healthy && kind != HCGroupSnapshotKind.POSITIONS)
        {
            foreach (HCGroupPeer candidate : m_Peers)
            {
                if (Live(candidate) && candidate.Id != peer.Id) snapshot.Candidates.Insert(Member(candidate.Id, peer, false));
            }
            foreach (HCGroupInvitation invitation : m_State.Invitations)
            {
                if (invitation.InviteeId == peer.Id && invitation.ExpiresUtc > m_LastUtc) snapshot.Invitations.Insert(invitation);
            }
        }
        if (m_Healthy && kind == HCGroupSnapshotKind.FULL && peer.Player.IsAlive())
            snapshot.Places = HCGroupRules.KnownPlaces(m_State, m_Config, peer.Id, m_Places);
        peer.LastGroup = snapshot.GroupId;
        ScriptRPC rpc = new ScriptRPC;
        rpc.Write(snapshot);
        rpc.Send(null, HCGroupProtocol.RPC_SNAPSHOT, true, peer.Identity);
    }

    void Broadcast()
    {
        if (!m_Healthy) return;
        m_FullSent = true;
        SendRound(HCGroupSnapshotKind.FULL);
    }

    void Tick(float deltaTime)
    {
        if (!m_Healthy) return;
        HCSaveScheduler.HCPumpFallback(m_SaveJob);
        if (!m_Healthy) { Stop(); return; }
        BeginVisibilityTick();
        int now = HCGroupClock.Utc();
        if (!HCGroupRules.TimestampValid(now) || now < m_LastUtc) { Stop(); return; }
        if (!(deltaTime > 0.0) || deltaTime > 300.0) { Stop(); return; }
        m_LastUtc = now;
        foreach (HCGroupExplorer active : m_State.Explorers)
        {
            if (Live(Peer(active.Id))) active.LastSeenUtc = now;
        }
        // Invitations are ephemeral; removing them needs no disk transaction.
        for (int i = m_State.Invitations.Count() - 1; i >= 0; i--)
        {
            if (m_State.Invitations.Get(i).ExpiresUtc <= now) m_State.Invitations.Remove(i);
        }
        // Expired markers are hidden from snapshots and clients by UTC at
        // once; their durable removal rides the batch below.
        m_DiscoveryTime += deltaTime;
        if (m_DiscoveryTime >= m_Config.DiscoveryIntervalSeconds)
        {
            m_DiscoveryTime = 0;
            Discover();
            if (!m_Healthy) return;
        }
        m_BatchTime += deltaTime;
        if (m_BatchTime >= 60.0)
        {
            int flushed = FlushBatch();
            if (flushed == HCGroupCode.STORAGE) { Stop(); return; }
            if (flushed == HCGroupCode.OK) Broadcast();
        }
        m_PositionTime += deltaTime;
        if (m_PositionTime >= m_Config.PositionIntervalSeconds)
        {
            m_PositionTime = 0;
            if (!m_FullSent) SendRound(HCGroupSnapshotKind.POSITIONS);
        }
    }
}

class HCGroupBatchSaveJob : HCSaveJob
{
    HCGroupService Owner;
    override string HCName() { return "GroupDiscovery"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCStepBatchSave();
    }
}
